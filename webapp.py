from __future__ import annotations

import os
from datetime import datetime

from flask import Flask, render_template, request

from inventory import analyse_workbook, export_data_uri

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024


@app.get("/")
def index():
    return render_template("index.html", results=None, meta=None, error=None)


@app.get("/health")
def health():
    return {"status": "ok", "app": "lagerhaltungsdaten"}


@app.post("/analyze")
def analyze():
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return render_template("index.html", results=None, meta=None, error="Bitte eine Excel-Datei auswählen."), 400
    if not uploaded.filename.lower().endswith(".xlsx"):
        return render_template("index.html", results=None, meta=None, error="Erlaubt sind ausschliesslich XLSX-Dateien."), 400
    try:
        results, meta = analyse_workbook(uploaded.stream)
        export_uri = export_data_uri(results, meta)
        filename = f"Lagerhaltungsanalyse_{datetime.now():%Y%m%d_%H%M}.xlsx"
        return render_template(
            "index.html",
            results=results,
            meta=meta,
            error=None,
            export_uri=export_uri,
            export_filename=filename,
            source_filename=uploaded.filename,
        )
    except Exception as exc:
        return render_template("index.html", results=None, meta=None, error=f"Analyse fehlgeschlagen: {exc}"), 400


@app.errorhandler(413)
def too_large(_error):
    return render_template("index.html", results=None, meta=None, error="Die Datei ist grösser als 30 MB."), 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5050")), debug=False)
