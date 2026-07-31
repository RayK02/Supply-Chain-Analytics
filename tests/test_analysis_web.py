from __future__ import annotations

import io
from datetime import date

from openpyxl import Workbook

from webapp import app


def analysis_workbook() -> io.BytesIO:
    workbook = Workbook()
    sales = workbook.active
    sales.title = "Artikelposten"
    sales.append(["Artikelnr.", "Buchungsdatum", "Belegart", "Menge", "Beschreibung"])
    for day, quantity in (
        (date(2026, 3, 31), -30),
        (date(2026, 4, 30), -40),
        (date(2026, 5, 31), -50),
        (date(2026, 6, 30), -60),
    ):
        sales.append(["000040", day, "Verkaufslieferung", quantity, "Testartikel"])
    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def test_web_form_applies_and_displays_analysis_settings():
    client = app.test_client()
    response = client.post(
        "/analyze",
        data={
            "analysis_file": (analysis_workbook(), "analysis.xlsx"),
            "months_average": "2",
            "analysis_start_date": "2026-03-01",
            "analysis_end_date": "2026-06-30",
        },
        content_type="multipart/form-data",
    )
    text = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "01.03.2026" in text
    assert "30.06.2026" in text
    assert "2 Kalendermonate" in text
    assert 'value="2"' in text
    assert "localStorage" in text


def test_web_form_rejects_reversed_dates_and_keeps_values():
    client = app.test_client()
    response = client.post(
        "/analyze",
        data={
            "analysis_file": (analysis_workbook(), "analysis.xlsx"),
            "months_average": "3",
            "analysis_start_date": "2026-07-01",
            "analysis_end_date": "2026-06-30",
        },
        content_type="multipart/form-data",
    )
    text = response.get_data(as_text=True)
    assert response.status_code == 400
    assert "Startdatum darf nicht nach dem Enddatum" in text
    assert 'value="2026-07-01"' in text
    assert 'value="2026-06-30"' in text
