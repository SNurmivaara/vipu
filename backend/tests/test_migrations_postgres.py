"""Data-transforming migration tests against a populated PostgreSQL database.

SQLite tests skip migration SQL entirely, so these build a legacy schema in a
throwaway PostgreSQL schema, apply migrations up to a historical point, insert
synthetic rows, run the remaining migrations and assert on the transformed data.

Runs only when TEST_POSTGRES_URL points at a disposable PostgreSQL database,
e.g. postgresql+psycopg2://postgres:postgres@localhost:5432/postgres. Each test
works in its own schema, which is dropped afterwards.
"""

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app import migrations
from app.migrations import MIGRATIONS, run_migrations

POSTGRES_URL = os.environ.get("TEST_POSTGRES_URL")

pytestmark = pytest.mark.skipif(
    not POSTGRES_URL, reason="TEST_POSTGRES_URL not set; PostgreSQL tests skipped"
)

# Tables as they existed before migration 001 (only the columns migrations
# read or write, plus the ones later migrations drop).
LEGACY_SCHEMA = """
    CREATE TABLE accounts (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        balance NUMERIC(12,2) NOT NULL DEFAULT 0,
        is_credit BOOLEAN NOT NULL DEFAULT FALSE,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    );
    CREATE TABLE budget_settings (
        id SERIAL PRIMARY KEY,
        current_balance NUMERIC(12,2) NOT NULL DEFAULT 0
    );
    CREATE TABLE income_items (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        amount NUMERIC(12,2) NOT NULL DEFAULT 0
    );
    CREATE TABLE expense_items (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        amount NUMERIC(12,2) NOT NULL DEFAULT 0,
        is_savings_goal BOOLEAN NOT NULL DEFAULT FALSE
    );
    CREATE TABLE networth_groups (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        group_type VARCHAR(20) NOT NULL
    );
    CREATE TABLE networth_categories (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        group_id INTEGER NOT NULL REFERENCES networth_groups(id)
    );
    CREATE TABLE networth_snapshots (
        id SERIAL PRIMARY KEY,
        month INTEGER NOT NULL,
        year INTEGER NOT NULL
    );
    CREATE TABLE networth_entries (
        id SERIAL PRIMARY KEY,
        snapshot_id INTEGER NOT NULL
            REFERENCES networth_snapshots(id) ON DELETE CASCADE,
        category_id INTEGER NOT NULL REFERENCES networth_categories(id),
        amount NUMERIC(12,2) NOT NULL DEFAULT 0
    );
    CREATE TABLE goals (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        goal_type VARCHAR(20) NOT NULL,
        target_value NUMERIC(12,2) NOT NULL,
        category_id INTEGER REFERENCES networth_categories(id),
        target_date TIMESTAMP WITH TIME ZONE,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        tracking_period VARCHAR(20),
        starting_value NUMERIC(12,2)
    );
"""


class Db:
    """A session on an isolated schema, with a way to migrate to a given point."""

    def __init__(self, session: Session, monkeypatch: pytest.MonkeyPatch):
        self.session = session
        self._monkeypatch = monkeypatch

    def migrate_through(self, migration_id: str) -> None:
        """Apply pending migrations up to and including migration_id."""
        ids = [m["id"] for m in MIGRATIONS]
        subset = MIGRATIONS[: ids.index(migration_id) + 1]
        self._monkeypatch.setattr(migrations, "MIGRATIONS", subset)
        run_migrations(self.session)

    def migrate_all(self) -> int:
        self._monkeypatch.setattr(migrations, "MIGRATIONS", MIGRATIONS)
        return run_migrations(self.session)

    def run(self, sql: str, **params):
        result = self.session.execute(text(sql), params)
        self.session.commit()
        return result

    def rows(self, sql: str, **params) -> list:
        return list(self.session.execute(text(sql), params).fetchall())


@pytest.fixture
def db(monkeypatch):
    schema = f"vipu_mig_{uuid.uuid4().hex[:12]}"
    engine = create_engine(
        POSTGRES_URL, connect_args={"options": f"-csearch_path={schema}"}
    )
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    session = Session(engine)
    try:
        session.execute(text(LEGACY_SCHEMA))
        session.commit()
        yield Db(session, monkeypatch)
    finally:
        session.close()
        with create_engine(POSTGRES_URL).begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


def test_all_migrations_apply_and_rerun_is_noop(db):
    assert db.migrate_all() == len(MIGRATIONS)
    recorded = db.rows("SELECT id FROM _migrations ORDER BY id")
    assert [r[0] for r in recorded] == sorted(m["id"] for m in MIGRATIONS)
    assert db.migrate_all() == 0


def test_009_archives_legacy_savings_goal_expenses(db):
    db.migrate_through("008_budget_snapshots")
    db.run("""
        INSERT INTO expense_items (name, amount, is_savings_goal, archived_at)
        VALUES
            ('Rent', 900, FALSE, NULL),
            ('Holiday fund', 100, TRUE, NULL),
            ('Car fund', 50, TRUE, NULL),
            ('Old fund', 25, TRUE, '2020-01-01T00:00:00+00');
    """)

    db.migrate_through("009_financial_roadmap")

    archived = {
        name: archived_at
        for name, archived_at in db.rows("SELECT name, archived_at FROM expense_items")
    }
    assert archived["Rent"] is None
    assert archived["Holiday fund"] is not None
    assert archived["Car fund"] is not None
    # Lines that were already archived keep their original timestamp.
    assert archived["Old fund"].year == 2020


