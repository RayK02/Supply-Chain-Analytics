import io
from datetime import date

from openpyxl import Workbook

from webapp import app


def workbook_stream() -> io.BytesIO:
    workbook = Workbook()
    sales = workbook.active
    sales.title = "Artikelposten"
    sales.append(["Artikelnr.", "Buchungsdatum", "Belegart", "Menge"])
    sales.append(["A-1", date(2026, 6, 30), "Verkaufslieferung", -100])
    stream = io.BytesIO()
    workbook.save(stream)
    stream.seek(0)
    return stream


def test_results_download_guidance_is_present_in_raw_html():
    client = app.test_client()
    response = client.post(
        "/analyze",
        data={
            "analysis_file": (workbook_stream(), "analysis.xlsx"),
            "months_average": "1",
            "xyz_months": "3",
            "analysis_start_date": "",
            "analysis_end_date": "",
            "output_mode": "view",
        },
        content_type="multipart/form-data",
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Für XLSX: Dateien oben erneut auswählen" in html
    assert "Der Browser gibt die Dateiauswahl nach dem Seitenwechsel nicht zurück" in html
    assert "Direkt als XLSX – ohne Webansicht" in html
    assert "XLSX über Direktmodus" not in html


def test_health_and_response_headers_expose_the_deployed_commit():
    client = app.test_client()
    health = client.get("/health")
    payload = health.get_json()

    assert health.status_code == 200
    assert payload["commit"]
    assert health.headers["X-App-Commit"] == payload["commit"]
