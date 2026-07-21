from __future__ import annotations

import math
import shutil
import sqlite3
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from .db import Database, ORDER_FIELDS, TIMESTAMP_FIELDS, utcnow


PHASES = {
    "order_release": ("created_at_at", "released_at", "Order-to-Release"),
    "release_pick": ("released_at", "pick_created_at", "Release-to-Pick"),
    "waiting_pick": ("pick_created_at", "pick_started_at", "Warten auf Pick"),
    "pick_cycle": ("pick_started_at", "pick_registered_at", "Pick-Durchlaufzeit"),
    "pack": ("pick_registered_at", "packed_at", "Packzeit"),
    "documents": ("pick_registered_at", "documents_complete_at", "Dokumentenzeit"),
    "order_ready": ("created_at_at", "ready_at", "Order-to-Ready"),
    "ready_pickup": ("ready_at", "picked_up_at", "Ready-to-Pickup"),
    "transport": ("picked_up_at", "received_at", "Transportlaufzeit"),
    "total": ("created_at_at", "received_at", "Gesamtdurchlaufzeit"),
}

STATUS_VALUES = ["neu", "im System", "freigegeben", "wartet auf Pick", "wird kommissioniert", "Pick abgeschlossen", "wird verpackt", "wartet auf Dokumente", "abholbereit", "wartet auf Abholung", "unterwegs", "angekommen", "abgeschlossen", "storniert", "Daten unvollständig"]

TIMELINE = [
    ("order_at", "Bestellt"), ("created_at_at", "Auftrag erstellt"), ("released_at", "Freigegeben"),
    ("pick_created_at", "Pick erstellt"), ("pick_started_at", "Pick begonnen"),
    ("pick_registered_at", "Pick registriert"), ("packed_at", "Verpackt"),
    ("documents_complete_at", "Dokumente vollständig"), ("ready_at", "Abholbereit"),
    ("picked_up_at", "Abgeholt"), ("received_at", "Wareneingang"),
]


