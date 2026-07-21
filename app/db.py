from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy import create_engine


ORDER_FIELDS = [
    "tracking_id", "warehouse_order_no", "at_sales_order_no", "external_document_no",
    "location_id", "order_at", "created_at_at", "released_at", "pick_created_at",
    "pick_started_at", "pick_registered_at", "packed_at", "documents_complete_at",
    "ready_at", "picked_up_at", "shipment_posted_at", "received_at", "line_count",
    "total_quantity", "pallet_count", "total_weight", "order_value", "carrier",
    "transport_mode", "status", "priority", "responsible", "delay_reason_id", "notes",
    "data_source",
]

TIMESTAMP_FIELDS = [
    "order_at", "created_at_at", "released_at", "pick_created_at", "pick_started_at",
    "pick_registered_at", "packed_at", "documents_complete_at", "ready_at",
    "picked_up_at", "shipment_posted_at", "received_at",
]

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS locations (
 id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE COLLATE NOCASE, name TEXT NOT NULL,
 country TEXT NOT NULL, type TEXT NOT NULL DEFAULT 'Aussenlager', active INTEGER NOT NULL DEFAULT 1,
 standard_transport_days REAL, sla_order_release REAL, sla_release_pick REAL,
 sla_pick_cycle REAL, sla_pack_ready REAL, sla_ready_pickup REAL,
 sla_order_ready REAL, sla_total REAL, notes TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS delay_reasons (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE COLLATE NOCASE, category TEXT NOT NULL DEFAULT 'intern', active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS orders (
 id INTEGER PRIMARY KEY, tracking_id TEXT NOT NULL UNIQUE COLLATE NOCASE,
 warehouse_order_no TEXT, at_sales_order_no TEXT, external_document_no TEXT,
 location_id INTEGER NOT NULL REFERENCES locations(id),
 order_at TEXT NOT NULL, created_at_at TEXT, released_at TEXT, pick_created_at TEXT,
 pick_started_at TEXT, pick_registered_at TEXT, packed_at TEXT, documents_complete_at TEXT,
 ready_at TEXT, picked_up_at TEXT, shipment_posted_at TEXT, received_at TEXT,
 line_count INTEGER, total_quantity REAL, pallet_count INTEGER, total_weight REAL,
 order_value REAL, carrier TEXT, transport_mode TEXT, status TEXT NOT NULL DEFAULT 'neu',
 priority TEXT NOT NULL DEFAULT 'normal', responsible TEXT, delay_reason_id INTEGER REFERENCES delay_reasons(id),
 notes TEXT, data_source TEXT NOT NULL DEFAULT 'Manuell', imported_at TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_orders_wh_no ON orders(warehouse_order_no) WHERE warehouse_order_no IS NOT NULL AND warehouse_order_no <> '';
CREATE UNIQUE INDEX IF NOT EXISTS ux_orders_at_no ON orders(at_sales_order_no) WHERE at_sales_order_no IS NOT NULL AND at_sales_order_no <> '';
CREATE INDEX IF NOT EXISTS ix_orders_location ON orders(location_id);
CREATE INDEX IF NOT EXISTS ix_orders_status ON orders(status);
CREATE TABLE IF NOT EXISTS events (
 id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
 event_type TEXT NOT NULL, event_at TEXT NOT NULL, source TEXT NOT NULL,
 actor TEXT, notes TEXT, old_value TEXT, new_value TEXT
);
CREATE TABLE IF NOT EXISTS import_logs (
 id INTEGER PRIMARY KEY, filename TEXT NOT NULL, file_type TEXT NOT NULL, imported_at TEXT NOT NULL,
 rows_read INTEGER DEFAULT 0, rows_new INTEGER DEFAULT 0, rows_updated INTEGER DEFAULT 0,
 rows_skipped INTEGER DEFAULT 0, errors TEXT DEFAULT '[]', warnings TEXT DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS import_profiles (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, file_type TEXT NOT NULL,
 sheet_name TEXT, header_row INTEGER DEFAULT 1, mapping_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS backups (id INTEGER PRIMARY KEY, filename TEXT NOT NULL, created_at TEXT NOT NULL, size_bytes INTEGER NOT NULL, reason TEXT);
"""

POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS locations (
 id BIGSERIAL PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL, country TEXT NOT NULL,
 type TEXT NOT NULL DEFAULT 'Aussenlager', active INTEGER NOT NULL DEFAULT 1,
 standard_transport_days DOUBLE PRECISION, sla_order_release DOUBLE PRECISION,
 sla_release_pick DOUBLE PRECISION, sla_pick_cycle DOUBLE PRECISION, sla_pack_ready DOUBLE PRECISION,
 sla_ready_pickup DOUBLE PRECISION, sla_order_ready DOUBLE PRECISION, sla_total DOUBLE PRECISION, notes TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS delay_reasons (
 id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL UNIQUE, category TEXT NOT NULL DEFAULT 'intern', active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS orders (
 id BIGSERIAL PRIMARY KEY, tracking_id TEXT NOT NULL UNIQUE, warehouse_order_no TEXT,
 at_sales_order_no TEXT, external_document_no TEXT, location_id BIGINT NOT NULL REFERENCES locations(id),
 order_at TIMESTAMPTZ NOT NULL, created_at_at TIMESTAMPTZ, released_at TIMESTAMPTZ,
 pick_created_at TIMESTAMPTZ, pick_started_at TIMESTAMPTZ, pick_registered_at TIMESTAMPTZ,
 packed_at TIMESTAMPTZ, documents_complete_at TIMESTAMPTZ, ready_at TIMESTAMPTZ,
 picked_up_at TIMESTAMPTZ, shipment_posted_at TIMESTAMPTZ, received_at TIMESTAMPTZ,
 line_count INTEGER, total_quantity DOUBLE PRECISION, pallet_count INTEGER, total_weight DOUBLE PRECISION,
 order_value DOUBLE PRECISION, carrier TEXT, transport_mode TEXT, status TEXT NOT NULL DEFAULT 'neu',
 priority TEXT NOT NULL DEFAULT 'normal', responsible TEXT, delay_reason_id BIGINT REFERENCES delay_reasons(id),
 notes TEXT, data_source TEXT NOT NULL DEFAULT 'Manuell', imported_at TIMESTAMPTZ,
 created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_orders_tracking_lower ON orders(LOWER(tracking_id));
CREATE UNIQUE INDEX IF NOT EXISTS ux_orders_wh_no_lower ON orders(LOWER(warehouse_order_no)) WHERE warehouse_order_no IS NOT NULL AND warehouse_order_no <> '';
CREATE UNIQUE INDEX IF NOT EXISTS ux_orders_at_no_lower ON orders(LOWER(at_sales_order_no)) WHERE at_sales_order_no IS NOT NULL AND at_sales_order_no <> '';
CREATE INDEX IF NOT EXISTS ix_orders_location ON orders(location_id);
CREATE INDEX IF NOT EXISTS ix_orders_status ON orders(status);
CREATE TABLE IF NOT EXISTS events (
 id BIGSERIAL PRIMARY KEY, order_id BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
 event_type TEXT NOT NULL, event_at TIMESTAMPTZ NOT NULL, source TEXT NOT NULL,
 actor TEXT, notes TEXT, old_value TEXT, new_value TEXT
);
CREATE TABLE IF NOT EXISTS import_logs (
 id BIGSERIAL PRIMARY KEY, filename TEXT NOT NULL, file_type TEXT NOT NULL, imported_at TIMESTAMPTZ NOT NULL,
 rows_read INTEGER DEFAULT 0, rows_new INTEGER DEFAULT 0, rows_updated INTEGER DEFAULT 0,
 rows_skipped INTEGER DEFAULT 0, errors TEXT DEFAULT '[]', warnings TEXT DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS import_profiles (
 id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL UNIQUE, file_type TEXT NOT NULL, sheet_name TEXT,
 header_row INTEGER DEFAULT 1, mapping_json TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TIMESTAMPTZ NOT NULL);
CREATE TABLE IF NOT EXISTS backups (id BIGSERIAL PRIMARY KEY, filename TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL, size_bytes BIGINT NOT NULL, reason TEXT);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA busy_timeout=5000")
        return con

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        con = self.connect()
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def initialize(self) -> None:
        with self.transaction() as con:
            con.executescript(SCHEMA)
            self._seed(con)

    def _seed(self, con: sqlite3.Connection) -> None:
        locations = [
            ("CH", "Schweiz", "Schweiz", 3, 1, 2, 2, 1, 1, 7, 10),
            ("UK", "Vereinigtes Königreich", "Vereinigtes Königreich", 12, 1, 2, 3, 2, 2, 10, 25),
            ("US", "Vereinigte Staaten", "USA", 15, 1, 2, 3, 2, 2, 10, 30),
        ]
        con.executemany("""INSERT OR IGNORE INTO locations
          (code,name,country,standard_transport_days,sla_order_release,sla_release_pick,sla_pick_cycle,
           sla_pack_ready,sla_ready_pickup,sla_order_ready,sla_total) VALUES (?,?,?,?,?,?,?,?,?,?,?)""", locations)
        reasons = [
            ("Auftrag nicht freigegeben", "intern"), ("fehlende Ware", "intern"),
            ("Fehlbestand", "intern"), ("Pick verspätet erstellt", "intern"),
            ("fehlendes Personal", "intern"), ("hohe Auslastung", "intern"),
            ("Verpackung verspätet", "intern"), ("fehlende Rechnung", "dokumente"),
            ("fehlende Zolldokumente", "zoll"), ("fehlende Gewichte", "dokumente"),
            ("Spedition nicht verfügbar", "spedition"), ("Abholung verschoben", "spedition"),
            ("Zollverzögerung", "zoll"), ("Transportverzögerung", "transport"),
            ("Feiertag", "kalender"), ("Wochenende", "kalender"), ("unbekannt", "unbekannt"),
        ]
        con.executemany("INSERT OR IGNORE INTO delay_reasons(name,category) VALUES (?,?)", reasons)
        defaults = {
            "warning_no_pick_days": "3", "warning_pick_idle_days": "2",
            "warning_ready_pickup_days": "2", "display_unit": "workdays",
            "language": "de", "max_upload_mb": "25",
            "connector_config": json.dumps({"system_type": "Datei", "base_url": "", "tenant": "", "environment": "", "company": "", "client_id": "", "scope": "", "api_version": "v2.0"}),
        }
        con.executemany("INSERT OR IGNORE INTO settings(key,value,updated_at) VALUES (?,?,?)", [(k, v, utcnow()) for k, v in defaults.items()])

    def all(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        with self.connect() as con:
            return list(con.execute(sql, params).fetchall())

    def one(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        with self.connect() as con:
            return con.execute(sql, params).fetchone()

    def scalar(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        row = self.one(sql, params)
        return row[0] if row else None

    @property
    def is_sqlite(self) -> bool:
        return True


class CompatRow(dict[str, Any]):
    def __getitem__(self, key: str | int) -> Any:
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class CompatResult:
    def __init__(self, result: Any, lastrowid: int | None = None):
        self.result = result
        self.lastrowid = lastrowid

    @staticmethod
    def _row(row: Any) -> CompatRow | None:
        return CompatRow(dict(row._mapping)) if row is not None else None

    def fetchone(self) -> CompatRow | None:
        return self._row(self.result.fetchone())

    def fetchall(self) -> list[CompatRow]:
        return [self._row(row) for row in self.result.fetchall()]


class PostgresConnection:
    ID_TABLES = {"locations", "delay_reasons", "orders", "events", "import_logs", "import_profiles", "backups"}

    def __init__(self, connection: Any):
        self.connection = connection

    @staticmethod
    def _adapt(sql: str) -> str:
        return sql.replace(" COLLATE NOCASE", "").replace("?", "%s")

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> CompatResult:
        adapted = self._adapt(sql)
        table = ""
        words = adapted.strip().split()
        if len(words) > 2 and words[0].upper() == "INSERT" and words[1].upper() == "INTO":
            table = words[2].split("(")[0].lower()
        wants_id = table in self.ID_TABLES and "RETURNING" not in adapted.upper() and "ON CONFLICT" not in adapted.upper()
        if wants_id:
            adapted += " RETURNING id"
        result = self.connection.exec_driver_sql(adapted, tuple(params))
        lastrowid = result.fetchone()[0] if wants_id else None
        return CompatResult(result, lastrowid)

    def executemany(self, sql: str, params: list[tuple[Any, ...]]) -> CompatResult:
        adapted = self._adapt(sql).replace("INSERT OR IGNORE INTO", "INSERT INTO")
        if "INSERT OR IGNORE" in sql.upper() and "ON CONFLICT" not in adapted.upper():
            adapted += " ON CONFLICT DO NOTHING"
        return CompatResult(self.connection.exec_driver_sql(adapted, params))

    def executescript(self, script: str) -> None:
        for statement in script.split(";"):
            if statement.strip():
                self.connection.exec_driver_sql(statement)

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()

    def close(self) -> None:
        self.connection.close()


class PostgresDatabase:
    """Small compatibility adapter preserving the app's repository API on Supabase Postgres."""

    def __init__(self, url: str):
        self.url = url
        self.path = Path("supabase-postgres")
        self.engine = create_engine(url, pool_pre_ping=True, pool_recycle=300)

    def connect(self) -> PostgresConnection:
        return PostgresConnection(self.engine.connect())

    @contextmanager
    def transaction(self) -> Iterator[PostgresConnection]:
        con = self.connect()
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def initialize(self) -> None:
        with self.transaction() as con:
            con.executescript(POSTGRES_SCHEMA)
            Database._seed(self, con)  # type: ignore[arg-type]

    def all(self, sql: str, params: tuple[Any, ...] = ()) -> list[CompatRow]:
        with self.transaction() as con:
            return con.execute(sql, params).fetchall()

    def one(self, sql: str, params: tuple[Any, ...] = ()) -> CompatRow | None:
        with self.transaction() as con:
            return con.execute(sql, params).fetchone()

    def scalar(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        row = self.one(sql, params)
        return row[0] if row else None

    @property
    def is_sqlite(self) -> bool:
        return False
