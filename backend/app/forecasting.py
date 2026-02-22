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

from app.models import NetWorthSnapshot

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
