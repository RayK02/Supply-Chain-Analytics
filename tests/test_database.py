from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.services import create_backup, list_orders, restore_backup, save_order, validate_order


def sample(app, tracking="T-1", at_no="SO-1"):
    db=app.extensions["db"]; loc=db.one("SELECT id FROM locations WHERE code='CH'")
    return {"tracking_id":tracking,"warehouse_order_no":"PO-"+tracking,"at_sales_order_no":at_no,"external_document_no":"EXT-"+tracking,"location_id":loc["id"],"order_at":"2026-07-01T08:00:00+00:00","created_at_at":"2026-07-01T08:00:00+00:00","released_at":"2026-07-02T08:00:00+00:00","priority":"normal","data_source":"Test"}


def test_save_event_duplicate_and_location_filter(app):
    db=app.extensions["db"]; item=sample(app); oid=save_order(db,item)
    assert db.scalar("SELECT COUNT(*) FROM events WHERE order_id=?",(oid,)) >= 1
    assert validate_order(sample(app,"T-2","SO-1"),db)
    assert len(list_orders(db,{"location":"CH"})) == 1
    assert len(list_orders(db,{"open":"1"})) == 1


def test_backup_restore(app,tmp_path):
    db=app.extensions["db"]; save_order(db,sample(app)); folder=tmp_path/"b"
    backup=create_backup(db,folder)
    with db.transaction() as con: con.execute("DELETE FROM orders")
    assert db.scalar("SELECT COUNT(*) FROM orders") == 0
    restore_backup(db,backup,folder)
    assert db.scalar("SELECT COUNT(*) FROM orders") == 1

