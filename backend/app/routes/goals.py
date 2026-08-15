from datetime import date, datetime
from decimal import Decimal

from apiflask import APIBlueprint
from flask import Response, jsonify, request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import get_session
from app.deadline_calc import get_next_payday, get_payday_after
from app.models import (
    BudgetSettings,
    Goal,
    NetWorthCategory,
    NetWorthSnapshot,
)
from app.routes.budget import (
    DAYS_PER_MONTH,
    compute_budget_totals,
    pending_one_time_items,
)

bp = APIBlueprint("goals", __name__, tag="Goals")

MAX_NAME_LENGTH = 100
MAX_TARGET_VALUE = 1_000_000_000  # 1 billion
VALID_GOAL_TYPES = ["net_worth", "savings_goal", "debt_payoff"]
# Goal types that participate in the sequential roadmap
ROADMAP_TYPES = ("savings_goal", "debt_payoff")

DATE_FORMAT_ERROR = "target_date must be a valid ISO date string"
CATEGORY_TYPE_ERROR = "category_id is only supported for savings_goal type"

# How far the payday-to-payday walk will look before giving up on a step.
# 100 years: long enough that any realistic plan resolves, short enough that a
# goal the surplus can never reach returns no date instead of an absurd one.
MAX_PROJECTION_PERIODS = 1200


@bp.get("/api/goals")
def list_goals() -> Response:
    """List all goals, roadmap steps first in plan order."""
    session = get_session()
    goals = (
        session.query(Goal)
        .order_by(Goal.priority.asc().nulls_last(), Goal.created_at.desc())
        .all()
    )
    return jsonify([g.to_dict() for g in goals])


def _next_priority(session: Session) -> int:
    """Next free position at the end of the roadmap."""
    max_priority = (
        session.query(func.max(Goal.priority))
        .filter(Goal.goal_type.in_(ROADMAP_TYPES))
        .scalar()
    )
    return 0 if max_priority is None else max_priority + 1


def _parse_amount(value: object, field: str) -> tuple[Decimal | None, str | None]:
    """Parse a non-negative money field; returns (value, error)."""
    try:
        amount = Decimal(str(value))
    except (ValueError, TypeError, ArithmeticError):
        return None, f"{field} must be a valid number"
    if amount < 0:
        return None, f"{field} must be positive"
    if amount > MAX_TARGET_VALUE:
        return None, f"{field} exceeds maximum allowed value"
    return amount, None


@bp.post("/api/goals")
def create_goal() -> Response | tuple[Response, int]:
    """Create a new goal.

    Required fields: name, goal_type, target_value
    Optional fields: category_id (savings_goal only), current_amount,
    target_date, is_active. Roadmap goals (savings_goal/debt_payoff) are
    appended to the end of the plan.
    """
    session = get_session()
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Validate required fields
    if "name" not in data:
        return jsonify({"error": "name is required"}), 400
    if "goal_type" not in data:
        return jsonify({"error": "goal_type is required"}), 400
    if "target_value" not in data:
        return jsonify({"error": "target_value is required"}), 400

    # Validate name
    name = str(data["name"]).strip()
    if not name or len(name) > MAX_NAME_LENGTH:
        return jsonify({"error": f"name must be 1-{MAX_NAME_LENGTH} characters"}), 400

    # Validate goal_type
    goal_type = str(data["goal_type"]).strip()
    if goal_type not in VALID_GOAL_TYPES:
        types_str = ", ".join(VALID_GOAL_TYPES)
        return jsonify({"error": f"goal_type must be one of: {types_str}"}), 400

    target_value, err = _parse_amount(data["target_value"], "target_value")
    if err:
        return jsonify({"error": err}), 400

    # Optional category link (progress then tracks the category's snapshot balance)
    category_id = None
    if data.get("category_id") is not None:
        if goal_type != "savings_goal":
            return jsonify({"error": CATEGORY_TYPE_ERROR}), 400
        category_id = int(data["category_id"])
        category = session.query(NetWorthCategory).filter_by(id=category_id).first()
        if not category:
            return jsonify({"error": "Category not found"}), 404

    # Optional manual progress
    current_amount = None
    if data.get("current_amount") is not None:
        current_amount, err = _parse_amount(data["current_amount"], "current_amount")
        if err:
            return jsonify({"error": err}), 400

    # Parse optional target_date
    target_date = None
    if "target_date" in data and data["target_date"]:
        try:
            date_str = str(data["target_date"])
            target_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            return jsonify({"error": DATE_FORMAT_ERROR}), 400

    goal = Goal(
        name=name,
        goal_type=goal_type,
        target_value=target_value,
        category_id=category_id,
        current_amount=current_amount,
        target_date=target_date,
        is_active=bool(data.get("is_active", True)),
        priority=_next_priority(session) if goal_type in ROADMAP_TYPES else None,
    )
    session.add(goal)
    session.commit()

    return jsonify(goal.to_dict()), 201


