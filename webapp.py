from __future__ import annotations

import io
import os
from datetime import date, datetime
from typing import Any

from flask import Flask, jsonify, redirect, render_template, request, send_file, url_for

from analysis_service import (
    _apply_analysis_settings,
    add_current_workbook,
    analyse_workbook,
    finalize_prepared_analysis,
    prepare_analysis_workbook,
)
from analysis_token import AnalysisTokenError, decode_analysis_token, encode_analysis_token
from inventory import build_export

app = Flask(__name__)
# Vercel rejects request bodies at 4.5 MB before Flask can handle them.
# Workbooks are therefore transferred one at a time and the browser keeps
# enough headroom for multipart framing below the platform limit.
app.config["MAX_CONTENT_LENGTH"] = 4_490_000

APP_COMMIT = os.environ.get("VERCEL_GIT_COMMIT_SHA", "local")
DEFAULT_ANALYSIS_SETTINGS = {
    "months_average": "",
    "xyz_months": "",
    "analysis_start_date": "",
    "analysis_end_date": "",
}
MAX_RENDERED_RESULTS = 1_500

_OLD_DOWNLOAD_GUIDANCE = (
    '<span class="download disabled" title="Für einen XLSX-Export oben den direkten XLSX-Modus wählen">'
    'XLSX über Direktmodus</span>'
)
_NEW_DOWNLOAD_GUIDANCE = (
    '<span class="download disabled" aria-disabled="true" '
    'title="Der Browser gibt die Dateiauswahl nach dem Seitenwechsel nicht zurück. '
    'Deshalb oben dieselben Dateien erneut auswählen und «Direkt als XLSX – ohne Webansicht» klicken.">'
    'Für XLSX: Dateien oben erneut auswählen</span>'
)
_OLD_UPLOAD_NOTE = "Web-Upload: insgesamt maximal ca. 4 MB."
_NEW_UPLOAD_NOTE = (
    "Web-Upload: Dateien zuerst einlesen, danach Zeitraum und Berechnungslogik festlegen. "
    "Jede einzelne Datei darf maximal ca. 4,43 MB gross sein."
)
_OLD_CLIENT_MESSAGES = '<div id="clientError" class="message error" hidden></div>'
_NEW_CLIENT_MESSAGES = (
    '<div id="clientStatus" class="message warning" role="status" aria-live="polite" hidden></div>\n'
    '      <div id="clientError" class="message error" role="alert" hidden></div>'
)


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-App-Commit"] = APP_COMMIT
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self'; script-src 'self'; "
        "img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    )
    return response


def _render_page(**context: Any) -> str:
    html = render_template("index.html", **context)
    return (
        html.replace(_OLD_DOWNLOAD_GUIDANCE, _NEW_DOWNLOAD_GUIDANCE)
        .replace(_OLD_UPLOAD_NOTE, _NEW_UPLOAD_NOTE)
        .replace(_OLD_CLIENT_MESSAGES, _NEW_CLIENT_MESSAGES)
    )


def _render_index(
    *,
    error: str | None = None,
    status: int = 200,
    analysis_settings: dict[str, Any] | None = None,
    settings_submitted: bool = False,
    **context: Any,
):
    return _render_page(
        results=None,
        meta=None,
        error=error,
        analysis_settings={**DEFAULT_ANALYSIS_SETTINGS, **(analysis_settings or {})},
        settings_submitted=settings_submitted,
        **context,
    ), status


def _api_error(message: str, status: int = 400):
    return jsonify({"error": message}), status


@app.get("/")
def index():
    return _render_index()


@app.get("/analyze")
def analyze_get():
    return redirect(url_for("index"), code=303)


@app.get("/health")
def health():
    return {"status": "ok", "app": "lagerhaltungsdaten", "commit": APP_COMMIT}


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


def _send_export(results: list[dict[str, Any]], meta: dict[str, Any]):
    export_bytes = build_export(results, meta)
    export_filename = f"Lagerhaltungsanalyse_{datetime.now():%Y%m%d_%H%M}.xlsx"
    return send_file(
        io.BytesIO(export_bytes),
        as_attachment=True,
        download_name=export_filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        max_age=0,
    )


