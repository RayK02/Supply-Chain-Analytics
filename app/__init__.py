from __future__ import annotations

import os
from pathlib import Path

from flask import Flask

from .db import Database, PostgresDatabase
from .services import seed_demo


def create_app(test_config: dict | None = None) -> Flask:
    base = Path(__file__).resolve().parent.parent
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("TRACKER_SECRET_KEY", "local-only-change-me"),
        DATABASE=str(base / "data" / "tracker.sqlite3"), BACKUP_DIR=str(base / "backups"),
        UPLOAD_DIR=str(base / "data" / "uploads"), MAX_CONTENT_LENGTH=25 * 1024 * 1024,
    )
    if test_config: app.config.update(test_config)
    Path(app.config["UPLOAD_DIR"]).mkdir(parents=True, exist_ok=True)
    database_url = os.environ.get("DATABASE_URL", "")
    if database_url.startswith("postgres://"):
        database_url = "postgresql+psycopg://" + database_url.removeprefix("postgres://")
    elif database_url.startswith("postgresql://"):
        database_url = "postgresql+psycopg://" + database_url.removeprefix("postgresql://")
    app.extensions["db"] = PostgresDatabase(database_url) if database_url else Database(app.config["DATABASE"])
    app.extensions["db"].initialize()
    if not app.config.get("TESTING") and os.environ.get("TRACKER_NO_DEMO") != "1": seed_demo(app.extensions["db"])
    from .routes import bp
    app.register_blueprint(bp)
    return app
