from datetime import date

import pytest

from app.inventory_analysis import calculate_analysis


def sale(day: date, quantity: float, article: str = "000001", document_type: str = "Verkaufslieferung") -> dict:
    return {
        "article_key": article,
        "description": "Testartikel",
        "booking_date": day,
        "document_type": document_type,
        "quantity": -quantity,
    }


def test_analysis_dates_filter_abc_total_and_average_window():
    rows = [
        sale(date(2026, 1, 31), 10),
        sale(date(2026, 2, 28), 20),
        sale(date(2026, 3, 31), 30),
        sale(date(2026, 4, 30), 40),
        sale(date(2026, 5, 31), 50),
        sale(date(2026, 6, 30), 60),
    ]
    results, meta = calculate_analysis(rows, parameters={
        "analysis_start_date": "2026-03-01",
        "analysis_end_date": "2026-06-30",
        "months_average": 2,
    })
    result = results[0]
    assert result["sales_total"] == 180
    assert result["sales_recent"] == 110
    assert result["average_month"] == 55
    assert result["monthly_sales"] == [50, 60]
    assert result["xyz_class"] == "X"
    assert result["xyz_reason"] is None
    assert meta["analysis_start"] == date(2026, 3, 1)
    assert meta["analysis_end"] == date(2026, 6, 30)
    assert meta["average_start"] == date(2026, 5, 1)
    assert meta["average_end"] == date(2026, 6, 30)
    assert meta["months_average"] == 2
    assert meta["xyz_months_used"] == 4


def test_changing_average_months_changes_average_but_not_abc_total():
    rows = [
        sale(date(2026, 3, 31), 30),
        sale(date(2026, 4, 30), 40),
        sale(date(2026, 5, 31), 50),
        sale(date(2026, 6, 30), 60),
    ]
    two_months, _ = calculate_analysis(rows, parameters={
        "analysis_start_date": "2026-03-01",
        "analysis_end_date": "2026-06-30",
        "months_average": 2,
    })
    three_months, _ = calculate_analysis(rows, parameters={
        "analysis_start_date": "2026-03-01",
        "analysis_end_date": "2026-06-30",
        "months_average": 3,
    })
    assert two_months[0]["sales_total"] == three_months[0]["sales_total"] == 180
    assert two_months[0]["average_month"] == 55
    assert three_months[0]["average_month"] == 50


def test_date_boundaries_are_inclusive():
    rows = [
        sale(date(2026, 3, 1), 10),
        sale(date(2026, 3, 31), 20),
        sale(date(2026, 4, 1), 30),
    ]
    results, _ = calculate_analysis(rows, parameters={
        "analysis_start_date": "2026-03-01",
        "analysis_end_date": "2026-03-31",
        "months_average": 1,
    })
    assert results[0]["sales_total"] == 30
    assert results[0]["average_month"] == 30


def test_partial_end_month_is_excluded_from_average():
    rows = [
        sale(date(2026, 4, 30), 100),
        sale(date(2026, 5, 31), 100),
        sale(date(2026, 6, 30), 100),
        sale(date(2026, 7, 15), 50),
    ]
    results, meta = calculate_analysis(rows, parameters={
        "analysis_start_date": "2026-04-01",
        "analysis_end_date": "2026-07-15",
        "months_average": 3,
    })
    assert results[0]["sales_total"] == 350
    assert results[0]["monthly_sales"] == [100, 100, 100]
    assert results[0]["average_month"] == 100
    assert meta["average_start"] == date(2026, 4, 1)
    assert meta["average_end"] == date(2026, 6, 30)
    assert any("angebrochene Monat" in warning for warning in meta["warnings"])


def test_invalid_date_range_is_rejected():
    with pytest.raises(ValueError, match="Startdatum"):
        calculate_analysis([sale(date(2026, 3, 1), 10)], parameters={
            "analysis_start_date": "2026-04-01",
            "analysis_end_date": "2026-03-01",
            "months_average": 3,
        })


def test_average_month_range_is_validated():
    with pytest.raises(ValueError, match="zwischen 1 und 36"):
        calculate_analysis([sale(date(2026, 3, 1), 10)], parameters={"months_average": 0})
    with pytest.raises(ValueError, match="zwischen 1 und 36"):
        calculate_analysis([sale(date(2026, 3, 1), 10)], parameters={"months_average": 37})


def test_xyz_month_range_is_validated():
    with pytest.raises(ValueError, match="XYZ-Monate"):
        calculate_analysis([sale(date(2026, 3, 31), 10)], parameters={"xyz_months": 2})
    with pytest.raises(ValueError, match="XYZ-Monate"):
        calculate_analysis([sale(date(2026, 3, 31), 10)], parameters={"xyz_months": 37})
