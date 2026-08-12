from __future__ import annotations

import io
from datetime import date

from openpyxl import Workbook

from webapp import app


def workbook_stream() -> io.BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Artikelposten"
    sheet.append(["Artikelnr.", "Buchungsdatum", "Belegart", "Menge", "Beschreibung"])
    sheet.append(["A-100", date(2026, 1, 31), "Verkaufslieferung", -100, "Testartikel"])
    sheet.append(["A-100", date(2026, 4, 30), "Verkaufslieferung", -300, "Testartikel"])
    stream = io.BytesIO()
    workbook.save(stream)
    stream.seek(0)
    return stream


def prepare_token(client) -> str:
    response = client.post(
        "/api/prepare-analysis",
        data={"analysis_file": (workbook_stream(), "analysis.xlsx")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["data_start"] == "2026-01-31"
    assert payload["data_end"] == "2026-04-30"
    assert payload["sales_rows"] == 2
    return payload["token"]


def test_same_prepared_upload_can_be_recalculated_with_different_dates():
    client = app.test_client()
    token = prepare_token(client)

    january = client.post(
        "/api/finalize-analysis",
        data={
            "analysis_token": token,
            "output_mode": "view",
            "months_average": "1",
            "xyz_months": "3",
            "analysis_start_date": "2026-01-01",
            "analysis_end_date": "2026-01-31",
        },
        content_type="multipart/form-data",
    )
    april = client.post(
        "/api/finalize-analysis",
        data={
            "analysis_token": token,
            "output_mode": "view",
            "months_average": "1",
            "xyz_months": "3",
            "analysis_start_date": "2026-04-01",
            "analysis_end_date": "2026-04-30",
        },
        content_type="multipart/form-data",
    )

    assert january.status_code == 200
    assert april.status_code == 200
    january_text = january.get_data(as_text=True)
    april_text = april.get_data(as_text=True)
    assert "01.01.2026" in january_text
    assert "31.01.2026" in january_text
    assert "Netto 100" in january_text
    assert "01.04.2026" in april_text
    assert "30.04.2026" in april_text
    assert "Netto 300" in april_text


def test_prepare_does_not_require_or_validate_analysis_dates():
    client = app.test_client()
    response = client.post(
        "/api/prepare-analysis",
        data={
            "analysis_file": (workbook_stream(), "analysis.xlsx"),
            "analysis_start_date": "2026-07-01",
            "analysis_end_date": "2026-04-01",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200

    invalid_finalize = client.post(
        "/api/finalize-analysis",
        data={
            "analysis_token": response.get_json()["token"],
            "output_mode": "view",
            "analysis_start_date": "2026-07-01",
            "analysis_end_date": "2026-04-01",
        },
        content_type="multipart/form-data",
    )
    assert invalid_finalize.status_code == 400
    assert "Startdatum darf nicht nach dem Enddatum" in invalid_finalize.get_json()["error"]


def test_index_documents_prepare_then_configure_workflow_and_new_file_limit():
    client = app.test_client()
    response = client.get("/")
    text = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Dateien zuerst einlesen, danach Zeitraum und Berechnungslogik festlegen" in text
    assert "4,43 MB" in text
