"""Tests for database migrations system."""

from unittest.mock import MagicMock, patch

import pytest

from app.migrations import (
    MIGRATIONS,
    _apply_migration,
    _get_applied_migrations,
    run_migrations,
)


class TestMigrationSystem:
    """Tests for the migration infrastructure."""

    def test_migration_ids_are_unique(self):
        """All migration IDs must be unique."""
        ids = [m["id"] for m in MIGRATIONS]
        assert len(ids) == len(set(ids)), "Duplicate migration IDs found"

    def test_migrations_have_required_fields(self):
        """Each migration must have id, name, and sql fields."""
        for migration in MIGRATIONS:
            assert "id" in migration, f"Migration missing 'id': {migration}"
            assert "name" in migration, f"Migration missing 'name': {migration}"
            assert "sql" in migration, f"Migration missing 'sql': {migration}"
            assert migration["id"].strip(), "Migration ID cannot be empty"
            assert migration["name"].strip(), "Migration name cannot be empty"
            assert migration["sql"].strip(), "Migration SQL cannot be empty"

    def test_get_applied_migrations_returns_set(self):
        """_get_applied_migrations should return a set of IDs."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("001_test",), ("002_test",)]
        mock_session.execute.return_value = mock_result

        result = _get_applied_migrations(mock_session)

        assert result == {"001_test", "002_test"}

    def test_apply_migration_executes_sql_and_records(self):
        """_apply_migration should execute SQL and record the migration."""
        mock_session = MagicMock()
        migration = {
            "id": "test_migration",
            "name": "Test migration",
            "sql": "UPDATE test SET foo = 'bar';",
        }

        _apply_migration(mock_session, migration)

        # Should have called execute twice (SQL + INSERT)
        assert mock_session.execute.call_count == 2
        # Should have committed
        mock_session.commit.assert_called_once()

    def test_apply_migration_rolls_back_on_error(self):
        """_apply_migration should rollback on error."""
        mock_session = MagicMock()
        mock_session.execute.side_effect = Exception("Database error")
        migration = {
            "id": "test_migration",
            "name": "Test migration",
            "sql": "INVALID SQL;",
        }

        with pytest.raises(Exception):  # noqa: B017
            _apply_migration(mock_session, migration)

        mock_session.rollback.assert_called_once()

    def test_run_migrations_skips_sqlite(self):
        """run_migrations should skip SQLite databases."""
        mock_session = MagicMock()
        mock_bind = MagicMock()
        mock_bind.dialect.name = "sqlite"
        mock_session.bind = mock_bind

        count = run_migrations(mock_session)

        assert count == 0
        # Should not have tried to create migration table
        mock_session.execute.assert_not_called()

    def test_run_migrations_skips_already_applied(self):
        """run_migrations should skip already-applied migrations."""
        mock_session = MagicMock()
        mock_bind = MagicMock()
        mock_bind.dialect.name = "postgresql"
        mock_session.bind = mock_bind

        # Mock _get_applied_migrations to return all migration IDs
        all_ids = {m["id"] for m in MIGRATIONS}

        with patch("app.migrations._get_applied_migrations", return_value=all_ids):
            with patch("app.migrations._ensure_migrations_table"):
                with patch("app.migrations._apply_migration") as mock_apply:
                    count = run_migrations(mock_session)

        assert count == 0
        mock_apply.assert_not_called()

    def test_run_migrations_applies_pending(self):
        """run_migrations should apply pending migrations."""
        if not MIGRATIONS:
            return  # Skip if no migrations defined

        mock_session = MagicMock()
        mock_bind = MagicMock()
        mock_bind.dialect.name = "postgresql"
        mock_session.bind = mock_bind

        # Mock no migrations applied yet
        with patch("app.migrations._get_applied_migrations", return_value=set()):
            with patch("app.migrations._ensure_migrations_table"):
                with patch("app.migrations._apply_migration") as mock_apply:
                    count = run_migrations(mock_session)

        assert count == len(MIGRATIONS)
        assert mock_apply.call_count == len(MIGRATIONS)

    def test_run_migrations_is_idempotent(self):
        """Running migrations twice should only apply each once."""
        mock_session = MagicMock()
        mock_bind = MagicMock()
        mock_bind.dialect.name = "postgresql"
        mock_session.bind = mock_bind

        applied = set()

        def mock_get_applied(_):
            return applied.copy()

        def mock_apply(_, migration):
            applied.add(migration["id"])

        with patch(
            "app.migrations._get_applied_migrations", side_effect=mock_get_applied
        ):
            with patch("app.migrations._ensure_migrations_table"):
                with patch("app.migrations._apply_migration", side_effect=mock_apply):
                    # First run
                    count1 = run_migrations(mock_session)
                    # Second run
                    count2 = run_migrations(mock_session)

        assert count1 == len(MIGRATIONS)
        assert count2 == 0  # Nothing to apply on second run
