"""Application startup against PostgreSQL.

Runs only when TEST_POSTGRES_URL points at a disposable PostgreSQL database
(see test_migrations_postgres.py). The app starts in a throwaway schema. Use a
plain postgresql:// URL so the app starts on SQLAlchemy's default driver, as in
production.
"""

import os
import uuid

import pytest
from sqlalchemy import create_engine, text

import app as app_module
from app import create_app
from app.config import TestingConfig

POSTGRES_URL = os.environ.get("TEST_POSTGRES_URL")

pytestmark = pytest.mark.skipif(
    not POSTGRES_URL, reason="TEST_POSTGRES_URL not set; PostgreSQL tests skipped"
)


@pytest.fixture
def schema_url():
    assert POSTGRES_URL is not None
    schema = f"vipu_app_{uuid.uuid4().hex[:12]}"
    admin = create_engine(POSTGRES_URL)
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        separator = "&" if "?" in POSTGRES_URL else "?"
        yield f"{POSTGRES_URL}{separator}options=-csearch_path%3D{schema}"
    finally:
        if app_module.engine is not None:
            app_module.engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_startup_leaves_no_pooled_connection_for_forked_workers(schema_url):
    class Config(TestingConfig):
        SQLALCHEMY_DATABASE_URI = schema_url

    app = create_app(Config)

    # gunicorn --preload forks here; an inherited pooled connection would be
    # shared by every worker and corrupt each other's queries.
    assert app_module.engine.pool.checkedin() == 0

    with app.test_client() as client:
        assert client.get("/api/budget/current").status_code == 200
