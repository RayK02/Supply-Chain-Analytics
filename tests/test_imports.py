from pathlib import Path

from app.imports import decimal_value, import_rows, normalize_row, read_csv_rows, suggest_mapping
from app.services import parse_dt


def test_alias_mapping():
    mapping=suggest_mapping(["Sales Order No.","Standort","Bestelldatum","Registered Pick Date"])
    assert mapping["Sales Order No."] == "at_sales_order_no"
    assert mapping["Standort"] == "location_code"
    assert mapping["Registered Pick Date"] == "pick_registered_at"


def test_dates_and_decimals():
    assert parse_dt("21.07.2026").day == 21
    assert decimal_value("1.234,56") == 1234.56
    assert decimal_value("1,234.56") == 1234.56


def test_normalize_row(app):
    db=app.extensions["db"]
    row=normalize_row({"Ort":"CH","SO":"SO-5","Datum":"21.07.2026"},{"Ort":"location_code","SO":"at_sales_order_no","Datum":"order_at"},db)
    assert row["tracking_id"] == "SO-5" and row["location_id"]


def test_complete_csv_import_and_duplicate(app, tmp_path):
    db = app.extensions["db"]
    path = tmp_path / "orders.csv"
    path.write_text("Tracking-ID;Sales Order No.;Standort;Bestelldatum\nIMP-1;SO-IMP-1;CH;21.07.2026\n", encoding="utf-8")
    rows = read_csv_rows(path)
    mapping = suggest_mapping(rows[0].keys())
    first = import_rows(db, rows, mapping, path.name)
    second = import_rows(db, rows, mapping, path.name, "skip")
    assert first["new"] == 1 and second["skipped"] == 1
