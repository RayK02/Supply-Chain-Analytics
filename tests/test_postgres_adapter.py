from app.db import POSTGRES_SCHEMA, PostgresConnection


def test_postgres_schema_is_portable():
    assert "BIGSERIAL" in POSTGRES_SCHEMA
    assert "COLLATE NOCASE" not in POSTGRES_SCHEMA
    assert "TIMESTAMPTZ" in POSTGRES_SCHEMA


def test_postgres_placeholder_adaptation():
    sql = PostgresConnection._adapt("SELECT * FROM orders WHERE LOWER(tracking_id)=LOWER(?)")
    assert sql.endswith("LOWER(%s)")
    assert "?" not in sql