def _render_results(
    results: list[dict[str, Any]],
    meta: dict[str, Any],
    *,
    source_filename: str,
    current_filenames: list[str],
    analysis_settings: dict[str, Any],
):
    result_count_total = len(results)
    rendered_results = results[:MAX_RENDERED_RESULTS]
    if result_count_total > MAX_RENDERED_RESULTS:
        meta.setdefault("warnings", []).append(
            f"Zur Stabilität werden in der Webansicht nur die ersten {MAX_RENDERED_RESULTS} von "
            f"{result_count_total} Artikeln angezeigt. Der direkte XLSX-Download enthält alle Artikel."
        )

    return _render_page(
        results=rendered_results,
        result_count_total=result_count_total,
        meta=meta,
        error=None,
        source_filename=source_filename,
        current_filenames=current_filenames,
        analysis_settings=analysis_settings,
        settings_submitted=True,
    )


def _payload_date_range(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    dates = [row[3] for row in payload.get("sales", []) if isinstance(row, list) and len(row) == 6 and isinstance(row[3], date)]
    if not dates:
        return None, None
    return min(dates).isoformat(), max(dates).isoformat()


@app.post("/api/prepare-analysis")
def prepare_analysis_api():
    """Read the analysis workbook only; UI settings are deliberately applied later."""
    try:
        analysis_file = request.files.get("analysis_file")
        if not analysis_file or not analysis_file.filename:
            return _api_error("Bitte die Analyse-Arbeitsmappe auswählen.")
        error = _xlsx_error(analysis_file.filename, "Die Analyse-Arbeitsmappe")
        if error:
            return _api_error(error)

        payload = prepare_analysis_workbook(
            analysis_file.stream,
            None,
            source_filename=analysis_file.filename,
        )
        data_start, data_end = _payload_date_range(payload)
        return jsonify({
            "token": encode_analysis_token(payload),
            "data_start": data_start,
            "data_end": data_end,
            "sales_rows": len(payload.get("sales", [])),
        })
    except (ValueError, AnalysisTokenError) as exc:
        return _api_error(str(exc))
    except Exception:
        return _api_error("Die Analyse-Arbeitsmappe konnte nicht vorbereitet werden.")


@app.post("/api/add-current")
def add_current_api():
    try:
        payload = decode_analysis_token(request.form.get("analysis_token", ""))
        current_file = request.files.get("current_file")
        if not current_file or not current_file.filename:
            return _api_error("Bitte eine IST-Lagerhaltungsdatenliste auswählen.")
        error = _xlsx_error(current_file.filename, "Die IST-Lagerhaltungsdatenliste")
        if error:
            return _api_error(error)

        add_current_workbook(payload, current_file.filename, current_file.stream)
        return jsonify({"token": encode_analysis_token(payload)})
    except (ValueError, AnalysisTokenError) as exc:
        return _api_error(str(exc))
    except Exception:
        return _api_error("Die IST-Lagerhaltungsdatenliste konnte nicht verarbeitet werden.")


@app.post("/api/finalize-analysis")
def finalize_analysis_api():
    try:
        analysis_options, display_settings = _analysis_settings_from_form()
        payload = decode_analysis_token(request.form.get("analysis_token", ""))
        # The workbook is already prepared. Apply the values currently visible in
        # the UI now, immediately before the one and only calculation.
        payload["parameters"] = _apply_analysis_settings(dict(payload["parameters"]), analysis_options)
        results, meta = finalize_prepared_analysis(payload)
        if request.form.get("output_mode") == "download":
            return _send_export(results, meta)
        return _render_results(
            results,
            meta,
            source_filename=payload["source_filename"],
            current_filenames=list(payload["current_filenames"]),
            analysis_settings=display_settings,
        )
    except (ValueError, AnalysisTokenError) as exc:
        return _api_error(str(exc))
    except Exception:
        return _api_error("Die vorbereitete Analyse konnte nicht abgeschlossen werden.")


@app.post("/analyze")
def analyze():
    """No-JavaScript fallback. The browser UI normally uses the stateless API."""
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
            return _send_export(results, meta)
        return _render_results(
            results,
            meta,
            source_filename=analysis_file.filename,
            current_filenames=[uploaded.filename for uploaded in current_uploads],
            analysis_settings=display_settings,
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
    message = (
        "Eine einzelne Datei überschreitet das Web-Limit. Vercel akzeptiert pro Anfrage maximal 4,5 MB; "
        "die App lässt deshalb etwa 4,43 MB pro Einzeldatei zu. Bitte die Datei verkleinern oder die lokale Version verwenden."
    )
    if request.path.startswith("/api/"):
        return _api_error(message, status=413)
    return _render_index(
        error=message,
        status=413,
        settings_submitted=False,
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5050")), debug=False)
