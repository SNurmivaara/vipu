"""Verify startup migrations and rerun behavior on a disposable PostgreSQL DB.

Run via stdin in the backend container; do not call create_app here, because
that would apply missing migrations and hide a startup regression.
"""

import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.migrations import MIGRATIONS, run_migrations

engine = create_engine(os.environ["DATABASE_URL"])
assert engine.dialect.name == "postgresql", "This check requires PostgreSQL"
registered = {migration["id"] for migration in MIGRATIONS}
assert len(registered) == len(MIGRATIONS), "Duplicate migration IDs"

with Session(engine) as session:
    query = text("SELECT id, name, applied_at FROM _migrations ORDER BY id")
    before = session.execute(query).all()
    recorded = {row.id for row in before}
    assert recorded == registered, (
        f"Migration records differ: missing={registered - recorded}, "
        f"unexpected={recorded - registered}"
    )
    applied = run_migrations(session)
    assert applied == 0, f"Repeat run applied {applied} migrations"
    after = session.execute(query).all()
    assert after == before, "Repeat run changed migration records"

print(f"Verified {len(registered)} startup migrations; repeat run applied zero")
