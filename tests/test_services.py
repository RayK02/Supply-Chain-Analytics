from datetime import datetime, timezone

import pytest

from app.services import calculate_status, duration, percentile, quality_issues, stats, work_hours


def dt(text): return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)


def test_workdays_skip_weekend():
    assert work_hours(dt("2026-07-17T00:00"), dt("2026-07-20T00:00")) == 24
    assert duration("2026-07-17T00:00", "2026-07-20T00:00", "workdays") == 1


def test_calendar_days_and_hours():
    assert duration("2026-07-01T08:00", "2026-07-03T20:00", "days") == 2.5
    assert duration("2026-07-01T08:00", "2026-07-03T20:00", "hours") == 60


def test_missing_and_negative_duration():
    assert duration(None, "2026-07-01", "days") is None
    assert duration("2026-07-03", "2026-07-01", "days") == -2


def test_statistics_and_sla():
    result = stats([1, 2, 3, 10], sla=3)
    assert result["median"] == 2.5 and result["p80"] == pytest.approx(5.8)
    assert result["within_sla"] == 75 and result["outside_sla"] == 25


def test_status_progression():
    assert calculate_status({"created_at_at":"x","released_at":"x","pick_created_at":"x"}) == "wartet auf Pick"
    assert calculate_status({"picked_up_at":"x"}) == "unterwegs"
    assert calculate_status({"received_at":"x"}) == "abgeschlossen"


def test_quality_invalid_sequence_and_missing():
    issues = quality_issues({"tracking_id":"X","location_id":1,"order_at":"2026-01-01","at_sales_order_no":"SO","created_at_at":"2026-01-03","released_at":"2026-01-02"})
    assert any(x["code"] == "invalid_sequence" for x in issues)