@bp.get("/api/goals/<int:goal_id>")
def get_goal(goal_id: int) -> Response | tuple[Response, int]:
    """Get a specific goal."""
    session = get_session()
    goal = session.query(Goal).filter_by(id=goal_id).first()

    if not goal:
        return jsonify({"error": "Goal not found"}), 404

    return jsonify(goal.to_dict())


@bp.put("/api/goals/<int:goal_id>")
def update_goal(goal_id: int) -> Response | tuple[Response, int]:
    """Update an existing goal."""
    session = get_session()
    goal = session.query(Goal).filter_by(id=goal_id).first()

    if not goal:
        return jsonify({"error": "Goal not found"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    if "name" in data:
        name = str(data["name"]).strip()
        if not name or len(name) > MAX_NAME_LENGTH:
            name_err = f"name must be 1-{MAX_NAME_LENGTH} characters"
            return jsonify({"error": name_err}), 400
        goal.name = name

    if "goal_type" in data:
        goal_type = str(data["goal_type"]).strip()
        if goal_type not in VALID_GOAL_TYPES:
            types_str = ", ".join(VALID_GOAL_TYPES)
            return jsonify({"error": f"goal_type must be one of: {types_str}"}), 400

        # Keep roadmap ordering consistent when a goal moves in or out of the plan
        if goal_type in ROADMAP_TYPES and goal.priority is None:
            goal.priority = _next_priority(session)
        elif goal_type not in ROADMAP_TYPES:
            goal.priority = None

        goal.goal_type = goal_type

    if "target_value" in data:
        target_value, err = _parse_amount(data["target_value"], "target_value")
        if err is not None or target_value is None:
            return jsonify({"error": err}), 400
        goal.target_value = target_value

    if "current_amount" in data:
        if data["current_amount"] is None:
            goal.current_amount = None
        else:
            current_amount, err = _parse_amount(
                data["current_amount"], "current_amount"
            )
            if err is not None or current_amount is None:
                return jsonify({"error": err}), 400
            goal.current_amount = current_amount

    if "category_id" in data:
        if data["category_id"] is None:
            goal.category_id = None
        else:
            if data.get("goal_type", goal.goal_type) != "savings_goal":
                return jsonify({"error": CATEGORY_TYPE_ERROR}), 400
            category_id = int(data["category_id"])
            category = session.query(NetWorthCategory).filter_by(id=category_id).first()
            if not category:
                return jsonify({"error": "Category not found"}), 404
            goal.category_id = category_id

    if "target_date" in data:
        if data["target_date"] is None:
            goal.target_date = None
        else:
            try:
                date_str = str(data["target_date"])
                date_val = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                goal.target_date = date_val
            except ValueError:
                return jsonify({"error": DATE_FORMAT_ERROR}), 400

    if "is_active" in data:
        goal.is_active = bool(data["is_active"])

    session.commit()
    return jsonify(goal.to_dict())


@bp.delete("/api/goals/<int:goal_id>")
def delete_goal(goal_id: int) -> tuple[Response, int]:
    """Delete a goal."""
    session = get_session()
    goal = session.query(Goal).filter_by(id=goal_id).first()

    if not goal:
        return jsonify({"error": "Goal not found"}), 404

    session.delete(goal)
    session.commit()
    return jsonify({"message": "Goal deleted"}), 200


def _roadmap_current_value(goal: Goal, latest: NetWorthSnapshot | None) -> Decimal:
    """Current progress of a roadmap step.

    A linked net worth category wins (auto-tracked from the latest snapshot);
    otherwise the manually maintained current_amount.
    """
    if goal.goal_type == "savings_goal" and goal.category_id and latest:
        return abs(_get_category_amount_in_snapshot(latest, goal.category_id))
    return goal.current_amount if goal.current_amount is not None else Decimal("0")


def _project_completions(
    remaining_steps: list[Decimal],
    surplus: Decimal,
    opening_balance: Decimal,
    one_times: list[tuple[date, Decimal]],
    today: date,
    payday_day: int,
) -> list[date | None]:
    """Completion date for each unfinished step, walking payday to payday.

    The budget month rolls over on payday rather than on the 1st, because that
    is when the money actually arrives. So the surplus is realized in a lump at
    each payday instead of trickling in day by day, and a step completes on the
    payday that first covers it. The current part-period is credited pro rata
    for the days remaining in it, so a projection made the day before payday
    doesn't get handed a full month of surplus it hasn't earned.

    One-time items are charged on the day they actually fall due rather than all
    up front — a step that finishes before a bill lands shouldn't be delayed by
    it, and one that finishes after should.

    Steps are funded strictly in order out of a single running balance.
    """
    completions: list[date | None] = [None] * len(remaining_steps)
    if surplus <= 0 or not remaining_steps:
        return completions

    charges: dict[date, Decimal] = {}
    balance = opening_balance
    for due, amount in one_times:
        if due <= today:
            # Already due (or undated, so treated as immediate)
            balance += amount
        else:
            charges[due] = charges.get(due, Decimal("0")) + amount

    index = 0

    def settle(on: date) -> None:
        """Close out every step the balance now covers."""
        nonlocal index, balance
        while index < len(remaining_steps) and balance >= remaining_steps[index]:
            balance -= remaining_steps[index]
            completions[index] = on
            index += 1

    settle(today)

    boundaries: list[date] = []
    boundary = get_next_payday(today, payday_day)
    for _ in range(MAX_PROJECTION_PERIODS):
        boundaries.append(boundary)
        boundary = get_payday_after(boundary, payday_day)

    boundary_set = set(boundaries)
    events = sorted(boundary_set | {d for d in charges if d <= boundaries[-1]})

    previous_payday = today
    for event in events:
        if index >= len(remaining_steps):
            break
        if event in boundary_set:
            span = Decimal((event - previous_payday).days)
            balance += surplus * span / DAYS_PER_MONTH
            previous_payday = event
        balance += charges.get(event, Decimal("0"))
        settle(event)

    return completions


@bp.get("/api/goals/roadmap")
def get_roadmap() -> Response:
    """The sequential financial roadmap, funded by the monthly budget surplus.

    Active savings_goal/debt_payoff goals in priority order form a waterfall:
    the whole surplus (monthly net income minus monthly expenses, each
    recurring line normalized to its per-month rate) flows into the first
    unfinished step until it completes, then cascades to the next. Returns
    per-step progress and projected completion dates at the current surplus.
    """
    session = get_session()

    goals = (
        session.query(Goal)
        .filter(Goal.goal_type.in_(ROADMAP_TYPES), Goal.is_active.is_(True))
        .order_by(Goal.priority.asc().nulls_last(), Goal.created_at.asc())
        .all()
    )

    totals = compute_budget_totals(session)
    surplus = totals["monthly_surplus"]

    snapshots = _get_snapshots(session, 1)
    latest = snapshots[0] if snapshots else None

    today = date.today()
    settings = session.query(BudgetSettings).first()
    payday_day = settings.payday_day if settings else 25

    # Where the plan actually starts from, rather than an implied clean zero.
    #
    # current_balance sums every account, and credit cards are stored negative,
    # so it already assumes each card is paid off in full — the same assumption
    # calculate_cc_payments_before_payday makes. The card debt is therefore
    # counted here exactly once and must not be subtracted again on its due day.
    #
    # The projection walks from opening_balance, clamped at zero: a shortfall has
    # to be earned back before any step can be funded (card interest makes that
    # the only sensible order), but spare cash is deliberately NOT a head start.
    # Money sitting outside the account a goal tracks isn't earmarked for that
    # goal, and for a category-linked goal it would double-count against the
    # progress read from the net worth snapshot.
    #
    # The reported starting position clamps once, after the pending one-time
    # items are netted in, so money genuinely in the account covers a one-off
    # bill. Clamping the balance first meant any net-negative one-off flow read
    # as "starting behind" with five figures in the bank: a 50 € bill against a
    # 10 550 € balance is not a shortfall.
    opening_balance = min(Decimal("0"), totals["current_balance"])
    one_times = pending_one_time_items(session, today)
    one_time_net = sum((amount for _, amount in one_times), Decimal("0"))
    starting_position = min(Decimal("0"), totals["current_balance"] + one_time_net)

    # Total drag expressed in months of surplus. Not a date: one-time items land
    # on their own due dates during the walk, so this is "how much of the plan's
    # surplus is already spoken for", which is what the UI banner reports.
    shortfall_months = Decimal("0")
    if starting_position < 0 and surplus > 0:
        shortfall_months = -starting_position / surplus

    unfinished = [
        max(Decimal("0"), goal.target_value - _roadmap_current_value(goal, latest))
        for goal in goals
        if goal.target_value - _roadmap_current_value(goal, latest) > 0
    ]
    projected = _project_completions(
        unfinished, surplus, opening_balance, one_times, today, payday_day
    )

    projection = iter(projected)
    active_seen = False
    steps = []
    for goal in goals:
        current = _roadmap_current_value(goal, latest)
        target = goal.target_value
        remaining = max(Decimal("0"), target - current)

        if target > 0:
            progress_pct = min(100.0, float(current / target * 100))
        else:
            progress_pct = 100.0

        months_to_complete: float | None = None
        completion_date: date | None = None
        if remaining <= 0:
            status = "completed"
        else:
            status = "upcoming" if active_seen else "active"
            active_seen = True
            completion_date = next(projection, None)
            if completion_date is not None:
                months_to_complete = float(
                    Decimal((completion_date - today).days) / DAYS_PER_MONTH
                )

        steps.append(
            {
                "goal": goal.to_dict(),
                "current_value": float(current),
                "remaining": float(remaining),
                "progress_percentage": round(progress_pct, 2),
                "status": status,
                "months_to_complete": (
                    round(months_to_complete, 1)
                    if months_to_complete is not None
                    else None
                ),
                "projected_completion_date": (
                    completion_date.isoformat() if completion_date else None
                ),
            }
        )

    return jsonify(
        {
            "surplus_monthly": float(surplus),
            # Starting stock the plan is projected from: net cash across all
            # accounts (cards assumed paid in full) plus pending one-time items,
            # clamped so spare cash is never a head start. Zero or negative.
            "starting_position": float(starting_position),
            "pending_one_time_net": float(one_time_net),
            "shortfall_months": (
                round(float(shortfall_months), 1) if shortfall_months else 0.0
            ),
            "goals": steps,
        }
    )


@bp.put("/api/goals/reorder")
def reorder_goals() -> Response | tuple[Response, int]:
    """Reorder the roadmap: goal_ids in the desired sequence."""
    session = get_session()
    data = request.get_json()

    if not data or not isinstance(data.get("goal_ids"), list):
        return jsonify({"error": "goal_ids list is required"}), 400

    try:
        goal_ids = [int(goal_id) for goal_id in data["goal_ids"]]
    except (ValueError, TypeError):
        return jsonify({"error": "goal_ids must be integers"}), 400

    goals = session.query(Goal).filter(Goal.id.in_(goal_ids)).all()
    by_id = {g.id: g for g in goals}

    missing = [goal_id for goal_id in goal_ids if goal_id not in by_id]
    if missing:
        return jsonify({"error": f"Goals not found: {missing}"}), 404

    non_roadmap = [g.id for g in goals if g.goal_type not in ROADMAP_TYPES]
    if non_roadmap:
        return jsonify({"error": f"Not roadmap goals: {non_roadmap}"}), 400

    for index, goal_id in enumerate(goal_ids):
        by_id[goal_id].priority = index
    session.commit()

    return jsonify([by_id[goal_id].to_dict() for goal_id in goal_ids])


def _get_snapshots(session: Session, num_months: int) -> list[NetWorthSnapshot]:
    """Get snapshots ordered newest first."""
    result: list[NetWorthSnapshot] = (
        session.query(NetWorthSnapshot)
        .order_by(NetWorthSnapshot.year.desc(), NetWorthSnapshot.month.desc())
        .limit(num_months + 1)  # +1 to get the "before" snapshot for comparison
        .all()
    )
    return result


def _get_category_amount_in_snapshot(
    snapshot: NetWorthSnapshot, category_id: int
) -> Decimal:
    """Get the amount for a specific category in a snapshot."""
    for entry in snapshot.entries:
        if entry.category_id == category_id:
            return entry.amount if entry.amount is not None else Decimal("0")
    return Decimal("0")


# Minimum snapshots before we trust a measured saving pace.
MIN_MONTHS_FOR_PACE = 3


def _months_between(later: NetWorthSnapshot, earlier: NetWorthSnapshot) -> int:
    """Whole months from the earlier snapshot to the later one."""
    return (later.year - earlier.year) * 12 + (later.month - earlier.month)


def _tracked_value_in_snapshot(snapshot: NetWorthSnapshot, goal: Goal) -> Decimal:
    """The value this goal tracks within a single snapshot."""
    if goal.goal_type in ("net_worth", "net_worth_target"):
        return Decimal(str(snapshot.net_worth))
    if goal.goal_type in ("savings_goal", "category_target") and goal.category_id:
        return abs(_get_category_amount_in_snapshot(snapshot, goal.category_id))
    return Decimal("0")


def _recent_monthly_change(
    goal: Goal, snapshots: list[NetWorthSnapshot]
) -> Decimal | None:
    """Average monthly change in the tracked value across the snapshot window.

    This is the *actual* recent saving pace: how much the tracked balance has
    moved per month over the available history. The previous implementation
    divided the whole current balance by the number of months of data, which
    treated a long-standing balance as if it had all been saved since tracking
    began and badly overstated progress.

    Returns None when there aren't at least two snapshots spanning a positive
    number of months, so no pace can be derived.
    """
    if len(snapshots) < 2:
        return None

    latest, oldest = snapshots[0], snapshots[-1]
    months = _months_between(latest, oldest)
    if months <= 0:
        return None

    change = _tracked_value_in_snapshot(latest, goal) - _tracked_value_in_snapshot(
        oldest, goal
    )
    return change / Decimal(months)


def _empty_pace() -> dict:
    """A pace analysis with no verdict."""
    return {
        "status": None,
        "status_reason": None,
        "required_monthly": None,
        "recent_monthly": None,
        "projected_value": None,
        "months_remaining": None,
    }


def _analyze_pace(
    goal: Goal,
    current_value: Decimal,
    target_value: Decimal,
    recent_monthly: Decimal | None,
    data_months: int,
) -> dict:
    """Assess whether a net_worth / savings_goal is on track for its target.

    Compares the *required* monthly pace (the gap to target spread over the
    time remaining) against the *actual* recent monthly pace measured from
    snapshots, and explains the verdict so the UI can say why.

    Returns a dict with: status, status_reason, required_monthly,
    recent_monthly, projected_value, months_remaining.
    """
    pace = _empty_pace()

    # Already there.
    if current_value >= target_value:
        pace["status"] = "on_track"
        pace["status_reason"] = "Target reached"
        return pace

    # Without a deadline there is no pace to be on track for.
    if not goal.target_date:
        pace["status_reason"] = "Set a target date to track your pace"
        return pace

    now = datetime.now(tz=goal.target_date.tzinfo)
    months_remaining = (goal.target_date.year - now.year) * 12 + (
        goal.target_date.month - now.month
    )
    pace["months_remaining"] = months_remaining

    if goal.target_date <= now or months_remaining <= 0:
        pace["status"] = "behind"
        pace["status_reason"] = "Target date has passed"
        return pace

    remaining = target_value - current_value
    required_monthly = remaining / Decimal(months_remaining)
    pace["required_monthly"] = float(required_monthly)

    # Need enough history to measure a trustworthy pace.
    if recent_monthly is None or data_months < MIN_MONTHS_FOR_PACE:
        pace["status_reason"] = "Add more monthly snapshots to track your pace"
        return pace

    pace["recent_monthly"] = float(recent_monthly)
    projected = current_value + recent_monthly * months_remaining
    pace["projected_value"] = float(projected)

    if recent_monthly >= required_monthly:
        pace["status"] = "on_track"
        pace["status_reason"] = "Saving fast enough to reach the target on time"
    elif recent_monthly <= 0:
        pace["status"] = "behind"
        pace["status_reason"] = "Balance isn't growing toward the target"
    else:
        pace["status"] = "behind"
        pace["status_reason"] = "Saving too slowly to reach the target on time"
    return pace


def calculate_goal_progress(
    goal: Goal,
    snapshots: list[NetWorthSnapshot],
) -> dict:
    """Calculate progress for a single goal.

    Returns a dict with:
    - goal: the goal data
    - current_value: current progress value
    - target_value: target value
    - progress_percentage: 0-100 percentage (capped at 100)
    - is_achieved: whether goal is met
    - status: 'on_track', 'behind', or None (if no target_date or <3 months data)
    - status_reason: short human-readable explanation of the status
    - required_monthly: monthly amount needed to hit the target by target_date
    - recent_monthly: actual recent monthly saving pace (from snapshots)
    - projected_value: value at target_date if the recent pace continues
    - months_remaining: whole months until target_date
    - data_months: number of months of snapshot data available
    - category_name: category name (for savings_goal type)
    """
    zero = Decimal("0")
    current_value = zero
    category_name: str | None = None
    data_months = len(snapshots)
    latest = snapshots[0] if snapshots else None

    # Support both old types (net_worth_target, category_target) and new types
    if goal.goal_type in ("net_worth", "net_worth_target"):
        # Overall net worth target
        if latest:
            current_value = Decimal(str(latest.net_worth))

    elif goal.goal_type in ("savings_goal", "category_target"):
        # Linked category balance wins; manual current_amount otherwise
        if latest and goal.category_id:
            current_value = abs(
                _get_category_amount_in_snapshot(latest, goal.category_id)
            )
        elif goal.current_amount is not None:
            current_value = goal.current_amount
        category_name = goal.category.name if goal.category else None

    elif goal.goal_type == "debt_payoff":
        current_value = goal.current_amount if goal.current_amount is not None else zero

    # Calculate progress percentage
    target = goal.target_value

    if target > 0:
        progress_pct = float((current_value / target) * 100)
    elif target == 0 and current_value >= 0:
        progress_pct = 100.0
    else:
        progress_pct = 0.0

    # Standard: achieved when current >= target
    is_achieved = current_value >= target

    # Cap at 100%, floor at 0%
    progress_pct = max(0.0, min(progress_pct, 100.0))

    # Calculate on-track status and the pace details behind it
    recent_monthly = _recent_monthly_change(goal, snapshots)
    pace = _analyze_pace(goal, current_value, target, recent_monthly, data_months)

    return {
        "goal": goal.to_dict(),
        "current_value": float(current_value),
        "target_value": float(target),
        "progress_percentage": round(progress_pct, 2),
        "is_achieved": is_achieved,
        "status": pace["status"],
        "status_reason": pace["status_reason"],
        "required_monthly": pace["required_monthly"],
        "recent_monthly": pace["recent_monthly"],
        "projected_value": pace["projected_value"],
        "months_remaining": pace["months_remaining"],
        "data_months": data_months,
        "category_name": category_name,
    }


@bp.get("/api/goals/progress")
def get_goals_progress() -> Response:
    """Get progress for all active goals.

    Calculates current progress based on:
    - net_worth: Latest net worth snapshot value
    - savings_goal: Linked category balance, or manual current_amount
    - debt_payoff: Manual current_amount (paid off so far)

    Returns a list of goal progress objects.
    """
    session = get_session()

    # Get all active goals
    goals = (
        session.query(Goal)
        .filter_by(is_active=True)
        .order_by(Goal.priority.asc().nulls_last(), Goal.created_at.desc())
        .all()
    )

    if not goals:
        return jsonify([])

    # Get snapshots (enough for calculating monthly changes)
    snapshots = _get_snapshots(session, 12)

    # Calculate progress for each goal
    progress_list = [calculate_goal_progress(goal, snapshots) for goal in goals]

    return jsonify(progress_list)
