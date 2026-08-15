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
    {
        "id": "002_deadlines_settings",
        "name": "Add payday_day to budget_settings",
        "sql": """
            ALTER TABLE budget_settings
                ADD COLUMN IF NOT EXISTS payday_day INTEGER DEFAULT 25;
        """,
    },
    {
        "id": "003_deadlines_income",
        "name": "Add deadline fields to income_items",
        "sql": """
            ALTER TABLE income_items
                ADD COLUMN IF NOT EXISTS due_day INTEGER DEFAULT 1;
            ALTER TABLE income_items
                ADD COLUMN IF NOT EXISTS frequency_value INTEGER DEFAULT 1;
            ALTER TABLE income_items
                ADD COLUMN IF NOT EXISTS frequency_unit VARCHAR(20) DEFAULT 'months';
            ALTER TABLE income_items
                ADD COLUMN IF NOT EXISTS start_date DATE;
            ALTER TABLE income_items
                ADD COLUMN IF NOT EXISTS end_date DATE;
            ALTER TABLE income_items
                ADD COLUMN IF NOT EXISTS is_ephemeral BOOLEAN DEFAULT FALSE;
            ALTER TABLE income_items
                ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP WITH TIME ZONE;
        """,
    },
    {
        "id": "004_deadlines_expenses",
        "name": "Add deadline fields to expense_items",
        "sql": """
            ALTER TABLE expense_items
                ADD COLUMN IF NOT EXISTS due_day INTEGER DEFAULT 1;
            ALTER TABLE expense_items
                ADD COLUMN IF NOT EXISTS frequency_value INTEGER DEFAULT 1;
            ALTER TABLE expense_items
                ADD COLUMN IF NOT EXISTS frequency_unit VARCHAR(20) DEFAULT 'months';
            ALTER TABLE expense_items
                ADD COLUMN IF NOT EXISTS start_date DATE;
            ALTER TABLE expense_items
                ADD COLUMN IF NOT EXISTS end_date DATE;
            ALTER TABLE expense_items
                ADD COLUMN IF NOT EXISTS is_ephemeral BOOLEAN DEFAULT FALSE;
            ALTER TABLE expense_items
                ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP WITH TIME ZONE;
        """,
    },
    {
        "id": "005_deadlines_accounts",
        "name": "Add payment_due_day to accounts for credit cards",
        "sql": """
            ALTER TABLE accounts
                ADD COLUMN IF NOT EXISTS payment_due_day INTEGER;
        """,
    },
    {
        "id": "006_forecasting_settings",
        "name": "Create forecasting_settings table for FIRE calculations",
        "sql": """
            CREATE TABLE IF NOT EXISTS forecasting_settings (
                id SERIAL PRIMARY KEY,
                inflation_pct NUMERIC(5,2) NOT NULL DEFAULT 2.0,
                safe_withdrawal_rate NUMERIC(5,2) NOT NULL DEFAULT 4.0,
                current_age INTEGER NOT NULL DEFAULT 30,
                target_retirement_age INTEGER NOT NULL DEFAULT 65,
                monthly_savings_override NUMERIC(12,2),
                annual_expenses_override NUMERIC(12,2),
                pension_accrued_monthly NUMERIC(12,2),
                pension_monthly_salary_override NUMERIC(12,2),
                pension_accrual_rate NUMERIC(5,2) NOT NULL DEFAULT 1.5,
                pension_full_age INTEGER NOT NULL DEFAULT 68,
                life_expectancy INTEGER NOT NULL DEFAULT 95,
                group_return_rates JSONB NOT NULL DEFAULT '{}',
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            );
        """,
    },
    {
        "id": "007_pension_guarantee",
        "name": "Add pension guarantee (takuuelake) fields to forecasting_settings",
        "sql": """
            ALTER TABLE forecasting_settings
                ADD COLUMN IF NOT EXISTS
                pension_guarantee_enabled
                BOOLEAN NOT NULL DEFAULT FALSE;
            ALTER TABLE forecasting_settings
                ADD COLUMN IF NOT EXISTS
                pension_guarantee_amount
                NUMERIC(12,2) NOT NULL DEFAULT 990.0;
        """,
    },
    {
        "id": "008_budget_snapshots",
        "name": "Create budget snapshot tables for tracking budget over time",
        "sql": """
            CREATE TABLE IF NOT EXISTS budget_snapshots (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL,
                timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                current_balance NUMERIC(12,2) NOT NULL DEFAULT 0,
                change_from_previous NUMERIC(12,2) NOT NULL DEFAULT 0,
                notes VARCHAR(500),
                CONSTRAINT uq_budget_snapshot_date UNIQUE (date)
            );

            CREATE INDEX IF NOT EXISTS ix_budget_snapshots_date
                ON budget_snapshots (date);

            CREATE TABLE IF NOT EXISTS budget_balance_entries (
                id SERIAL PRIMARY KEY,
                snapshot_id INTEGER NOT NULL
                    REFERENCES budget_snapshots(id) ON DELETE CASCADE,
                account_id INTEGER
                    REFERENCES accounts(id) ON DELETE SET NULL,
                account_name VARCHAR(100) NOT NULL,
                balance NUMERIC(12,2) NOT NULL DEFAULT 0,
                is_credit BOOLEAN NOT NULL DEFAULT FALSE,
                CONSTRAINT uq_budget_entry_snapshot_account
                    UNIQUE (snapshot_id, account_id)
            );
        """,
    },
    {
        "id": "009_financial_roadmap",
        "name": "Sequential roadmap: goal priority/current_amount, drop savings_rate, "
        "retire savings-goal expense lines",
        "sql": """
            ALTER TABLE goals
                ADD COLUMN IF NOT EXISTS priority INTEGER;
            ALTER TABLE goals
                ADD COLUMN IF NOT EXISTS current_amount NUMERIC(12,2);
            DELETE FROM goals WHERE goal_type IN ('savings_rate', 'category_rate');
            UPDATE goals SET goal_type = 'savings_goal'
                WHERE goal_type = 'category_target';
            UPDATE goals g SET priority = sub.rn - 1
                FROM (
                    SELECT id, ROW_NUMBER() OVER (ORDER BY created_at) AS rn
                    FROM goals WHERE goal_type = 'savings_goal'
                ) sub
                WHERE g.id = sub.id;
            UPDATE expense_items SET archived_at = NOW()
                WHERE is_savings_goal = TRUE AND archived_at IS NULL;
        """,
    },
    {
        "id": "010_occurrence_overrides",
        "name": "Add settled/pending occurrence overrides to income and expenses",
        "sql": """
            ALTER TABLE income_items
                ADD COLUMN IF NOT EXISTS settled_occurrence DATE;
            ALTER TABLE income_items
                ADD COLUMN IF NOT EXISTS pending_occurrence DATE;
            ALTER TABLE expense_items
                ADD COLUMN IF NOT EXISTS settled_occurrence DATE;
            ALTER TABLE expense_items
                ADD COLUMN IF NOT EXISTS pending_occurrence DATE;
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
