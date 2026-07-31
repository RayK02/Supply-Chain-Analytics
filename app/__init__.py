from __future__ import annotations

import os
import secrets
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask

from .auth import SupabaseAuth
from .db import Database, PostgresDatabase
from .services import seed_demo


def create_app(test_config: dict | None = None) -> Flask:
    base = Path(__file__).resolve().parent.parent
    load_dotenv(base / ".env")

    is_vercel = bool(os.environ.get("VERCEL"))
    runtime_root = Path("/tmp/supplychain") if is_vercel else base
    data_dir = runtime_root / "data"
    backup_dir = runtime_root / "backups"
    upload_dir = data_dir / "uploads"
    for directory in (data_dir, backup_dir, upload_dir):
        directory.mkdir(parents=True, exist_ok=True)

    secret_key = os.environ.get("TRACKER_SECRET_KEY")
    if not secret_key:
        secret_key = secrets.token_urlsafe(32) if is_vercel else "local-only-change-me"

    auth_default = "1" if is_vercel else "0"
    secure_cookie_default = "1" if is_vercel else "0"

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=secret_key,
        DATABASE=str(data_dir / "tracker.sqlite3"),
        BACKUP_DIR=str(backup_dir),
        UPLOAD_DIR=str(upload_dir),
        MAX_CONTENT_LENGTH=25 * 1024 * 1024,
        AUTH_REQUIRED=os.environ.get("TRACKER_AUTH_REQUIRED", auth_default) == "1",
        SUPABASE_URL=os.environ.get("SUPABASE_URL", ""),
        SUPABASE_ANON_KEY=os.environ.get("SUPABASE_ANON_KEY", ""),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("TRACKER_SECURE_COOKIES", secure_cookie_default) == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
        IS_VERCEL=is_vercel,
        PERSISTENT_DATABASE=bool(os.environ.get("DATABASE_URL")),
    )
    if test_config:
        app.config.update(test_config)

    database_url = os.environ.get("DATABASE_URL", "")
    if database_url.startswith("postgres://"):
        database_url = "postgresql+psycopg://" + database_url.removeprefix("postgres://")
    elif database_url.startswith("postgresql://"):
        database_url = "postgresql+psycopg://" + database_url.removeprefix("postgresql://")

    app.extensions["db"] = PostgresDatabase(database_url) if database_url else Database(app.config["DATABASE"])
    app.extensions["auth"] = SupabaseAuth(app.config["SUPABASE_URL"], app.config["SUPABASE_ANON_KEY"])
    app.extensions["db"].initialize()

    if not app.config.get("TESTING") and os.environ.get("TRACKER_NO_DEMO") != "1":
        seed_demo(app.extensions["db"])

    from .routes import bp

    app.register_blueprint(bp)
    return app
