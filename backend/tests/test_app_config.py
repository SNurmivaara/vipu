"""Tests for app/engine configuration (issues #55 and #147)."""

from sqlalchemy import create_engine

from app import POOL_RECYCLE_SECONDS, build_engine_options


class TestEngineOptions:
    """Engine pool options recover from dropped idle connections."""

    def test_postgres_enables_pre_ping_and_recycle(self):
        opts = build_engine_options("postgresql://vipu:vipu@db:5432/vipu")
        assert opts["pool_pre_ping"] is True
        assert opts["pool_recycle"] == POOL_RECYCLE_SECONDS

    def test_sqlite_uses_no_pool_options(self):
        # SQLite has its own pooling; pre-ping/recycle don't apply.
        assert build_engine_options("sqlite:///:memory:") == {}
        assert build_engine_options("sqlite:////tmp/vipu.db") == {}


class TestPostgresDriver:
    """Plain postgresql:// URLs, as deployments use, resolve to an installed driver."""

    def test_plain_url_uses_psycopg(self):
        # Fails with ModuleNotFoundError if the default driver is not installed.
        engine = create_engine("postgresql://u:p@localhost/db")
        try:
            assert engine.dialect.driver == "psycopg"
        finally:
            engine.dispose()