def parse_dt(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


def work_hours(start: datetime, end: datetime, holidays: set[str] | None = None) -> float:
    """Elapsed working time, counting only Mon-Fri. Calendar adapter can add holidays."""
    if end < start:
        return -work_hours(end, start, holidays)
    holidays = holidays or set()
    cursor = start
    total = 0.0
    while cursor.date() < end.date():
        nxt = datetime.combine(cursor.date() + timedelta(days=1), datetime.min.time(), tzinfo=cursor.tzinfo)
        if cursor.weekday() < 5 and cursor.date().isoformat() not in holidays:
            total += (nxt - cursor).total_seconds() / 3600
        cursor = nxt
    if cursor.weekday() < 5 and cursor.date().isoformat() not in holidays:
        total += (end - cursor).total_seconds() / 3600
    return total


def duration(start: Any, end: Any, unit: str = "workdays") -> float | None:
    a, b = parse_dt(start), parse_dt(end)
    if not a or not b:
        return None
    hours = work_hours(a, b) if unit == "workdays" else (b - a).total_seconds() / 3600
    if unit in ("days", "workdays"):
        return round(hours / 24, 2)
    return round(hours, 2)


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    pos = (len(ordered) - 1) * p
    low, high = math.floor(pos), math.ceil(pos)
    return ordered[low] if low == high else ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


def stats(values: Iterable[float], sla: float | None = None) -> dict[str, Any]:
    clean = [float(v) for v in values if v is not None and v >= 0]
    within = sum(1 for v in clean if sla is not None and v <= sla)
    return {
        "count": len(clean), "avg": round(statistics.mean(clean), 2) if clean else None,
        "median": round(statistics.median(clean), 2) if clean else None,
        "min": round(min(clean), 2) if clean else None, "max": round(max(clean), 2) if clean else None,
        "p80": round(percentile(clean, .8), 2) if clean else None,
        "p90": round(percentile(clean, .9), 2) if clean else None,
        "within_sla": round(within / len(clean) * 100, 1) if clean and sla is not None else None,
        "outside_sla": round((len(clean) - within) / len(clean) * 100, 1) if clean and sla is not None else None,
    }


def calculate_status(order: dict[str, Any]) -> str:
    if order.get("status") == "storniert": return "storniert"
    if order.get("received_at"): return "abgeschlossen"
    if order.get("picked_up_at"): return "unterwegs"
    if order.get("ready_at"): return "wartet auf Abholung"
    if order.get("documents_complete_at") and order.get("packed_at"): return "abholbereit"
    if order.get("packed_at"): return "wartet auf Dokumente"
    if order.get("pick_registered_at"): return "wird verpackt"
    if order.get("pick_started_at"): return "wird kommissioniert"
    if order.get("pick_created_at"): return "wartet auf Pick"
    if order.get("released_at"): return "freigegeben"
    if order.get("created_at_at"): return "im System"
    return "neu"


def quality_issues(order: dict[str, Any], known_statuses: list[str] | None = None) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for field, label in (("tracking_id", "Tracking-ID"), ("location_id", "Standort"), ("order_at", "Bestelldatum"), ("at_sales_order_no", "AT-Auftrag")):
        if not order.get(field): issues.append({"code": f"missing_{field}", "severity": "error", "message": f"{label} fehlt"})
    ordered = [(field, parse_dt(order.get(field))) for field, _ in TIMELINE]
    present = [(f, d) for f, d in ordered if d]
    for (fa, a), (fb, b) in zip(present, present[1:]):
        if b < a: issues.append({"code": "invalid_sequence", "severity": "error", "message": f"Unlogische Reihenfolge: {fb} liegt vor {fa}"})
    if order.get("picked_up_at") and not order.get("ready_at"):
        issues.append({"code": "missing_ready", "severity": "warning", "message": "Abholung vorhanden, Abholbereitschaft fehlt"})
    if order.get("received_at") and not order.get("picked_up_at"):
        issues.append({"code": "missing_pickup", "severity": "warning", "message": "Wareneingang vorhanden, Abholung fehlt"})
    if known_statuses and order.get("status") not in known_statuses:
        issues.append({"code": "unknown_status", "severity": "warning", "message": "Unbekannter Status"})
    total = duration(order.get("created_at_at"), order.get("received_at"), "days")
    if total is not None and total > 120:
        issues.append({"code": "outlier", "severity": "warning", "message": "Extreme Gesamtdurchlaufzeit (>120 Tage)"})
    return issues


def enrich_order(row: Any, unit: str = "workdays") -> dict[str, Any]:
    order = dict(row)
    order["durations"] = {key: duration(order.get(a), order.get(b), unit) for key, (a, b, _) in PHASES.items()}
    now = datetime.now(timezone.utc)
    order["open_age"] = None if order.get("received_at") else duration(order.get("created_at_at") or order.get("order_at"), now, unit)
    order["quality_issues"] = quality_issues(order, STATUS_VALUES)
    sla_total = order.get("sla_total")
    total_or_open = order["durations"]["total"] if order["durations"]["total"] is not None else order["open_age"]
    if total_or_open is None or sla_total is None: order["sla_state"] = "unbekannt"
    elif total_or_open > sla_total: order["sla_state"] = "überschritten"
    elif total_or_open > sla_total * .8: order["sla_state"] = "gefährdet"
    else: order["sla_state"] = "innerhalb"
    return order


def validate_order(data: dict[str, Any], db: Database, order_id: int | None = None) -> list[str]:
    errors = []
    if not str(data.get("tracking_id") or "").strip(): errors.append("Tracking-ID ist erforderlich.")
    if not data.get("location_id"): errors.append("Standort ist erforderlich.")
    if not data.get("order_at"): errors.append("Bestelldatum ist erforderlich.")
    if not any(data.get(k) for k in ("warehouse_order_no", "at_sales_order_no", "external_document_no")):
        errors.append("Mindestens eine Auftragsreferenz ist erforderlich.")
    for field in TIMESTAMP_FIELDS:
        if data.get(field) and not parse_dt(data[field]): errors.append(f"Ungültiges Datum in {field}.")
    errors.extend(i["message"] for i in quality_issues(data) if i["severity"] == "error" and not i["code"].startswith("missing_"))
    for field in ("tracking_id", "warehouse_order_no", "at_sales_order_no"):
        value = str(data.get(field) or "").strip()
        if value:
            row = db.one(f"SELECT id FROM orders WHERE {field}=? COLLATE NOCASE", (value,))
            if row and row["id"] != order_id: errors.append(f"{field} ist bereits vorhanden.")
    return errors


def save_order(db: Database, data: dict[str, Any], order_id: int | None = None, source: str = "Manuell") -> int:
    clean = {k: (data.get(k) if data.get(k) != "" else None) for k in ORDER_FIELDS}
    for field in ("location_id", "line_count", "pallet_count", "delay_reason_id"):
        clean[field] = int(clean[field]) if clean.get(field) not in (None, "") else None
    for field in ("total_quantity", "total_weight", "order_value"):
        clean[field] = float(str(clean[field]).replace(",", ".")) if clean.get(field) not in (None, "") else None
    clean["status"] = calculate_status(clean)
    now = utcnow()
    with db.transaction() as con:
        if order_id:
            old = dict(con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone())
            sets = ",".join(f"{k}=?" for k in clean)
            con.execute(f"UPDATE orders SET {sets},updated_at=? WHERE id=?", (*clean.values(), now, order_id))
            for key, value in clean.items():
                if old.get(key) != value:
                    con.execute("INSERT INTO events(order_id,event_type,event_at,source,actor,old_value,new_value) VALUES (?,?,?,?,?,?,?)", (order_id, "Feld geändert", now, source, source, str(old.get(key) or ""), str(value or "")))
            return order_id
        cols = list(clean) + ["imported_at", "created_at", "updated_at"]
        vals = list(clean.values()) + ([now if source != "Manuell" else None, now, now])
        cur = con.execute(f"INSERT INTO orders({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})", vals)
        oid = int(cur.lastrowid)
        con.execute("INSERT INTO events(order_id,event_type,event_at,source,actor,new_value) VALUES (?,?,?,?,?,?)", (oid, "Bestellung angelegt", now, source, source, clean["status"]))
        for field, label in TIMELINE:
            if clean.get(field): con.execute("INSERT INTO events(order_id,event_type,event_at,source,actor,new_value) VALUES (?,?,?,?,?,?)", (oid, label, clean[field], source, source, clean[field]))
        return oid


def list_orders(db: Database, filters: dict[str, str] | None = None, unit: str = "workdays") -> list[dict[str, Any]]:
    filters = filters or {}
    where, params = [], []
    if filters.get("location"): where.append("l.code=?"); params.append(filters["location"])
    if filters.get("status"): where.append("o.status=?"); params.append(filters["status"])
    if filters.get("carrier"): where.append("o.carrier=?"); params.append(filters["carrier"])
    if filters.get("open") == "1": where.append("o.received_at IS NULL AND o.status <> 'storniert'")
    if filters.get("from"): where.append("date(o.order_at)>=date(?)"); params.append(filters["from"])
    if filters.get("to"): where.append("date(o.order_at)<=date(?)"); params.append(filters["to"])
    if filters.get("q"):
        where.append("(o.tracking_id LIKE ? OR o.at_sales_order_no LIKE ? OR o.external_document_no LIKE ?)")
        params.extend([f"%{filters['q']}%"] * 3)
    sql = """SELECT o.*,l.code location_code,l.name location_name,l.sla_order_ready,l.sla_total,l.standard_transport_days,
             d.name delay_reason FROM orders o JOIN locations l ON l.id=o.location_id
             LEFT JOIN delay_reasons d ON d.id=o.delay_reason_id"""
    if where: sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY COALESCE(o.created_at_at,o.order_at) DESC"
    items = [enrich_order(r, unit) for r in db.all(sql, tuple(params))]
    cfg = {r["key"]: r["value"] for r in db.all("SELECT key,value FROM settings")}
    for item in items:
        warnings: list[str] = []
        no_pick = float(cfg.get("warning_no_pick_days", 3))
        idle = float(cfg.get("warning_pick_idle_days", 2))
        ready_wait = float(cfg.get("warning_ready_pickup_days", 2))
        now = datetime.now(timezone.utc)
        if item.get("released_at") and not item.get("pick_created_at") and (duration(item["released_at"], now, "workdays") or 0) > no_pick: warnings.append("Seit mehr als Zielwert ohne Pick")
        if item.get("pick_created_at") and not item.get("pick_started_at") and (duration(item["pick_created_at"], now, "workdays") or 0) > idle: warnings.append("Pick erstellt, aber nicht begonnen")
        if item.get("pick_started_at") and not item.get("pick_registered_at") and (duration(item["pick_started_at"], now, "workdays") or 0) > idle: warnings.append("Pick begonnen, aber nicht abgeschlossen")
        if item.get("pick_registered_at") and not item.get("ready_at") and (duration(item["pick_registered_at"], now, "workdays") or 0) > idle: warnings.append("Pick abgeschlossen, aber nicht abholbereit")
        if item.get("ready_at") and not item.get("picked_up_at") and (duration(item["ready_at"], now, "workdays") or 0) > ready_wait: warnings.append("Abholbereit, aber nicht abgeholt")
        if item.get("picked_up_at") and not item.get("received_at") and (duration(item["picked_up_at"], now, "workdays") or 0) > (item.get("standard_transport_days") or 9999): warnings.append("Unterwegs länger als Standardtransportzeit")
        item["warnings"] = warnings
    if filters.get("sla"): items = [x for x in items if x["sla_state"] == filters["sla"]]
    if filters.get("quality") == "1": items = [x for x in items if x["quality_issues"]]
    return items


def dashboard(db: Database, filters: dict[str, str] | None = None, unit: str = "workdays") -> dict[str, Any]:
    orders = list_orders(db, filters, unit)
    completed = [o for o in orders if o.get("received_at")]
    open_orders = [o for o in orders if not o.get("received_at") and o.get("status") != "storniert"]
    phase_stats = {}
    for key, (_, _, label) in PHASES.items():
        vals = [o["durations"][key] for o in completed if o["durations"][key] is not None]
        phase_stats[key] = {"label": label, **stats(vals)}
    locations = {}
    for o in orders:
        loc = locations.setdefault(o["location_code"], {"name": o["location_name"], "orders": [], "reasons": {}})
        loc["orders"].append(o)
        if o.get("delay_reason"): loc["reasons"][o["delay_reason"]] = loc["reasons"].get(o["delay_reason"], 0) + 1
    comparisons = []
    for code, info in locations.items():
        os = info["orders"]
        comparisons.append({"code": code, "name": info["name"], "count": len(os),
            "order_ready": stats([x["durations"]["order_ready"] for x in os if x["durations"]["order_ready"] is not None]),
            "transport": stats([x["durations"]["transport"] for x in os if x["durations"]["transport"] is not None]),
            "total": stats([x["durations"]["total"] for x in os if x["durations"]["total"] is not None]),
            "sla": round(sum(x["sla_state"] == "innerhalb" for x in os) / len(os) * 100, 1),
            "top_reason": max(info["reasons"], key=info["reasons"].get) if info["reasons"] else "–"})
    oldest = max((o["open_age"] or 0 for o in open_orders), default=0)
    overdue = sum(o["sla_state"] == "überschritten" for o in open_orders)
    sla_known = [o for o in orders if o["sla_state"] != "unbekannt"]
    monthly: dict[str, int] = {}
    reasons: dict[str, int] = {}
    for order in orders:
        parsed = parse_dt(order.get("order_at"))
        if parsed: monthly[parsed.strftime("%Y-%m")] = monthly.get(parsed.strftime("%Y-%m"), 0) + 1
        if order.get("delay_reason"): reasons[order["delay_reason"]] = reasons.get(order["delay_reason"], 0) + 1
    trend = [{"label": parse_dt(o["order_at"]).strftime("%d.%m") if parse_dt(o.get("order_at")) else "–", "ready": o["durations"]["order_ready"], "transport": o["durations"]["transport"]} for o in sorted(completed, key=lambda x: x.get("order_at") or "")]
    med_ready = phase_stats["order_ready"]["median"] or 0
    med_transport = phase_stats["transport"]["median"] or 0
    return {"orders": orders, "completed": completed, "open": open_orders, "open_count": len(open_orders),
        "overdue": overdue, "oldest": oldest, "phase_stats": phase_stats, "locations": comparisons,
        "median_ready": phase_stats["order_ready"]["median"], "median_transport": phase_stats["transport"]["median"],
        "median_total": phase_stats["total"]["median"], "sla_rate": round(sum(o["sla_state"] == "innerhalb" for o in sla_known) / len(sla_known) * 100, 1) if sla_known else None,
        "monthly": [{"label": k, "count": v} for k, v in sorted(monthly.items())],
        "reasons": sorted(({"label": k, "count": v} for k, v in reasons.items()), key=lambda x: x["count"], reverse=True),
        "trend": trend, "internal_share": round(med_ready / (med_ready + med_transport) * 100, 1) if med_ready + med_transport else 0}


def create_backup(db: Database, backup_dir: Path, reason: str = "Manuell") -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"tracker-{datetime.now():%Y%m%d-%H%M%S-%f}.sqlite3"
    with db.connect() as src, sqlite3.connect(target) as dest: src.backup(dest)
    with db.transaction() as con:
        con.execute("INSERT INTO backups(filename,created_at,size_bytes,reason) VALUES (?,?,?,?)", (target.name, utcnow(), target.stat().st_size, reason))
    return target


def restore_backup(db: Database, backup: Path, backup_dir: Path) -> None:
    if not backup.exists(): raise ValueError("Sicherungsdatei nicht gefunden.")
    test = sqlite3.connect(backup)
    try:
        if test.execute("PRAGMA integrity_check").fetchone()[0] != "ok": raise ValueError("Sicherung ist beschädigt.")
        if not test.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='orders'").fetchone(): raise ValueError("Keine gültige Tracker-Datenbank.")
    finally: test.close()
    create_backup(db, backup_dir, "Automatisch vor Wiederherstellung")
    shutil.copy2(backup, db.path)


def seed_demo(db: Database) -> None:
    if db.scalar("SELECT COUNT(*) FROM orders"):
        return
    ids = {r["code"]: r["id"] for r in db.all("SELECT id,code FROM locations")}
    reasons = {r["name"]: r["id"] for r in db.all("SELECT id,name FROM delay_reasons")}
    base = datetime.now(timezone.utc).replace(hour=8, minute=0, second=0, microsecond=0)
    def iso(days: float) -> str: return (base + timedelta(days=days)).isoformat()
    samples = [
      dict(tracking_id="CH-2026-001", warehouse_order_no="CH-PO-1001", at_sales_order_no="AT-SO-5001", external_document_no="EXT-CH-01", location_id=ids["CH"], order_at=iso(-30), created_at_at=iso(-30), released_at=iso(-29), pick_created_at=iso(-27), pick_started_at=iso(-26), pick_registered_at=iso(-24), packed_at=iso(-23), documents_complete_at=iso(-22), ready_at=iso(-21), picked_up_at=iso(-19), received_at=iso(-16), line_count=18,total_quantity=340,pallet_count=4,total_weight=1280,order_value=28500,carrier="Gebrüder Weiss",transport_mode="Strasse",priority="normal",responsible="Logistik AT",delay_reason_id=reasons["Abholung verschoben"],notes="14 Kalendertage Gesamtlaufzeit",data_source="Beispieldaten"),
      dict(tracking_id="CH-2026-002", warehouse_order_no="CH-PO-1002", at_sales_order_no="AT-SO-5002", external_document_no="EXT-CH-02", location_id=ids["CH"], order_at=iso(-20), created_at_at=iso(-20), released_at=iso(-19), pick_created_at=iso(-18), pick_started_at=iso(-18), pick_registered_at=iso(-16), packed_at=iso(-15), documents_complete_at=iso(-15), ready_at=iso(-15), picked_up_at=iso(-14), received_at=iso(-12), line_count=9,total_quantity=110,pallet_count=2,total_weight=540,order_value=12000,carrier="DHL Freight",transport_mode="Strasse",priority="hoch",responsible="Logistik AT",notes="8 Kalendertage",data_source="Beispieldaten"),
      dict(tracking_id="UK-2026-001", warehouse_order_no="UK-PO-7001", at_sales_order_no="AT-SO-5003", external_document_no="EXT-UK-01", location_id=ids["UK"], order_at=iso(-45), created_at_at=iso(-45), released_at=iso(-43), pick_created_at=iso(-40), pick_started_at=iso(-39), pick_registered_at=iso(-37), packed_at=iso(-36), documents_complete_at=iso(-35), ready_at=iso(-35), picked_up_at=iso(-34), received_at=iso(-21), line_count=32,total_quantity=780,pallet_count=8,total_weight=3200,order_value=67000,carrier="DB Schenker",transport_mode="Strasse/Fähre",priority="normal",responsible="Logistik AT",delay_reason_id=reasons["Transportverzögerung"],data_source="Beispieldaten"),
      dict(tracking_id="CH-2026-OPEN", warehouse_order_no="CH-PO-1003", at_sales_order_no="AT-SO-5004", external_document_no="EXT-CH-03", location_id=ids["CH"], order_at=iso(-18), created_at_at=iso(-18), released_at=iso(-17), pick_created_at=iso(-15), pick_started_at=None,pick_registered_at=None,packed_at=None,documents_complete_at=None,ready_at=None,picked_up_at=None,received_at=None,line_count=15,total_quantity=220,pallet_count=3,total_weight=810,order_value=19000,carrier="DHL Freight",transport_mode="Strasse",priority="kritisch",responsible="Logistik AT",delay_reason_id=reasons["fehlende Ware"],data_source="Beispieldaten"),
      dict(tracking_id="US-2026-INCOMPLETE", warehouse_order_no="US-PO-301", at_sales_order_no="AT-SO-5005", external_document_no=None, location_id=ids["US"], order_at=iso(-9), created_at_at=iso(-9), released_at=None,pick_created_at=None,pick_started_at=None,pick_registered_at=None,packed_at=None,documents_complete_at=None,ready_at=None,picked_up_at=None,received_at=None,line_count=4,total_quantity=40,pallet_count=None,total_weight=None,order_value=4000,carrier=None,transport_mode="Seefracht",priority="normal",responsible=None,delay_reason_id=reasons["unbekannt"],data_source="Beispieldaten"),
      dict(tracking_id="CH-2026-ERROR", warehouse_order_no="CH-PO-1004", at_sales_order_no="AT-SO-5006", external_document_no="EXT-CH-04", location_id=ids["CH"], order_at=iso(-10), created_at_at=iso(-10), released_at=iso(-9), pick_created_at=iso(-8), pick_started_at=iso(-7), pick_registered_at=iso(-8),packed_at=None,documents_complete_at=None,ready_at=None,picked_up_at=None,received_at=None,line_count=2,total_quantity=12,pallet_count=1,total_weight=80,order_value=900,carrier="Unbekannt",transport_mode="Strasse",priority="normal",responsible="Logistik AT",delay_reason_id=reasons["unbekannt"],data_source="Beispieldaten"),
      dict(tracking_id="UK-2026-PICKUP", warehouse_order_no="UK-PO-7002", at_sales_order_no="AT-SO-5007", external_document_no="EXT-UK-02", location_id=ids["UK"], order_at=iso(-14), created_at_at=iso(-14), released_at=iso(-13), pick_created_at=iso(-12), pick_started_at=iso(-11), pick_registered_at=iso(-9),packed_at=iso(-8),documents_complete_at=iso(-8),ready_at=iso(-8),picked_up_at=iso(-3),received_at=None,line_count=11,total_quantity=190,pallet_count=2,total_weight=700,order_value=16500,carrier="DB Schenker",transport_mode="Strasse/Fähre",priority="hoch",responsible="Logistik AT",delay_reason_id=reasons["Abholung verschoben"],data_source="Beispieldaten"),
    ]
    for sample in samples: save_order(db, sample, source="Beispieldaten")
