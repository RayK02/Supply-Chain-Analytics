from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import create_app


@pytest.fixture()
def app(tmp_path):
    app = create_app({"TESTING": True, "AUTH_REQUIRED": False, "SECRET_KEY": "test", "DATABASE": str(tmp_path / "test.sqlite3"), "BACKUP_DIR": str(tmp_path / "backups"), "UPLOAD_DIR": str(tmp_path / "uploads")})
    return app


@pytest.fixture()
def client(app): return app.test_client()
