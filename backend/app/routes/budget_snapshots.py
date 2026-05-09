from datetime import date
from decimal import Decimal

from apiflask import APIBlueprint
from flask import Response, jsonify, request

from sqlalchemy.orm import Session as SQLAlchemySession

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


def _compute_pay_period_fields(
    session: SQLAlchemySession, snap: BudgetSnapshot
) -> dict:
    """Compute pay_period_change and pay_period_start for a single snapshot."""
    settings = session.query(BudgetSettings).first()
    payday_day = settings.payday_day if settings else 25

    period_start = _get_pay_period_start(snap.date, payday_day)

    # Find the last snapshot before this pay period as baseline
    baseline = (
        session.query(BudgetSnapshot)
        .filter(BudgetSnapshot.date < period_start)
        .order_by(BudgetSnapshot.date.desc())
        .first()
    )

    if baseline is not None:
        change = float(snap.current_balance - baseline.current_balance)
    else:
        change = 0.0

    return {
        "pay_period_change": change,
        "pay_period_start": period_start.isoformat(),
    }


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
        snap_dict = existing.to_dict()
        snap_dict.update(_compute_pay_period_fields(session, existing))
        return jsonify({"snapshot": snap_dict, "updated": True})
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
        snap_dict = snapshot.to_dict()
        snap_dict.update(_compute_pay_period_fields(session, snapshot))
        return jsonify({"snapshot": snap_dict, "updated": False}), 201


@bp.get("/api/budget/snapshots")
def list_budget_snapshots() -> Response:
    """List budget snapshots, newest first.

    Each snapshot includes:
    - ``pay_period_change``: cumulative balance change since pay period start
    - ``pay_period_start``: ISO date string for the period this snapshot belongs to

    Query params:
    - ``limit``: max snapshots to return (default 50, max 200)
    - ``offset``: number of snapshots to skip (default 0)

    Response includes ``total`` for pagination.
    """
    session = get_session()

    settings = session.query(BudgetSettings).first()
    payday_day = settings.payday_day if settings else 25

    # Pagination
    limit = min(int(request.args.get("limit", 50)), 200)
    offset = int(request.args.get("offset", 0))

    total = session.query(BudgetSnapshot).count()

    snapshots = (
        session.query(BudgetSnapshot)
        .order_by(BudgetSnapshot.date.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    if not snapshots:
        return jsonify({"snapshots": [], "total": total})

    # To compute pay_period_change we need the last snapshot before the
    # oldest pay period on this page as a potential baseline.
    oldest_date = snapshots[-1].date
    oldest_period_start = _get_pay_period_start(oldest_date, payday_day)

    baseline_snap = (
        session.query(BudgetSnapshot)
        .filter(BudgetSnapshot.date < oldest_period_start)
        .order_by(BudgetSnapshot.date.desc())
        .first()
    )

    # Build chronological list: baseline (if any) + page snapshots
    chronological: list[BudgetSnapshot] = []
    if baseline_snap:
        chronological.append(baseline_snap)
    chronological.extend(reversed(snapshots))

    # Single pass: track the baseline balance per pay period.
    # When the period changes, the last snapshot of the previous period
    # becomes the new baseline. Within a period, all snapshots compare
    # against the same baseline.
    pay_period_data: dict[int, tuple[float, str]] = {}
    current_period: date | None = None
    period_baseline: Decimal | None = None
    prev_balance: Decimal | None = (
        baseline_snap.current_balance if baseline_snap else None
    )

    start_idx = 1 if baseline_snap else 0
    for snap in chronological[start_idx:]:
        period_start = _get_pay_period_start(snap.date, payday_day)

        if period_start != current_period:
            # Entering a new pay period — baseline is the last snapshot
            # from the previous period
            current_period = period_start
            period_baseline = prev_balance

        if period_baseline is not None:
            change = float(snap.current_balance - period_baseline)
        else:
            change = 0.0

        pay_period_data[snap.id] = (change, period_start.isoformat())
        prev_balance = snap.current_balance

    result = []
    for snap in snapshots:
        d = snap.to_dict()
        change, period_start_str = pay_period_data.get(
            snap.id, (0.0, _get_pay_period_start(snap.date, payday_day).isoformat())
        )
        d["pay_period_change"] = change
        d["pay_period_start"] = period_start_str
        result.append(d)

    return jsonify({"snapshots": result, "total": total})


@bp.put("/api/budget/snapshots/<int:snapshot_id>")
def update_budget_snapshot(snapshot_id: int) -> tuple[Response, int] | Response:
    """Update a budget snapshot's entries and/or notes.

    Accepts JSON with:
    - ``entries``: list of ``{account_name, balance, is_credit, account_id?}``
    - ``notes``: optional string (max 500 chars)

    Recalculates current_balance and change_from_previous. Also updates
    the next snapshot's change_from_previous if one exists.
    """
    session = get_session()
    snapshot = session.get(BudgetSnapshot, snapshot_id)
    if not snapshot:
        return jsonify({"error": "Snapshot not found"}), 404

    data = request.get_json(silent=True) or {}

    if "notes" in data:
        notes = data["notes"]
        snapshot.notes = str(notes)[:500] if notes is not None else None

    if "entries" in data:
        entries = data["entries"]
        if not isinstance(entries, list):
            return jsonify({"error": "entries must be a list"}), 400

        # Replace all entries
        session.query(BudgetBalanceEntry).filter(
            BudgetBalanceEntry.snapshot_id == snapshot.id
        ).delete()

        for entry_data in entries:
            account_name = entry_data.get("account_name", "")
            if not account_name:
                return jsonify({"error": "Each entry needs account_name"}), 400

            session.add(BudgetBalanceEntry(
                snapshot_id=snapshot.id,
                account_id=entry_data.get("account_id"),
                account_name=str(account_name)[:100],
                balance=Decimal(str(entry_data.get("balance", 0))),
                is_credit=bool(entry_data.get("is_credit", False)),
            ))

        # Recalculate current_balance from new entries
        session.flush()
        snapshot.current_balance = sum(
            (e.balance for e in snapshot.entries), Decimal("0")
        )

    # Recalculate change_from_previous
    prev = (
        session.query(BudgetSnapshot)
        .filter(BudgetSnapshot.date < snapshot.date)
        .order_by(BudgetSnapshot.date.desc())
        .first()
    )
    snapshot.change_from_previous = (
        snapshot.current_balance - prev.current_balance
        if prev
        else Decimal("0")
    )

    # Update next snapshot's change_from_previous too
    next_snap = (
        session.query(BudgetSnapshot)
        .filter(BudgetSnapshot.date > snapshot.date)
        .order_by(BudgetSnapshot.date.asc())
        .first()
    )
    if next_snap:
        next_snap.change_from_previous = (
            next_snap.current_balance - snapshot.current_balance
        )

    session.commit()
    session.refresh(snapshot)
    snap_dict = snapshot.to_dict()
    snap_dict.update(_compute_pay_period_fields(session, snapshot))
    return jsonify({"snapshot": snap_dict})


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
