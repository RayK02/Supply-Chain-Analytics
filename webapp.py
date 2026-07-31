from __future__ import annotations

import os
from datetime import datetime

from flask import Flask, render_template, request

from inventory import analyse_workbook, export_data_uri

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 60 * 1024 * 1024


@app.get("/")
def index():
    return render_template("index.html", results=None, meta=None, error=None)


@app.get("/health")
def health():
    return {"status": "ok", "app": "lagerhaltungsdaten"}


def _xlsx_error(filename: str, label: str) -> str | None:
    if not filename.lower().endswith(".xlsx"):
        return f"{label} muss eine XLSX-Datei sein: {filename}"
    return None


@app.post("/analyze")
def analyze():
    analysis_file = request.files.get("analysis_file") or request.files.get("file")
    if not analysis_file or not analysis_file.filename:
        return render_template(
            "index.html",
            results=None,
            meta=None,
            error="Bitte die Analyse-Arbeitsmappe auswählen.",
        ), 400

    error = _xlsx_error(analysis_file.filename, "Die Analyse-Arbeitsmappe")
    if error:
        return render_template("index.html", results=None, meta=None, error=error), 400

    current_uploads = [
        uploaded
        for uploaded in request.files.getlist("current_files")
        if uploaded and uploaded.filename
    ]
    for uploaded in current_uploads:
        error = _xlsx_error(uploaded.filename, "Die IST-Lagerhaltungsdatenliste")
        if error:
            return render_template("index.html", results=None, meta=None, error=error), 400

    try:
        current_inputs = [(uploaded.filename, uploaded.stream) for uploaded in current_uploads]
        results, meta = analyse_workbook(analysis_file.stream, current_inputs)
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
        )
    except Exception as exc:
        return render_template(
            "index.html",
            results=None,
            meta=None,
            error=f"Analyse fehlgeschlagen: {exc}",
        ), 400


@app.errorhandler(413)
def too_large(_error):
    return render_template(
        "index.html",
        results=None,
        meta=None,
        error="Die hochgeladenen Dateien sind zusammen grösser als 60 MB.",
    ), 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5050")), debug=False)
