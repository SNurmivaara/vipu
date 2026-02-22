"""Simple database migrations system.

Migrations are applied automatically on application startup.
Each migration runs once and is tracked in the _migrations table.
"""

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# List of migrations in order. Each migration has:
# - id: unique identifier (never change once released)
# - name: human-readable description
# - sql: the SQL to execute
MIGRATIONS: list[dict] = [
    {
        "id": "001_goals_v2",
        "name": "Simplify goal types and remove unused columns",
        "sql": """
            UPDATE goals SET goal_type = 'net_worth'
                WHERE goal_type = 'net_worth_target';
            UPDATE goals SET goal_type = 'savings_goal'
                WHERE goal_type = 'category_target';
            UPDATE goals SET goal_type = 'savings_rate'
                WHERE goal_type = 'category_rate';
            DELETE FROM goals WHERE goal_type = 'category_monthly';
            ALTER TABLE goals DROP COLUMN IF EXISTS tracking_period;
            ALTER TABLE goals DROP COLUMN IF EXISTS starting_value;
        """,
    },
]


def _ensure_migrations_table(session: Session) -> None:
    """Create the migrations tracking table if it doesn't exist."""
    session.execute(text("""
            CREATE TABLE IF NOT EXISTS _migrations (
                id VARCHAR(100) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))
    session.commit()


def _get_applied_migrations(session: Session) -> set[str]:
    """Get the set of already-applied migration IDs."""
    result = session.execute(text("SELECT id FROM _migrations"))
    return {row[0] for row in result.fetchall()}


def _apply_migration(session: Session, migration: dict) -> None:
    """Apply a single migration and record it.

    The migration and its recording are done in a single transaction.
    If any part fails, the entire migration is rolled back.
    """
    migration_id = migration["id"]
    migration_name = migration["name"]

    logger.info(f"Applying migration {migration_id}: {migration_name}")

    try:
        # Execute the migration SQL
        session.execute(text(migration["sql"]))

        # Record that this migration was applied
        session.execute(
            text("INSERT INTO _migrations (id, name) VALUES (:id, :name)"),
            {"id": migration_id, "name": migration_name},
        )
        session.commit()

        logger.info(f"Migration {migration_id} applied successfully")
    except Exception as e:
        session.rollback()
        logger.error(f"Migration {migration_id} failed: {e}")
        raise


def run_migrations(session: Session) -> int:
    """Run all pending migrations.

    Returns the number of migrations applied.
    Migrations only run on PostgreSQL (skipped for SQLite in tests).
    """
    # Skip migrations for SQLite (used in tests)
    dialect = session.bind.dialect.name if session.bind else "unknown"
    if dialect != "postgresql":
        logger.debug(f"Skipping migrations for {dialect} database")
        return 0

    _ensure_migrations_table(session)
    applied = _get_applied_migrations(session)

    count = 0
    for migration in MIGRATIONS:
        if migration["id"] not in applied:
            _apply_migration(session, migration)
            count += 1

    if count > 0:
        logger.info(f"Applied {count} migration(s)")
    else:
        logger.debug("No pending migrations")

    return count
