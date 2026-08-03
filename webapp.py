from __future__ import annotations

import io
import os
from datetime import date, datetime
from typing import Any

from flask import Flask, redirect, render_template, request, send_file, url_for

from analysis_service import analyse_workbook
from inventory import build_export

app = Flask(__name__)
# Vercel Functions reject payloads around 4.5 MB before Flask can handle them.
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024

DEFAULT_ANALYSIS_SETTINGS = {
    "months_average": "",
    "xyz_months": "",
    "analysis_start_date": "",
    "analysis_end_date": "",
}
MAX_RENDERED_RESULTS = 1_500


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self'; script-src 'self'; "
        "img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    )
    return response


def _render_index(
    *,
    error: str | None = None,
    status: int = 200,
    analysis_settings: dict[str, Any] | None = None,
    settings_submitted: bool = False,
    **context: Any,
):
    return render_template(
        "index.html",
        results=None,
        meta=None,
        error=error,
        analysis_settings={**DEFAULT_ANALYSIS_SETTINGS, **(analysis_settings or {})},
        settings_submitted=settings_submitted,
        **context,
    ), status


@app.get("/")
def index():
    return _render_index()


@app.get("/analyze")
def analyze_get():
    return redirect(url_for("index"), code=303)


@app.get("/health")
def health():
    return {"status": "ok", "app": "lagerhaltungsdaten"}


def _xlsx_error(filename: str, label: str) -> str | None:
    if not filename.lower().endswith(".xlsx"):
        return f"{label} muss eine XLSX-Datei sein: {filename}"
    return None


def _parse_date(value: str, label: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"{label} ist ungültig.") from exc


def _optional_months(raw: str, label: str, minimum: int) -> int | None:
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{label} müssen eine ganze Zahl sein.") from exc
    if not minimum <= value <= 36:
        raise ValueError(f"{label} müssen zwischen {minimum} und 36 liegen.")
    return value


def _analysis_settings_from_form() -> tuple[dict[str, Any], dict[str, Any]]:
    raw_months = request.form.get("months_average", "").strip()
    raw_xyz_months = request.form.get("xyz_months", "").strip()
    raw_start = request.form.get("analysis_start_date", "").strip()
    raw_end = request.form.get("analysis_end_date", "").strip()
    display: dict[str, Any] = {
        "months_average": raw_months,
        "xyz_months": raw_xyz_months,
        "analysis_start_date": raw_start,
        "analysis_end_date": raw_end,
    }
    settings: dict[str, Any] = {
        "analysis_start_date": _parse_date(raw_start, "Das Startdatum"),
        "analysis_end_date": _parse_date(raw_end, "Das Enddatum"),
    }

    months = _optional_months(raw_months, "Durchschnittsmonate", 1)
    if months is not None:
        settings["months_average"] = months
        display["months_average"] = months
    xyz_months = _optional_months(raw_xyz_months, "XYZ-Monate", 3)
    if xyz_months is not None:
        settings["xyz_months"] = xyz_months
        display["xyz_months"] = xyz_months

    start = settings["analysis_start_date"]
    end = settings["analysis_end_date"]
    if start and end and start > end:
        raise ValueError("Das Startdatum darf nicht nach dem Enddatum liegen.")
    return settings, display


def _display_settings_from_request() -> dict[str, Any]:
    return {
        "months_average": request.form.get("months_average", ""),
        "xyz_months": request.form.get("xyz_months", ""),
        "analysis_start_date": request.form.get("analysis_start_date", ""),
        "analysis_end_date": request.form.get("analysis_end_date", ""),
    }


@app.post("/analyze")
def analyze():
    try:
        analysis_options, display_settings = _analysis_settings_from_form()
    except ValueError as exc:
        return _render_index(
            error=str(exc),
            status=400,
            analysis_settings=_display_settings_from_request(),
            settings_submitted=True,
        )

    analysis_file = request.files.get("analysis_file") or request.files.get("file")
    if not analysis_file or not analysis_file.filename:
        return _render_index(
            error="Bitte die Analyse-Arbeitsmappe auswählen.",
            status=400,
            analysis_settings=display_settings,
            settings_submitted=True,
        )

    error = _xlsx_error(analysis_file.filename, "Die Analyse-Arbeitsmappe")
    if error:
        return _render_index(
            error=error,
            status=400,
            analysis_settings=display_settings,
            settings_submitted=True,
        )

    current_uploads = [uploaded for uploaded in request.files.getlist("current_files") if uploaded and uploaded.filename]
    for uploaded in current_uploads:
        error = _xlsx_error(uploaded.filename, "Die IST-Lagerhaltungsdatenliste")
        if error:
            return _render_index(
                error=error,
                status=400,
                analysis_settings=display_settings,
                settings_submitted=True,
            )

    try:
        current_inputs = [(uploaded.filename, uploaded.stream) for uploaded in current_uploads]
        results, meta = analyse_workbook(analysis_file.stream, current_inputs, analysis_options)

        if request.form.get("output_mode") == "download":
            export_bytes = build_export(results, meta)
            export_filename = f"Lagerhaltungsanalyse_{datetime.now():%Y%m%d_%H%M}.xlsx"
            return send_file(
                io.BytesIO(export_bytes),
                as_attachment=True,
                download_name=export_filename,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                max_age=0,
            )

        result_count_total = len(results)
        rendered_results = results[:MAX_RENDERED_RESULTS]
        if result_count_total > MAX_RENDERED_RESULTS:
            meta.setdefault("warnings", []).append(
                f"Zur Stabilität werden in der Webansicht nur die ersten {MAX_RENDERED_RESULTS} von "
                f"{result_count_total} Artikeln angezeigt. Der direkte XLSX-Download enthält alle Artikel."
            )

        return render_template(
            "index.html",
            results=rendered_results,
            result_count_total=result_count_total,
            meta=meta,
            error=None,
            source_filename=analysis_file.filename,
            current_filenames=[uploaded.filename for uploaded in current_uploads],
            analysis_settings=display_settings,
            settings_submitted=True,
        )
    except Exception as exc:
        return _render_index(
            error=f"Analyse fehlgeschlagen: {exc}",
            status=400,
            analysis_settings=display_settings,
            settings_submitted=True,
        )


@app.errorhandler(413)
def too_large(_error):
    return _render_index(
        error="Die Dateien sind für den Web-Upload zu gross. Bitte insgesamt unter 4 MB bleiben oder die lokale Version verwenden.",
        status=413,
        settings_submitted=False,
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5050")), debug=False)
