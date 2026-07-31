from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any

from flask import Flask, render_template, request

from analysis_service import analyse_workbook
from inventory import export_data_uri

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 60 * 1024 * 1024

DEFAULT_ANALYSIS_SETTINGS = {
    "months_average": 3,
    "analysis_start_date": "",
    "analysis_end_date": "",
}


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


def _analysis_settings_from_form() -> tuple[dict[str, Any], dict[str, Any]]:
    raw_months = request.form.get("months_average", "3").strip()
    raw_start = request.form.get("analysis_start_date", "").strip()
    raw_end = request.form.get("analysis_end_date", "").strip()
    display = {
        "months_average": raw_months or 3,
        "analysis_start_date": raw_start,
        "analysis_end_date": raw_end,
    }
    try:
        months = int(raw_months)
    except ValueError as exc:
        raise ValueError("Durchschnittsmonate müssen eine ganze Zahl sein.") from exc
    if not 1 <= months <= 36:
        raise ValueError("Durchschnittsmonate müssen zwischen 1 und 36 liegen.")
    start = _parse_date(raw_start, "Das Startdatum")
    end = _parse_date(raw_end, "Das Enddatum")
    if start and end and start > end:
        raise ValueError("Das Startdatum darf nicht nach dem Enddatum liegen.")
    settings = {
        "months_average": months,
        "analysis_start_date": start,
        "analysis_end_date": end,
    }
    display["months_average"] = months
    return settings, display


@app.post("/analyze")
def analyze():
    try:
        analysis_options, display_settings = _analysis_settings_from_form()
    except ValueError as exc:
        return _render_index(
            error=str(exc),
            status=400,
            analysis_settings={
                "months_average": request.form.get("months_average", "3"),
                "analysis_start_date": request.form.get("analysis_start_date", ""),
                "analysis_end_date": request.form.get("analysis_end_date", ""),
            },
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

    current_uploads = [
        uploaded
        for uploaded in request.files.getlist("current_files")
        if uploaded and uploaded.filename
    ]
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
        results, meta = analyse_workbook(
            analysis_file.stream,
            current_inputs,
            analysis_options,
        )
        export_uri = export_data_uri(results, meta)
        filename = f"Lagerhaltungsanalyse_{datetime.now():%Y%m%d_%H%M}.xlsx"
        return render_template(
            "index.html",
            results=results,
            meta=meta,
            error=None,
            export_uri=export_uri,
            export_filename=filename,
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
        error="Die hochgeladenen Dateien sind zusammen grösser als 60 MB.",
        status=413,
        settings_submitted=False,
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5050")), debug=False)
