"""Financial Independence / Retire Early (FIRE) calculation utilities.

All monetary values are in EUR using Decimal for precision.
Return rates are annual percentages (e.g., 7 for 7%).
Inflation is an annual percentage (e.g., 2 for 2%).
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Literal

# Type alias for pension scenario labels
PensionLabel = Literal["early", "normal", "late"]

# Early/late pension adjustment rate per month (Finnish TyEL)
PENSION_ADJUSTMENT_PER_MONTH = Decimal("0.004")


@dataclass
class FireInputs:
    """Inputs for FIRE calculations."""

    current_net_worth: Decimal
    monthly_contribution: Decimal  # monthly savings/investment
    annual_expenses: Decimal
    annual_return_pct: Decimal  # e.g. 7 for 7%
    inflation_pct: Decimal  # e.g. 2 for 2%
    current_age: int
    target_retirement_age: int
    safe_withdrawal_rate: Decimal  # e.g. 4 for 4%
    # Optional pension inputs (presence activates pension mode)
    pension_accrued_monthly: Decimal | None = None
    pension_monthly_salary: Decimal | None = None
    pension_accrual_rate: Decimal = Decimal("1.5")
    pension_full_age: int = 68
    pension_guarantee_enabled: bool = False
    pension_guarantee_amount: Decimal = Decimal("990.0")
    life_expectancy: int = 95


@dataclass
class PensionScenario:
    """A single pension scenario (early/normal/late)."""

    label: PensionLabel
    pension_start_age: int
    monthly_pension: Decimal
    annual_pension: Decimal
    pension_fire_number: Decimal


@dataclass
class PensionResult:
    """Pension calculation results."""

    projected_monthly_pension: Decimal
    scenarios: list[PensionScenario]
    pension_coast_fire_number: Decimal
    guarantee_active: bool
    guarantee_amount: Decimal
    crossover_age: Decimal | None


@dataclass
class ProjectionPoint:
    """A single point in the projection timeline."""

    age: int
    year: int
    month: int
    net_worth: Decimal
    coast_net_worth: Decimal
    # Pension drawdown projections (present when pension is active)
    net_worth_early: Decimal | None = None
    net_worth_normal: Decimal | None = None
    net_worth_late: Decimal | None = None


@dataclass
class FireResult:
    """Complete FIRE calculation results."""

    fire_number: Decimal
    coast_fire_number: Decimal
    coast_fire_reached: bool
    years_to_fire: Decimal | None  # None if unreachable
    fire_age: Decimal | None
    coast_fire_age: Decimal | None
    on_track: bool
    portfolio_depleted_age: Decimal | None
    projections: list[ProjectionPoint] = field(default_factory=list)
    pension: PensionResult | None = None


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _decimal_round(value: Decimal, places: int = 2) -> Decimal:
    """Round a Decimal to specified decimal places."""
    return value.quantize(Decimal(10) ** -places)


def _decimal_power(base: Decimal, exponent: Decimal) -> Decimal:
    """Calculate base ** exponent for Decimals using float conversion.

    Note: For financial projections, float precision is acceptable.
    """
    return Decimal(str(float(base) ** float(exponent)))


# ---------------------------------------------------------------------------
# Core calculation functions
# ---------------------------------------------------------------------------


def calc_fire_number(annual_expenses: Decimal, swr_pct: Decimal) -> Decimal:
    """Calculate the FIRE number based on annual expenses and safe withdrawal rate.

    FIRE Number = Annual Expenses / (SWR / 100)
    """
    if swr_pct <= 0:
        return Decimal("Infinity")
    return annual_expenses / (swr_pct / 100)


def calc_coast_fire_number(
    fire_number: Decimal,
    real_annual_return_pct: Decimal,
    years_to_retirement: Decimal,
) -> Decimal:
    """Calculate Coast FIRE number.

    This is how much you need RIGHT NOW so that compound growth alone
    (no further contributions) reaches your FIRE number by retirement.

    CoastFIRE = FIRE_Number / (1 + realReturn)^yearsToRetirement
    """
    if years_to_retirement <= 0:
        return fire_number
    r = real_annual_return_pct / 100
    growth_factor = _decimal_power(1 + r, years_to_retirement)
    return fire_number / growth_factor


def calc_years_to_fire(
    current_net_worth: Decimal,
    monthly_contribution: Decimal,
    fire_number: Decimal,
    real_annual_return_pct: Decimal,
) -> Decimal | None:
    """Calculate years to reach FIRE using iterative month-by-month simulation.

    Uses real (inflation-adjusted) returns.
    Returns None if FIRE is unreachable within 100 years.
    """
    if current_net_worth >= fire_number:
        return Decimal("0")

    monthly_return = (
        _decimal_power(1 + real_annual_return_pct / 100, Decimal("1") / 12) - 1
    )
    nw = current_net_worth
    max_months = 100 * 12

    for m in range(1, max_months + 1):
        nw = nw * (1 + monthly_return) + monthly_contribution
        if nw >= fire_number:
            return Decimal(m) / 12

    return None


def calc_coast_fire_age(
    current_net_worth: Decimal,
    monthly_contribution: Decimal,
    fire_number: Decimal,
    real_annual_return_pct: Decimal,
    current_age: int,
    target_retirement_age: int,
) -> Decimal | None:
    """Calculate the age at which you reach Coast FIRE.

    At each month, checks: can current NW (with contributions) compound to
    the FIRE number in the remaining time without further contributions?
    Returns None if unreachable before target retirement age.
    """
    r = real_annual_return_pct / 100
    monthly_return = _decimal_power(1 + r, Decimal("1") / 12) - 1
    total_months = round((target_retirement_age - current_age) * 12)

    if total_months <= 0:
        return None

    # Check starting point
    years_to_retire = Decimal(target_retirement_age - current_age)
    coast_needed_now = fire_number / _decimal_power(1 + r, years_to_retire)
    if current_net_worth >= coast_needed_now:
        return Decimal(current_age)

    nw = current_net_worth

    for m in range(1, total_months + 1):
        nw = nw * (1 + monthly_return) + monthly_contribution
        age = Decimal(current_age) + Decimal(m) / 12
        years_remaining = Decimal(target_retirement_age) - age
        if years_remaining <= 0:
            break
        coast_needed = fire_number / _decimal_power(1 + r, years_remaining)
        if nw >= coast_needed:
            return _decimal_round(age, 1)

    return None


# ---------------------------------------------------------------------------
# Pension calculation functions
# ---------------------------------------------------------------------------


def calc_projected_monthly_pension(
    accrued_monthly: Decimal,
    current_age: int,
    fire_age: Decimal,
    monthly_salary: Decimal,
    accrual_rate_pct: Decimal,
) -> Decimal:
    """Project monthly pension at FIRE age based on current accrual and future work.

    Accrual stops when you FIRE (stop working).
    """
    years_of_accrual = max(Decimal("0"), fire_age - current_age)
    additional_monthly_pension = (
        years_of_accrual * monthly_salary * (accrual_rate_pct / 100)
    )
    return accrued_monthly + additional_monthly_pension


def calc_pension_adjustment(
    projected_monthly: Decimal,
    pension_full_age: int,
    pension_start_age: int,
) -> Decimal:
    """Apply early/late pension adjustment (0.4%/month from full pension age).

    Early = reduction, late = bonus.
    """
    months_delta = (pension_start_age - pension_full_age) * 12
    adjustment_factor = 1 + months_delta * PENSION_ADJUSTMENT_PER_MONTH
    return max(Decimal("0"), projected_monthly * adjustment_factor)


def pv_annuity(
    annual_payment: Decimal, years: Decimal, real_annual_return: Decimal
) -> Decimal:
    """Present value of an annuity: fixed annual payment for N years at real return r.

    Used for die-with-zero calculations.
    """
    if years <= 0 or annual_payment <= 0:
        return Decimal("0")
    if abs(real_annual_return) < Decimal("0.0000000001"):
        return annual_payment * years
    r = real_annual_return
    discount_factor = _decimal_power(1 + r, -years)
    return annual_payment * (1 - discount_factor) / r


def calc_pension_fire_number(
    annual_expenses: Decimal,
    annual_pension: Decimal,
    fire_age: Decimal,
    pension_start_age: int,
    swr_pct: Decimal,
    real_annual_return: Decimal,
) -> Decimal:
    """Pension-adjusted FIRE number using two-phase SWR + pension model.

    Phase 1 (FIRE age → pension start): portfolio covers ALL expenses via
    annuity drawdown.
    Phase 2 (pension start → ∞): portfolio sustains (expenses - pension)
    indefinitely via SWR.

    FIRE number = PV of phase 1 expenses + PV of phase 2 portfolio needed
    at pension start.
    """
    r = real_annual_return
    phase1_years = max(Decimal("0"), Decimal(pension_start_age) - fire_age)

    # Portfolio needed at pension start to sustain the gap indefinitely via SWR
    phase2_annual_gap = max(Decimal("0"), annual_expenses - annual_pension)
    phase2_portfolio = (
        phase2_annual_gap / (swr_pct / 100) if swr_pct > 0 else Decimal("Infinity")
    )

    phase1_pv = pv_annuity(annual_expenses, phase1_years, r)

    # Discount phase 2 portfolio back to FIRE age
    if phase1_years > 0:
        discount_factor = _decimal_power(1 + r, -phase1_years)
    else:
        discount_factor = Decimal("1")
    phase2_pv = phase2_portfolio * discount_factor

    return phase1_pv + phase2_pv


def calc_guarantee_crossover_age(
    accrued_monthly: Decimal,
    current_age: int,
    monthly_salary: Decimal,
    accrual_rate_pct: Decimal,
    guarantee_amount: Decimal,
    max_age: int,
) -> Decimal | None:
    """Calculate the age at which projected TyEL pension >= guarantee amount.

    Returns None if already exceeded or if it never crosses within reasonable
    timeframe.
    """
    if accrued_monthly >= guarantee_amount:
        return Decimal(current_age)
    annual_accrual = monthly_salary * (accrual_rate_pct / 100)
    if annual_accrual <= 0:
        return None
    years_needed = (guarantee_amount - accrued_monthly) / annual_accrual
    crossover_age = Decimal(current_age) + years_needed
    return _decimal_round(crossover_age, 1) if crossover_age <= max_age else None


def generate_pension_scenarios(
    projected_monthly_pension: Decimal,
    pension_full_age: int,
    fire_age: Decimal,
    annual_expenses: Decimal,
    swr_pct: Decimal,
    real_annual_return: Decimal,
) -> list[PensionScenario]:
    """Generate the 3 pension scenarios (early / normal / late)."""
    configs: list[tuple[PensionLabel, int]] = [
        ("early", -3),
        ("normal", 0),
        ("late", 3),
    ]

    scenarios: list[PensionScenario] = []
    for label, offset in configs:
        pension_start_age = pension_full_age + offset
        monthly_pension = calc_pension_adjustment(
            projected_monthly_pension,
            pension_full_age,
            pension_start_age,
        )
        annual_pension = monthly_pension * 12
        pension_fire_number = calc_pension_fire_number(
            annual_expenses,
            annual_pension,
            fire_age,
            pension_start_age,
            swr_pct,
            real_annual_return,
        )
        scenarios.append(
            PensionScenario(
                label=label,
                pension_start_age=pension_start_age,
                monthly_pension=_decimal_round(monthly_pension, 2),
                annual_pension=_decimal_round(annual_pension, 2),
                pension_fire_number=_decimal_round(pension_fire_number, 2),
            )
        )

    return scenarios


# ---------------------------------------------------------------------------
# Pension-aware FIRE calculation
# ---------------------------------------------------------------------------


def calc_fire_number_for_age(
    retirement_age: Decimal,
    annual_expenses: Decimal,
    safe_withdrawal_rate: Decimal,
    real_return: Decimal,
    pension_accrued_monthly: Decimal,
    current_age: int,
    pension_monthly_salary: Decimal,
    pension_accrual_rate: Decimal,
    pension_full_age: int,
    pension_guarantee_enabled: bool = False,
    pension_guarantee_amount: Decimal = Decimal("990.0"),
) -> Decimal:
    """Calculate the FIRE number for a specific retirement age.

    Accounts for pension accrued up to that age.
    """
    # Calculate pension at retirement age
    projected_monthly = calc_projected_monthly_pension(
        pension_accrued_monthly,
        current_age,
        retirement_age,
        pension_monthly_salary,
        pension_accrual_rate,
    )

    # Apply guarantee floor if enabled
    effective_monthly = (
        max(projected_monthly, pension_guarantee_amount)
        if pension_guarantee_enabled
        else projected_monthly
    )

    # Apply early/late adjustment for normal pension start age
    adjusted_monthly = calc_pension_adjustment(
        effective_monthly,
        pension_full_age,
        pension_full_age,  # normal pension = starts at full age
    )
    annual_pension = adjusted_monthly * 12

    # Calculate FIRE number for this retirement age
    return calc_pension_fire_number(
        annual_expenses,
        annual_pension,
        retirement_age,
        pension_full_age,
        safe_withdrawal_rate,
        real_return,
    )


def calc_pension_aware_years_to_fire(
    current_net_worth: Decimal,
    monthly_contribution: Decimal,
    annual_expenses: Decimal,
    real_annual_return_pct: Decimal,
    current_age: int,
    safe_withdrawal_rate: Decimal,
    pension_accrued_monthly: Decimal,
    pension_monthly_salary: Decimal,
    pension_accrual_rate: Decimal,
    pension_full_age: int,
    pension_guarantee_enabled: bool = False,
    pension_guarantee_amount: Decimal = Decimal("990.0"),
) -> tuple[Decimal, Decimal] | None:
    """Calculate earliest FIRE age with pension awareness.

    At each simulated month, calculates what the FIRE number would be
    if you retired at that age (accounting for pension accrued up to that point).

    Returns tuple of (years_to_fire, fire_number_at_that_age) or None if unreachable.
    """
    real_return = real_annual_return_pct / 100
    monthly_return = _decimal_power(1 + real_return, Decimal("1") / 12) - 1
    max_months = 100 * 12

    # Check if already FIRE'd at current age
    current_fire_number = calc_fire_number_for_age(
        Decimal(current_age),
        annual_expenses,
        safe_withdrawal_rate,
        real_return,
        pension_accrued_monthly,
        current_age,
        pension_monthly_salary,
        pension_accrual_rate,
        pension_full_age,
        pension_guarantee_enabled,
        pension_guarantee_amount,
    )
    if current_net_worth >= current_fire_number:
        return (Decimal("0"), current_fire_number)

    nw = current_net_worth

    for m in range(1, max_months + 1):
        nw = nw * (1 + monthly_return) + monthly_contribution
        age = Decimal(current_age) + Decimal(m) / 12

        fire_number_at_age = calc_fire_number_for_age(
            age,
            annual_expenses,
            safe_withdrawal_rate,
            real_return,
            pension_accrued_monthly,
            current_age,
            pension_monthly_salary,
            pension_accrual_rate,
            pension_full_age,
            pension_guarantee_enabled,
            pension_guarantee_amount,
        )

        if nw >= fire_number_at_age:
            return (Decimal(m) / 12, fire_number_at_age)

    return None


# ---------------------------------------------------------------------------
# Projection generation
# ---------------------------------------------------------------------------


def generate_projections(
    inputs: FireInputs,
    years_ahead: int = 40,
    pension_result: PensionResult | None = None,
) -> list[ProjectionPoint]:
    """Generate year-by-year projections for net worth growth.

    When pension inputs are present, extends past FIRE age with drawdown projections.
    """
    real_return_pct = inputs.annual_return_pct - inputs.inflation_pct
    monthly_return = _decimal_power(1 + real_return_pct / 100, Decimal("1") / 12) - 1
    total_months = years_ahead * 12
    current_year = datetime.now().year
    current_month = datetime.now().month

    points: list[ProjectionPoint] = []
    has_pension = pension_result is not None

    # Fire age for drawdown transition
    if has_pension:
        fire_age = Decimal(inputs.target_retirement_age)
    else:
        fire_age = Decimal("Infinity")

    monthly_expenses = inputs.annual_expenses / 12
    early_pension_monthly = (
        pension_result.scenarios[0].monthly_pension
        if has_pension and pension_result
        else Decimal("0")
    )
    normal_pension_monthly = (
        pension_result.scenarios[1].monthly_pension
        if has_pension and pension_result
        else Decimal("0")
    )
    late_pension_monthly = (
        pension_result.scenarios[2].monthly_pension
        if has_pension and pension_result
        else Decimal("0")
    )
    early_start_age = (
        pension_result.scenarios[0].pension_start_age
        if has_pension and pension_result
        else 999
    )
    normal_start_age = (
        pension_result.scenarios[1].pension_start_age
        if has_pension and pension_result
        else 999
    )
    late_start_age = (
        pension_result.scenarios[2].pension_start_age
        if has_pension and pension_result
        else 999
    )

    nw = inputs.current_net_worth
    coast_nw = inputs.current_net_worth
    nw_early = inputs.current_net_worth
    nw_normal = inputs.current_net_worth
    nw_late = inputs.current_net_worth

    # Add starting point
    start_point = ProjectionPoint(
        age=inputs.current_age,
        year=current_year,
        month=current_month,
        net_worth=_decimal_round(nw, 0),
        coast_net_worth=_decimal_round(coast_nw, 0),
    )
    if has_pension:
        start_point.net_worth_early = _decimal_round(nw, 0)
        start_point.net_worth_normal = _decimal_round(nw, 0)
        start_point.net_worth_late = _decimal_round(nw, 0)
    points.append(start_point)

    def apply_drawdown(
        current_nw: Decimal,
        pension_monthly: Decimal,
        pension_start_age: int,
        age: Decimal,
    ) -> Decimal:
        if current_nw <= 0:
            return Decimal("0")
        val = current_nw * (1 + monthly_return) - monthly_expenses
        if age >= pension_start_age:
            val += pension_monthly
        return max(Decimal("0"), val)

    for m in range(1, total_months + 1):
        age = Decimal(inputs.current_age) + Decimal(m) / 12
        in_drawdown = has_pension and age >= fire_age

        if in_drawdown:
            nw_early = apply_drawdown(
                nw_early, early_pension_monthly, early_start_age, age
            )
            nw_normal = apply_drawdown(
                nw_normal, normal_pension_monthly, normal_start_age, age
            )
            nw_late = apply_drawdown(nw_late, late_pension_monthly, late_start_age, age)
            nw = nw_normal
        else:
            nw = nw * (1 + monthly_return) + inputs.monthly_contribution
            nw_early = nw
            nw_normal = nw
            nw_late = nw

        coast_nw = coast_nw * (1 + monthly_return)

        # Only add yearly points
        if m % 12 == 0:
            years_out = m // 12
            proj_month = current_month
            proj_year = current_year + years_out
            if proj_month > 12:
                proj_month -= 12
                proj_year += 1

            point = ProjectionPoint(
                age=inputs.current_age + years_out,
                year=proj_year,
                month=proj_month,
                net_worth=_decimal_round(nw, 0),
                coast_net_worth=_decimal_round(coast_nw, 0),
            )
            if has_pension:
                point.net_worth_early = _decimal_round(nw_early, 0)
                point.net_worth_normal = _decimal_round(nw_normal, 0)
                point.net_worth_late = _decimal_round(nw_late, 0)
            points.append(point)

    return points


# ---------------------------------------------------------------------------
# Main calculation
# ---------------------------------------------------------------------------


def calculate_fire(inputs: FireInputs) -> FireResult:
    """Calculate all FIRE metrics from inputs."""
    real_return_pct = inputs.annual_return_pct - inputs.inflation_pct
    real_return = real_return_pct / 100

    # Check if pension mode is active
    has_pension = inputs.pension_accrued_monthly is not None

    fire_number: Decimal
    pension_result: PensionResult | None = None

    if has_pension:
        pension_accrued = inputs.pension_accrued_monthly
        assert pension_accrued is not None  # checked by has_pension
        accrual_rate = inputs.pension_accrual_rate
        pension_full_age = inputs.pension_full_age
        monthly_salary = inputs.pension_monthly_salary or Decimal("0")

        retirement_age = Decimal(inputs.target_retirement_age)

        projected_monthly = calc_projected_monthly_pension(
            pension_accrued,
            inputs.current_age,
            retirement_age,
            monthly_salary,
            accrual_rate,
        )

        guarantee_enabled = inputs.pension_guarantee_enabled
        guarantee_amount = inputs.pension_guarantee_amount

        scenarios = generate_pension_scenarios(
            projected_monthly,
            pension_full_age,
            retirement_age,
            inputs.annual_expenses,
            inputs.safe_withdrawal_rate,
            real_return,
        )

        # Apply guarantee floor to each scenario's pension
        if guarantee_enabled:
            for scenario in scenarios:
                if scenario.monthly_pension < guarantee_amount:
                    scenario.monthly_pension = guarantee_amount
                    scenario.annual_pension = guarantee_amount * 12
                    scenario.pension_fire_number = _decimal_round(
                        calc_pension_fire_number(
                            inputs.annual_expenses,
                            scenario.annual_pension,
                            retirement_age,
                            scenario.pension_start_age,
                            inputs.safe_withdrawal_rate,
                            real_return,
                        ),
                        2,
                    )

        fire_number = _decimal_round(scenarios[1].pension_fire_number, 0)

        pension_coast_fire_number = calc_coast_fire_number(
            fire_number,
            real_return_pct,
            max(Decimal("0"), retirement_age - inputs.current_age),
        )

        crossover_age = (
            calc_guarantee_crossover_age(
                pension_accrued,
                inputs.current_age,
                monthly_salary,
                accrual_rate,
                guarantee_amount,
                pension_full_age + 3,
            )
            if guarantee_enabled
            else None
        )

        pension_result = PensionResult(
            projected_monthly_pension=_decimal_round(projected_monthly, 2),
            scenarios=scenarios,
            pension_coast_fire_number=_decimal_round(pension_coast_fire_number, 0),
            guarantee_active=guarantee_enabled and projected_monthly < guarantee_amount,
            guarantee_amount=guarantee_amount,
            crossover_age=crossover_age,
        )
    else:
        fire_number = _decimal_round(
            calc_fire_number(inputs.annual_expenses, inputs.safe_withdrawal_rate), 0
        )

    years_to_retirement = max(0, inputs.target_retirement_age - inputs.current_age)
    if has_pension and pension_result:
        coast_fire_number = pension_result.pension_coast_fire_number
    else:
        coast_fire_number = _decimal_round(
            calc_coast_fire_number(
                fire_number, real_return_pct, Decimal(years_to_retirement)
            ),
            0,
        )
    coast_fire_reached = inputs.current_net_worth >= coast_fire_number

    # Calculate years to FIRE - use pension-aware calculation when pension is active
    years_to_fire: Decimal | None

    if has_pension:
        pension_accrued = inputs.pension_accrued_monthly
        assert pension_accrued is not None
        pension_aware_result = calc_pension_aware_years_to_fire(
            inputs.current_net_worth,
            inputs.monthly_contribution,
            inputs.annual_expenses,
            real_return_pct,
            inputs.current_age,
            inputs.safe_withdrawal_rate,
            pension_accrued,
            inputs.pension_monthly_salary or Decimal("0"),
            inputs.pension_accrual_rate,
            inputs.pension_full_age,
            inputs.pension_guarantee_enabled,
            inputs.pension_guarantee_amount,
        )
        years_to_fire = pension_aware_result[0] if pension_aware_result else None
    else:
        years_to_fire = calc_years_to_fire(
            inputs.current_net_worth,
            inputs.monthly_contribution,
            fire_number,
            real_return_pct,
        )

    fire_age = (
        _decimal_round(Decimal(inputs.current_age) + years_to_fire, 1)
        if years_to_fire is not None
        else None
    )

    # Calculate Coast FIRE age: the age at which your NW (with contributions)
    # can compound to the FIRE number without further savings by retirement.
    coast_fire_age = (
        Decimal(inputs.current_age)
        if coast_fire_reached
        else calc_coast_fire_age(
            inputs.current_net_worth,
            inputs.monthly_contribution,
            fire_number,
            real_return_pct,
            inputs.current_age,
            inputs.target_retirement_age,
        )
    )

    # Generate projections
    life_expectancy = inputs.life_expectancy
    default_projection_years = min(
        max(years_to_retirement + 10, int(years_to_fire) + 5 if years_to_fire else 40),
        60,
    )
    projection_years = (
        max(life_expectancy - inputs.current_age + 2, default_projection_years)
        if has_pension
        else default_projection_years
    )
    projections = generate_projections(inputs, projection_years, pension_result)

    # Find when portfolio depletes (normal scenario hits 0)
    portfolio_depleted_age: Decimal | None = None
    if has_pension:
        for p in projections:
            if (
                p.age > inputs.target_retirement_age
                and p.net_worth_normal is not None
                and p.net_worth_normal <= 0
            ):
                portfolio_depleted_age = Decimal(p.age)
                break

    return FireResult(
        fire_number=fire_number,
        coast_fire_number=coast_fire_number,
        coast_fire_reached=coast_fire_reached,
        years_to_fire=(
            _decimal_round(years_to_fire, 1) if years_to_fire is not None else None
        ),
        fire_age=fire_age,
        coast_fire_age=coast_fire_age,
        on_track=years_to_fire is not None and years_to_fire <= years_to_retirement,
        portfolio_depleted_age=portfolio_depleted_age,
        projections=projections,
        pension=pension_result,
    )
