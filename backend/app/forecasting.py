"""Forecasting module for net worth projections.

This module provides modular forecasting capabilities that can be used by:
- API endpoints for user-facing forecasts
- Future AI integrations for custom queries like:
  - "How long until I reach 100k net worth?"
  - "What's my savings rate over the past 6 months?"
  - "When will I pay off my student loan at this pace?"

The module uses linear regression for trend-based projections and provides
helper functions for various financial calculations.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

from app.models import Goal, NetWorthSnapshot

# Type aliases for clarity
TrackingPeriod = Literal["month", "quarter", "half_year", "year"]
ForecastPeriod = Literal["month", "quarter", "half_year", "year"]

PERIOD_MONTHS: dict[str, int] = {
    "month": 1,
    "quarter": 3,
    "half_year": 6,
    "year": 12,
}


@dataclass
class ForecastPoint:
    """A single point in a forecast projection."""

    month: int
    year: int
    projected_net_worth: float


@dataclass
class NetWorthForecast:
    """Complete net worth forecast result."""

    period: ForecastPeriod
    months_ahead: int
    monthly_change_rate: float  # Average monthly change used for projection
    data_points_used: int  # Number of snapshots used for calculation
    projections: list[ForecastPoint]


@dataclass
class GoalForecastInfo:
    """Forecast information for a specific goal."""

    forecast_date: str | None  # ISO date when goal will be reached, None if never
    months_until_target: int | None  # Months until goal reached, None if never
    on_track: bool  # True if goal will be met by target_date
    required_monthly_change: float  # Monthly change needed to meet goal on time
    current_monthly_change: float  # Current average monthly change


def calculate_monthly_change_rate(
    snapshots: list[NetWorthSnapshot],
    period: ForecastPeriod = "quarter",
) -> tuple[float, int]:
    """Calculate average monthly change rate from historical snapshots.

    Args:
        snapshots: List of snapshots ordered newest first
        period: Time period to use for calculation

    Returns:
        Tuple of (monthly_change_rate, data_points_used)
    """
    if len(snapshots) < 2:
        return 0.0, 0

    num_months = PERIOD_MONTHS.get(period, 3)

    # Calculate changes over the specified period
    total_change = Decimal("0")
    changes_count = 0

    for i in range(min(num_months, len(snapshots) - 1)):
        current = snapshots[i]
        previous = snapshots[i + 1]
        change = current.net_worth - previous.net_worth
        total_change += change
        changes_count += 1

    if changes_count == 0:
        return 0.0, 0

    avg_monthly_change = float(total_change / changes_count)
    return avg_monthly_change, changes_count


def generate_net_worth_forecast(
    snapshots: list[NetWorthSnapshot],
    period: ForecastPeriod = "quarter",
    months_ahead: int = 12,
) -> NetWorthForecast:
    """Generate net worth projection based on historical trend.

    Uses the average monthly change over the specified period to project
    future net worth values.

    Args:
        snapshots: List of snapshots ordered newest first
        period: Time period to base the projection on
        months_ahead: Number of months to project into the future

    Returns:
        NetWorthForecast with projections and metadata
    """
    monthly_rate, data_points = calculate_monthly_change_rate(snapshots, period)

    projections: list[ForecastPoint] = []

    if snapshots:
        latest = snapshots[0]
        current_nw = float(latest.net_worth)
        current_month = latest.month
        current_year = latest.year

        for i in range(1, months_ahead + 1):
            # Calculate next month
            next_month = current_month + i
            next_year = current_year

            while next_month > 12:
                next_month -= 12
                next_year += 1

            projected_nw = current_nw + (monthly_rate * i)

            projections.append(
                ForecastPoint(
                    month=next_month,
                    year=next_year,
                    projected_net_worth=round(projected_nw, 2),
                )
            )

    return NetWorthForecast(
        period=period,
        months_ahead=months_ahead,
        monthly_change_rate=round(monthly_rate, 2),
        data_points_used=data_points,
        projections=projections,
    )


def calculate_goal_forecast(
    goal: Goal,
    current_value: float,
    snapshots: list[NetWorthSnapshot],
    category_id: int | None = None,
) -> GoalForecastInfo:
    """Calculate forecast information for a goal.

    For net_worth_target and category_target goals, calculates:
    - When the goal will be reached at current pace
    - Whether the goal is on track to be met by target_date
    - What monthly change is required to meet the goal on time

    Args:
        goal: The goal to forecast for
        current_value: Current progress value toward the goal
        snapshots: List of snapshots ordered newest first
        category_id: Category ID for category-based goals

    Returns:
        GoalForecastInfo with projection details
    """
    target = float(goal.target_value)
    remaining = target - current_value

    # Calculate current monthly change rate
    current_monthly_change = 0.0

    if goal.goal_type == "net_worth_target":
        current_monthly_change, _ = calculate_monthly_change_rate(snapshots, "quarter")
    elif goal.goal_type == "category_target" and category_id:
        current_monthly_change = _calculate_category_change_rate(
            snapshots, category_id, period="quarter"
        )
    elif goal.goal_type in ("category_monthly", "category_rate"):
        # For these goal types, current_value already represents the rate
        current_monthly_change = current_value

    # Calculate months until target (if ever)
    months_until_target: int | None = None
    forecast_date: str | None = None

    if current_monthly_change > 0 and remaining > 0:
        months_until_target = int(remaining / current_monthly_change) + 1
        # Calculate the forecast date
        if snapshots:
            latest = snapshots[0]
            forecast_month = latest.month + months_until_target
            forecast_year = latest.year

            while forecast_month > 12:
                forecast_month -= 12
                forecast_year += 1

            forecast_date = f"{forecast_year}-{forecast_month:02d}-01"
    elif remaining <= 0:
        # Goal already achieved
        months_until_target = 0
        forecast_date = datetime.now().strftime("%Y-%m-%d")

    # Check if on track for target_date
    on_track = False
    required_monthly_change = 0.0

    if goal.target_date:
        target_dt = goal.target_date
        if snapshots:
            latest = snapshots[0]
            current_dt = datetime(latest.year, latest.month, 1)

            # Calculate months remaining until target date
            months_remaining = (target_dt.year - current_dt.year) * 12 + (
                target_dt.month - current_dt.month
            )

            if months_remaining > 0 and remaining > 0:
                required_monthly_change = remaining / months_remaining
                on_track = current_monthly_change >= required_monthly_change
            elif remaining <= 0:
                # Already achieved
                on_track = True
                required_monthly_change = 0.0
            else:
                # Target date passed but not achieved
                on_track = False
                # Would need to achieve it all at once
                required_monthly_change = remaining
    else:
        # No target date - always "on track" as long as we're making progress
        on_track = current_monthly_change > 0 or remaining <= 0

    return GoalForecastInfo(
        forecast_date=forecast_date,
        months_until_target=months_until_target,
        on_track=on_track,
        required_monthly_change=round(required_monthly_change, 2),
        current_monthly_change=round(current_monthly_change, 2),
    )


def _calculate_category_change_rate(
    snapshots: list[NetWorthSnapshot],
    category_id: int,
    period: ForecastPeriod = "quarter",
) -> float:
    """Calculate average monthly change rate for a specific category.

    Args:
        snapshots: List of snapshots ordered newest first
        category_id: Category to track
        period: Time period to use for calculation

    Returns:
        Average monthly change rate for the category
    """
    if len(snapshots) < 2:
        return 0.0

    num_months = PERIOD_MONTHS.get(period, 3)

    total_change = Decimal("0")
    changes_count = 0

    for i in range(min(num_months, len(snapshots) - 1)):
        current = snapshots[i]
        previous = snapshots[i + 1]

        curr_amt = _get_category_amount(current, category_id)
        prev_amt = _get_category_amount(previous, category_id)
        change = curr_amt - prev_amt

        total_change += change
        changes_count += 1

    if changes_count == 0:
        return 0.0

    return float(total_change / changes_count)


def _get_category_amount(snapshot: NetWorthSnapshot, category_id: int) -> Decimal:
    """Get the amount for a specific category in a snapshot."""
    for entry in snapshot.entries:
        if entry.category_id == category_id:
            return entry.amount if entry.amount is not None else Decimal("0")
    return Decimal("0")


# =============================================================================
# Utility functions for AI/analytics integration
# =============================================================================


def calculate_savings_rate(
    snapshots: list[NetWorthSnapshot],
    net_income: float,
    period: ForecastPeriod = "half_year",
) -> float:
    """Calculate savings rate as percentage of net income.

    Useful for queries like "What's my savings rate over the past 6 months?"

    Args:
        snapshots: List of snapshots ordered newest first
        net_income: Monthly net income
        period: Time period to calculate over

    Returns:
        Savings rate as a percentage (0-100+)
    """
    if net_income <= 0:
        return 0.0

    monthly_change, _ = calculate_monthly_change_rate(snapshots, period)
    return round((monthly_change / net_income) * 100, 2)


def estimate_time_to_target(
    snapshots: list[NetWorthSnapshot],
    target_amount: float,
    period: ForecastPeriod = "quarter",
) -> int | None:
    """Estimate months until reaching a target net worth.

    Useful for queries like "How long until I reach 100k?"

    Args:
        snapshots: List of snapshots ordered newest first
        target_amount: Target net worth to reach
        period: Time period to base estimate on

    Returns:
        Estimated months, or None if target cannot be reached
    """
    if not snapshots:
        return None

    current = float(snapshots[0].net_worth)
    remaining = target_amount - current

    if remaining <= 0:
        return 0  # Already reached

    monthly_rate, _ = calculate_monthly_change_rate(snapshots, period)

    if monthly_rate <= 0:
        return None  # Will never reach at current pace

    return int(remaining / monthly_rate) + 1


def calculate_trajectory_comparison(
    snapshots: list[NetWorthSnapshot],
    target_value: float,
    target_date: datetime,
) -> dict:
    """Compare current trajectory vs required trajectory to meet a goal.

    Useful for visualizing "where I am" vs "where I need to be".

    Args:
        snapshots: List of snapshots ordered newest first
        target_value: Target net worth
        target_date: Date to reach target by

    Returns:
        Dict with trajectory comparison data for charting
    """
    if not snapshots:
        return {"current_trajectory": [], "required_trajectory": []}

    latest = snapshots[0]
    current_nw = float(latest.net_worth)
    current_dt = datetime(latest.year, latest.month, 1)

    months_remaining = (target_date.year - current_dt.year) * 12 + (
        target_date.month - current_dt.month
    )

    if months_remaining <= 0:
        return {"current_trajectory": [], "required_trajectory": []}

    # Calculate trajectories
    current_rate, _ = calculate_monthly_change_rate(snapshots, "quarter")
    required_rate = (target_value - current_nw) / months_remaining

    current_trajectory = []
    required_trajectory = []

    for i in range(months_remaining + 1):
        month = current_dt.month + i
        year = current_dt.year

        while month > 12:
            month -= 12
            year += 1

        label = f"{year}-{month:02d}"
        current_trajectory.append(
            {
                "label": label,
                "value": round(current_nw + (current_rate * i), 2),
            }
        )
        required_trajectory.append(
            {
                "label": label,
                "value": round(current_nw + (required_rate * i), 2),
            }
        )

    return {
        "current_trajectory": current_trajectory,
        "required_trajectory": required_trajectory,
        "current_rate": round(current_rate, 2),
        "required_rate": round(required_rate, 2),
    }