def test_009_reshapes_goals(db):
    db.migrate_through("008_budget_snapshots")
    db.run("""
        INSERT INTO goals (name, goal_type, target_value, created_at) VALUES
            ('Net worth', 'net_worth', 100000, '2024-01-01T00:00:00+00'),
            ('Second', 'savings_goal', 2000, '2024-03-01T00:00:00+00'),
            ('First', 'savings_goal', 1000, '2024-02-01T00:00:00+00'),
            ('Rate', 'savings_rate', 20, '2024-01-01T00:00:00+00'),
            ('Cat rate', 'category_rate', 10, '2024-01-01T00:00:00+00'),
            ('Cat target', 'category_target', 500, '2024-04-01T00:00:00+00');
    """)

    db.migrate_through("009_financial_roadmap")

    goals = {
        name: (goal_type, priority)
        for name, goal_type, priority in db.rows(
            "SELECT name, goal_type, priority FROM goals"
        )
    }
    # savings_rate / category_rate goals are deleted.
    assert set(goals) == {"Net worth", "Second", "First", "Cat target"}
    assert goals["Net worth"] == ("net_worth", None)
    # category_target becomes savings_goal; priorities follow creation order.
    assert goals["First"] == ("savings_goal", 0)
    assert goals["Second"] == ("savings_goal", 1)
    assert goals["Cat target"] == ("savings_goal", 2)


def test_011_pins_day_and_week_schedules_to_a_start_date(db):
    db.migrate_through("010_occurrence_overrides")
    db.run("""
        INSERT INTO expense_items
            (name, amount, due_day, frequency_unit, start_date, is_ephemeral)
        VALUES
            ('Weekly', 10, 15, 'weeks', NULL, FALSE),
            ('Daily', 1, 31, 'days', NULL, FALSE),
            ('Monthly', 20, 5, 'months', NULL, FALSE),
            ('Ephemeral weekly', 5, 10, 'weeks', NULL, TRUE),
            ('Pinned weekly', 7, 10, 'weeks', '2024-01-10', FALSE);
        INSERT INTO income_items
            (name, amount, due_day, frequency_unit, start_date, is_ephemeral)
        VALUES
            ('Biweekly pay', 800, 20, 'weeks', NULL, FALSE),
            ('Salary', 3000, 25, 'months', NULL, FALSE);
    """)

    db.migrate_through("011_anchor_day_week_recurrence")

    expenses = {
        name: start
        for name, start in db.rows("SELECT name, start_date FROM expense_items")
    }
    income = {
        name: start
        for name, start in db.rows("SELECT name, start_date FROM income_items")
    }
    assert expenses["Weekly"] is not None and expenses["Weekly"].day == 15
    # Day 31 clamps to the last day of the current month.
    assert expenses["Daily"] is not None and expenses["Daily"].day >= 28
    assert expenses["Monthly"] is None
    assert expenses["Ephemeral weekly"] is None
    assert str(expenses["Pinned weekly"]) == "2024-01-10"
    assert income["Biweekly pay"] is not None and income["Biweekly pay"].day == 20
    assert income["Salary"] is None


def test_015_rekeys_liability_terms_from_group_to_category(db):
    db.migrate_through("014_swr_excluded_groups")
    db.run("""
        INSERT INTO networth_groups (id, name, group_type) VALUES
            (1, 'Loans', 'liability'),
            (2, 'Stale', 'liability'),
            (3, 'Savings', 'asset');
        INSERT INTO networth_categories (id, name, group_id) VALUES
            (1, 'Mortgage', 1),
            (2, 'Car loan', 1),
            (3, 'Old debt', 2),
            (4, 'Cash', 3);
        INSERT INTO networth_snapshots (id, month, year) VALUES
            (1, 12, 2023),
            (2, 1, 2024);
        INSERT INTO networth_entries (snapshot_id, category_id, amount) VALUES
            (1, 3, -999),
            (2, 1, -600),
            (2, 2, -200),
            (2, 4, 5000);
        INSERT INTO forecasting_settings (liability_terms) VALUES (
            '{"Loans": {"rate_pct": 3, "monthly_payment": 400},
              "Stale": {"rate_pct": 9, "monthly_payment": 50}}'::jsonb
        );
    """)

    db.migrate_through("015_liability_terms_by_category")

    (terms,) = db.rows("SELECT liability_terms FROM forecasting_settings")[0]
    # Terms for a group with no balance in the latest snapshot are dropped.
    assert set(terms) == {"Mortgage", "Car loan"}
    # The group's payment splits pro-rata by balance (600:200), rate inherited.
    assert float(terms["Mortgage"]["monthly_payment"]) == 300.0
    assert float(terms["Car loan"]["monthly_payment"]) == 100.0
    for category in terms.values():
        assert float(category["rate_pct"]) == 3.0
        assert category["schedule"] == "fixed"
