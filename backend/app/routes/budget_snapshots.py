from datetime import date
from decimal import Decimal

from apiflask import APIBlueprint
from flask import Response, jsonify, request

from app import get_session
from app.deadline_calc import normalize_day
from app.models import (
    Account,
    BudgetBalanceEntry,
    BudgetSettings,
    BudgetSnapshot,
)

bp = APIBlueprint("budget_snapshots", __name__, tag="Budget Snapshots")


def _get_pay_period_start(d: date, payday_day: int) -> date:
    """Get the start date of the pay period containing date `d`.

    The pay period starts on payday_day (inclusive) and runs until the
    day before the next payday_day.  A snapshot on payday_day belongs
    to the NEW period that starts that day.
    """
    actual_day = normalize_day(payday_day, d.year, d.month)
    if d.day >= actual_day:
        # On or after payday this month → period started this month
        return date(d.year, d.month, actual_day)
    else:
        # Before payday → period started last month
        if d.month == 1:
            prev_month, prev_year = 12, d.year - 1
        else:
            prev_month, prev_year = d.month - 1, d.year
        actual_prev_day = normalize_day(payday_day, prev_year, prev_month)
        return date(prev_year, prev_month, actual_prev_day)


@bp.post("/api/budget/snapshots")
def create_budget_snapshot() -> tuple[Response, int] | Response:
    """Create or update a budget snapshot for today.

    Captures current account balances and the net change from the
    previous snapshot.  If a snapshot already exists for today it is
    overwritten.
    """
    session = get_session()

    data = request.get_json(silent=True) or {}
    notes = data.get("notes")
    if notes is not None:
        notes = str(notes)[:500]

    accounts: list[Account] = (
        session.query(Account).order_by(Account.name).all()
    )
    current_balance = sum((a.balance for a in accounts), Decimal("0"))

    today = date.today()

    # Check for existing snapshot today
    existing = (
        session.query(BudgetSnapshot)
        .filter(BudgetSnapshot.date == today)
        .first()
    )

    # Get previous snapshot for change calculation
    if existing:
        prev = (
            session.query(BudgetSnapshot)
            .filter(BudgetSnapshot.date < today)
            .order_by(BudgetSnapshot.date.desc())
            .first()
        )
    else:
        prev = (
            session.query(BudgetSnapshot)
            .order_by(BudgetSnapshot.date.desc())
            .first()
        )

    prev_balance = prev.current_balance if prev else None
    change = (
        current_balance - prev_balance
        if prev_balance is not None
        else Decimal("0")
    )

    if existing:
        existing.current_balance = current_balance
        existing.change_from_previous = change
        if notes is not None:
            existing.notes = notes

        # Replace entries
        session.query(BudgetBalanceEntry).filter(
            BudgetBalanceEntry.snapshot_id == existing.id
        ).delete()

        for account in accounts:
            session.add(BudgetBalanceEntry(
                snapshot_id=existing.id,
                account_id=account.id,
                account_name=account.name,
                balance=account.balance,
                is_credit=account.is_credit,
            ))

        session.commit()
        session.refresh(existing)
        return jsonify({"snapshot": existing.to_dict(), "updated": True})
    else:
        snapshot = BudgetSnapshot(
            date=today,
            current_balance=current_balance,
            change_from_previous=change,
            notes=notes,
        )
        session.add(snapshot)
        session.flush()

        for account in accounts:
            session.add(BudgetBalanceEntry(
                snapshot_id=snapshot.id,
                account_id=account.id,
                account_name=account.name,
                balance=account.balance,
                is_credit=account.is_credit,
            ))

        session.commit()
        session.refresh(snapshot)
        return jsonify({"snapshot": snapshot.to_dict(), "updated": False}), 201


@bp.get("/api/budget/snapshots")
def list_budget_snapshots() -> Response:
    """List all budget snapshots, newest first.

    Each snapshot includes a computed ``pay_period_change`` field: the
    cumulative balance change since the start of its pay period.
    """
    session = get_session()

    settings = session.query(BudgetSettings).first()
    payday_day = settings.payday_day if settings else 25

    snapshots = (
        session.query(BudgetSnapshot)
        .order_by(BudgetSnapshot.date.desc())
        .all()
    )

    # Build chronological list to compute pay_period_change
    chronological = list(reversed(snapshots))

    pay_period_changes: dict[int, float] = {}
    for i, snap in enumerate(chronological):
        period_start = _get_pay_period_start(snap.date, payday_day)

        # Find the last snapshot *before* this pay period started
        baseline_balance: Decimal | None = None
        for j in range(i - 1, -1, -1):
            if chronological[j].date < period_start:
                baseline_balance = chronological[j].current_balance
                break

        if baseline_balance is not None:
            pay_period_changes[snap.id] = float(
                snap.current_balance - baseline_balance
            )
        else:
            # No snapshot before this period – accumulate from the
            # first snapshot in the period instead
            pay_period_changes[snap.id] = 0.0
            for j in range(i):
                if (
                    _get_pay_period_start(chronological[j].date, payday_day)
                    == period_start
                ):
                    pay_period_changes[snap.id] = float(
                        snap.current_balance - chronological[j].current_balance
                    )
                    break

    result = []
    for snap in snapshots:
        d = snap.to_dict()
        d["pay_period_change"] = pay_period_changes.get(snap.id, 0.0)
        result.append(d)

    return jsonify(result)


@bp.delete("/api/budget/snapshots/<int:snapshot_id>")
def delete_budget_snapshot(snapshot_id: int) -> tuple[Response, int] | Response:
    """Delete a budget snapshot."""
    session = get_session()
    snapshot = session.get(BudgetSnapshot, snapshot_id)
    if not snapshot:
        return jsonify({"error": "Snapshot not found"}), 404

    session.delete(snapshot)
    session.commit()
    return jsonify({"message": "Snapshot deleted"})
