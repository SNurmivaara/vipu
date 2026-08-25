"""Financial Independence / Retire Early (FIRE) calculation utilities.

All monetary values are in EUR using Decimal for precision.
Return rates are annual percentages (e.g., 7 for 7%).
Inflation is an annual percentage (e.g., 2 for 2%).
"""

import re
from dataclasses import dataclass, field, replace
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
    # Value-weighted nominal return of the mix at this point. Rises over time
    # as the faster-growing groups take a larger share. Diagnostic only.
    blended_return_pct: Decimal | None = None
    # Age-specific FIRE numbers (present when pension is active)
    fire_number_at_age: Decimal | None = None
    coast_fire_number_at_age: Decimal | None = None
    # Pension drawdown projections (present when pension is active)
    net_worth_early: Decimal | None = None
    net_worth_normal: Decimal | None = None
    net_worth_late: Decimal | None = None


@dataclass
class FireResult:
    """Complete FIRE calculation results."""

    fire_number: Decimal
    # FIRE number if you retired *now* (at current age). In pension mode this
    # accounts for pension accrued so far and is independent of the target
    # retirement age; in simple mode it equals fire_number.
    fire_number_now: Decimal
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


def real_return_from_nominal(nominal_pct: Decimal, inflation_pct: Decimal) -> Decimal:
    """Convert a nominal annual return (%) to a real one via the Fisher relation.

    real = (1 + nominal) / (1 + inflation) - 1

    Subtracting inflation is the common approximation. It overstates the real
    return, and the error compounds over a projection: 8% at 3% inflation is
    4.854% real, not 5%.
    """
    inflation = inflation_pct / 100
    if inflation <= -1:
        # Deflation of 100% or more has no meaningful Fisher conversion.
        return nominal_pct
    return ((1 + nominal_pct / 100) / (1 + inflation) - 1) * 100


def monthly_rate(annual_pct: Decimal) -> Decimal:
    """Monthly rate equivalent to an annual one: (1 + annual)^(1/12) - 1.

    Dividing by 12 overstates growth, because it skips the compounding of the
    intervening months. Twelve of these steps reproduce the annual rate.
    """
    return _decimal_power(1 + annual_pct / 100, Decimal("1") / 12) - 1


# ---------------------------------------------------------------------------
# Portfolio state
# ---------------------------------------------------------------------------


@dataclass
class PortfolioGroup:
    """One asset group in the simulated portfolio.

    Rates are annual percentages. ``real_annual_pct`` is what the simulation
    compounds. ``nominal_annual_pct`` is carried only to report the blended
    return implied by the mix.
    """

    name: str
    balance: Decimal
    real_annual_pct: Decimal
    nominal_annual_pct: Decimal


class PortfolioState:
    """Per-group balances, each stepped monthly at its own rate.

    Compounding one blended rate holds the mix fixed. In reality the
    higher-returning groups compound faster, their share of the portfolio
    rises, and the blended return rises with them. Holding balances per group
    reproduces that drift without modelling it: there is no blended rate in
    the loop at all.
    """

    def __init__(
        self, groups: list[PortfolioGroup], contribution_group: str | None = None
    ) -> None:
        self._groups = groups
        self._monthly = [monthly_rate(g.real_annual_pct) for g in groups]
        # Where new money lands. Unset spreads it across the mix, which credits
        # contributions at the portfolio average.
        self._contribution_group = (
            contribution_group
            if any(g.name == contribution_group for g in groups)
            else None
        )

    @classmethod
    def single(cls, balance: Decimal, real_annual_pct: Decimal) -> "PortfolioState":
        """Degenerate one-group portfolio, equivalent to a scalar simulation."""
        return cls(
            [PortfolioGroup("Portfolio", balance, real_annual_pct, real_annual_pct)]
        )

    def clone(self) -> "PortfolioState":
        """Independent copy, for branching scenarios off a shared trajectory."""
        return PortfolioState(
            [replace(g) for g in self._groups], self._contribution_group
        )

    @property
    def contribution_group(self) -> str | None:
        return self._contribution_group

    @property
    def total(self) -> Decimal:
        return sum((g.balance for g in self._groups), Decimal("0"))

    @property
    def balances(self) -> dict[str, Decimal]:
        return {g.name: g.balance for g in self._groups}

    def step(self, flow: Decimal = Decimal("0")) -> None:
        """Grow every group by one month, then apply a net cash flow pro-rata."""
        for group, monthly in zip(self._groups, self._monthly, strict=True):
            group.balance = group.balance * (1 + monthly)
        self._apply_flow(flow)

    def _apply_flow(self, flow: Decimal) -> None:
        if flow == 0:
            return
        if flow > 0 and self._contribution_group is not None:
            for group in self._groups:
                if group.name == self._contribution_group:
                    group.balance += flow
                    return
        total = self.total
        if total <= 0:
            if flow < 0:
                # A withdrawal from an empty portfolio leaves it empty.
                self.deplete()
                return
            # Nothing to weight by, so spread the contribution evenly.
            share = flow / len(self._groups)
            for group in self._groups:
                group.balance += share
            return
        if flow < 0 and -flow >= total:
            self.deplete()
            return
        for group in self._groups:
            group.balance += flow * (group.balance / total)

    def deplete(self) -> None:
        """Zero every group. A depleted portfolio stays depleted."""
        for group in self._groups:
            group.balance = Decimal("0")

    def blended_return_pct(self) -> Decimal:
        """Value-weighted nominal return of the current mix.

        A diagnostic only. Once drift is modelled this is a property of the mix
        at an instant, not of the plan, so it is never used to compound.
        """
        total = Decimal("0")
        weighted = Decimal("0")
        for group in self._groups:
            if group.balance <= 0:
                continue
            weighted += group.balance * group.nominal_annual_pct
            total += group.balance
        return weighted / total if total > 0 else Decimal("0")

    def coast_value(self, years: Decimal) -> Decimal:
        """Value after ``years`` of growth with no further contributions.

        Sum of bᵢ(1 + rᵢ)ⁿ across the groups. Scaling every bucket leaves the
        mix unchanged, so this closed form needs no simulation. It exceeds the
        blended-rate result (1 + r̄)ⁿ by Jensen's inequality, and that gap is
        precisely the drift.
        """
        if years <= 0:
            return self.total
        return sum(
            (
                group.balance * _decimal_power(1 + group.real_annual_pct / 100, years)
                for group in self._groups
            ),
            Decimal("0"),
        )


# ---------------------------------------------------------------------------
# Input derivation from persisted state
#
# These derive FIRE inputs from net worth allocations and per-group return
# assumptions. They previously lived in the frontend (ForecastingPanel); kept
# here so the FIRE result is computed consistently on the backend.
# ---------------------------------------------------------------------------

# Default annual return assumptions (%), matched by group-name keyword.
_DEFAULT_RETURN_RULES: list[tuple[str, Decimal]] = [
    (r"invest|stock|equit|fund|etf", Decimal("7")),
    (r"real.?estate|property|home|house", Decimal("3")),
    (r"cash|saving|bank|deposit", Decimal("1")),
    (r"crypto|bitcoin|eth", Decimal("7")),
    (r"bond|fixed.?income", Decimal("3")),
]
_DEFAULT_RETURN_FALLBACK = Decimal("5")


def default_return_for_group(group_name: str) -> Decimal:
    """Default annual return assumption (%) for an asset group by name.

    Mirrors the frontend keyword matching so projections are unchanged.
    """
    lower = group_name.lower()
    for pattern, rate in _DEFAULT_RETURN_RULES:
        if re.search(pattern, lower):
            return rate
    return _DEFAULT_RETURN_FALLBACK


def resolve_group_return_rates(
    by_group: dict[str, float | Decimal],
    group_return_rates: dict[str, float | Decimal],
) -> dict[str, Decimal]:
    """Return the effective return rate (%) for each asset group.

    Uses the persisted override when present, otherwise the keyword default.
    """
    resolved: dict[str, Decimal] = {}
    for group in by_group:
        override = group_return_rates.get(group)
        resolved[group] = (
            Decimal(str(override))
            if override is not None
            else default_return_for_group(group)
        )
    return resolved


def weighted_return(
    by_group: dict[str, float | Decimal],
    group_return_rates: dict[str, float | Decimal],
) -> Decimal:
    """Portfolio-weighted annual return (%) from asset allocations.

    Only positive balances (assets) are weighted. Falls back to 7% when there
    are no assets to weight. Mirrors the frontend calcWeightedReturn.
    """
    total_value = Decimal("0")
    weighted_sum = Decimal("0")
    for group, amount in by_group.items():
        amount_dec = Decimal(str(amount))
        if amount_dec <= 0:
            continue  # only assets
        override = group_return_rates.get(group)
        rate = (
            Decimal(str(override))
            if override is not None
            else default_return_for_group(group)
        )
        weighted_sum += amount_dec * rate
        total_value += amount_dec
    return weighted_sum / total_value if total_value > 0 else Decimal("7")


def build_portfolio(
    base: Decimal,
    by_group: dict[str, float | Decimal],
    group_return_rates: dict[str, float | Decimal],
    inflation_pct: Decimal,
    fallback_return_pct: Decimal = Decimal("7"),
    contribution_group: str | None = None,
) -> PortfolioState:
    """Build a portfolio by spreading ``base`` across the asset groups by weight.

    Each group compounds at its own Fisher-real rate, so the mix drifts as the
    faster groups outgrow the slower ones.

    ``contribution_group`` names the group new savings land in. Left unset,
    contributions spread across the mix and so earn the portfolio average,
    which is rarely where the money actually goes.

    Note that ``base`` is net worth, so the groups currently carry the
    liabilities spread across them in proportion to assets. Giving liabilities
    their own balances is a separate change; this one only removes the fixed
    blended rate.
    """
    rates = resolve_group_return_rates(by_group, group_return_rates)
    positives = {
        name: Decimal(str(amount))
        for name, amount in by_group.items()
        if Decimal(str(amount)) > 0
    }
    total = sum(positives.values(), Decimal("0"))

    if total <= 0:
        return PortfolioState.single(
            base, real_return_from_nominal(fallback_return_pct, inflation_pct)
        )

    return PortfolioState(
        [
            PortfolioGroup(
                name=name,
                balance=base * (amount / total),
                real_annual_pct=real_return_from_nominal(rates[name], inflation_pct),
                nominal_annual_pct=rates[name],
            )
            for name, amount in positives.items()
        ],
        contribution_group,
    )


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
    portfolio: PortfolioState | None = None,
) -> Decimal:
    """Calculate Coast FIRE number.

    This is how much you need RIGHT NOW so that compound growth alone
    (no further contributions) reaches your FIRE number by retirement.

    With a portfolio, the growth factor is the mix-weighted sum of per-group
    factors, which is larger than the blended-rate factor and so asks for less
    capital today. Without one:

    CoastFIRE = FIRE_Number / (1 + realReturn)^yearsToRetirement
    """
    if years_to_retirement <= 0:
        return fire_number
    if portfolio is not None and portfolio.total > 0:
        growth_factor = portfolio.coast_value(years_to_retirement) / portfolio.total
    else:
        growth_factor = _decimal_power(
            1 + real_annual_return_pct / 100, years_to_retirement
        )
    return fire_number / growth_factor


def calc_years_to_fire(
    current_net_worth: Decimal,
    monthly_contribution: Decimal,
    fire_number: Decimal,
    real_annual_return_pct: Decimal,
    portfolio: PortfolioState | None = None,
) -> Decimal | None:
    """Calculate years to reach FIRE using iterative month-by-month simulation.

    Uses real (inflation-adjusted) returns.
    Returns None if FIRE is unreachable within 100 years.
    """
    if current_net_worth >= fire_number:
        return Decimal("0")

    state = (
        portfolio.clone()
        if portfolio is not None
        else PortfolioState.single(current_net_worth, real_annual_return_pct)
    )
    max_months = 100 * 12

    for m in range(1, max_months + 1):
        state.step(monthly_contribution)
        if state.total >= fire_number:
            return Decimal(m) / 12

    return None


def calc_coast_fire_age(
    current_net_worth: Decimal,
    monthly_contribution: Decimal,
    fire_number: Decimal,
    real_annual_return_pct: Decimal,
    current_age: int,
    target_retirement_age: int,
    portfolio: PortfolioState | None = None,
) -> Decimal | None:
    """Calculate the age at which you reach Coast FIRE.

    At each month, checks: can current NW (with contributions) compound to
    the FIRE number in the remaining time without further contributions?
    The check uses the mix at that month, so it accounts for drift.
    Returns None if unreachable before target retirement age.
    """
    total_months = round((target_retirement_age - current_age) * 12)

    if total_months <= 0:
        return None

    state = (
        portfolio.clone()
        if portfolio is not None
        else PortfolioState.single(current_net_worth, real_annual_return_pct)
    )

    # Check starting point
    years_to_retire = Decimal(target_retirement_age - current_age)
    if state.coast_value(years_to_retire) >= fire_number:
        return Decimal(current_age)

    for m in range(1, total_months + 1):
        state.step(monthly_contribution)
        age = Decimal(current_age) + Decimal(m) / 12
        years_remaining = Decimal(target_retirement_age) - age
        if years_remaining <= 0:
            break
        if state.coast_value(years_remaining) >= fire_number:
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
    portfolio: PortfolioState | None = None,
) -> tuple[Decimal, Decimal] | None:
    """Calculate earliest FIRE age with pension awareness.

    At each simulated month, calculates what the FIRE number would be
    if you retired at that age (accounting for pension accrued up to that point).

    Returns tuple of (years_to_fire, fire_number_at_that_age) or None if unreachable.
    """
    real_return = real_annual_return_pct / 100
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

    state = (
        portfolio.clone()
        if portfolio is not None
        else PortfolioState.single(current_net_worth, real_annual_return_pct)
    )

    for m in range(1, max_months + 1):
        state.step(monthly_contribution)
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

        if state.total >= fire_number_at_age:
            return (Decimal(m) / 12, fire_number_at_age)

    return None


# ---------------------------------------------------------------------------
# Projection generation
# ---------------------------------------------------------------------------


def generate_projections(
    inputs: FireInputs,
    years_ahead: int = 40,
    pension_result: PensionResult | None = None,
    fire_number_at_target: Decimal | None = None,
    portfolio: PortfolioState | None = None,
) -> list[ProjectionPoint]:
    """Generate year-by-year projections for net worth growth.

    When pension inputs are present, extends past FIRE age with drawdown projections
    and calculates age-specific FIRE numbers for each projection point.
    """
    real_return_pct = real_return_from_nominal(
        inputs.annual_return_pct, inputs.inflation_pct
    )
    real_return = real_return_pct / 100
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

    # Target retirement age for Coast FIRE calculations
    target_retirement_age = inputs.target_retirement_age

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

    base_state = (
        portfolio
        if portfolio is not None
        else PortfolioState.single(inputs.current_net_worth, real_return_pct)
    )
    accum = base_state.clone()
    coast_state = base_state.clone()
    # Cloned off the accumulation trajectory at FIRE age, where they diverge.
    scenario_states: dict[PensionLabel, PortfolioState] | None = None

    # Helper to calculate age-specific FIRE number for pension mode
    def calc_fire_number_for_projection_age(retirement_age: Decimal) -> Decimal:
        """Calculate FIRE number for a specific retirement age."""
        if not has_pension:
            return calc_fire_number(inputs.annual_expenses, inputs.safe_withdrawal_rate)

        return calc_fire_number_for_age(
            retirement_age,
            inputs.annual_expenses,
            inputs.safe_withdrawal_rate,
            real_return,
            inputs.pension_accrued_monthly or Decimal("0"),
            inputs.current_age,
            inputs.pension_monthly_salary or Decimal("0"),
            inputs.pension_accrual_rate,
            inputs.pension_full_age,
            inputs.pension_guarantee_enabled,
            inputs.pension_guarantee_amount,
        )

    def calc_coast_fire_number_for_projection_age(projection_age: Decimal) -> Decimal:
        """Calculate Coast FIRE number for a specific projection age.

        In pension mode:
            Coast FIRE at age X = FIRE_number_at_target / (1 + r)^(target_age - X)
            This represents: "At age X, how much do you need to coast to target?"

        In non-pension mode: Coast FIRE is constant (result.coast_fire_number).
        """
        if fire_number_at_target is None:
            # Fallback for non-pension mode or when not provided
            # Calculate constant Coast FIRE
            years_to_retirement = max(
                Decimal("0"),
                Decimal(target_retirement_age) - Decimal(inputs.current_age),
            )
            fire_num = calc_fire_number(
                inputs.annual_expenses, inputs.safe_withdrawal_rate
            )
            return calc_coast_fire_number(
                fire_num, real_return_pct, years_to_retirement, coast_state
            )

        # Pension mode: Coast FIRE at age X =
        #     fire_number_at_target / (1 + r)^(target_age - X)
        years_to_retirement = max(
            Decimal("0"), Decimal(target_retirement_age) - projection_age
        )
        return calc_coast_fire_number(
            fire_number_at_target,
            real_return_pct,
            years_to_retirement,
            coast_state,
        )

    # Add starting point
    start_age = inputs.current_age
    start_fire_number = calc_fire_number_for_projection_age(Decimal(start_age))
    start_coast_fire_number = calc_coast_fire_number_for_projection_age(
        Decimal(start_age)
    )

    start_nw = accum.total
    start_point = ProjectionPoint(
        age=start_age,
        year=current_year,
        month=current_month,
        net_worth=_decimal_round(start_nw, 0),
        coast_net_worth=_decimal_round(coast_state.total, 0),
        blended_return_pct=_decimal_round(accum.blended_return_pct(), 2),
        fire_number_at_age=(
            _decimal_round(start_fire_number, 0) if has_pension else None
        ),
        coast_fire_number_at_age=(
            _decimal_round(start_coast_fire_number, 0) if has_pension else None
        ),
    )
    if has_pension:
        start_point.net_worth_early = _decimal_round(start_nw, 0)
        start_point.net_worth_normal = _decimal_round(start_nw, 0)
        start_point.net_worth_late = _decimal_round(start_nw, 0)
    points.append(start_point)

    def apply_drawdown(
        state: PortfolioState,
        pension_monthly: Decimal,
        pension_start_age: int,
        age: Decimal,
    ) -> None:
        """Spend down one scenario by a month, pro-rata across the groups."""
        if state.total <= 0:
            state.deplete()
            return
        flow = -monthly_expenses
        if age >= pension_start_age:
            flow += pension_monthly
        state.step(flow)

    for m in range(1, total_months + 1):
        age = Decimal(inputs.current_age) + Decimal(m) / 12
        in_drawdown = has_pension and age >= fire_age

        if in_drawdown:
            if scenario_states is None:
                scenario_states = {
                    "early": accum.clone(),
                    "normal": accum.clone(),
                    "late": accum.clone(),
                }
            apply_drawdown(
                scenario_states["early"], early_pension_monthly, early_start_age, age
            )
            apply_drawdown(
                scenario_states["normal"], normal_pension_monthly, normal_start_age, age
            )
            apply_drawdown(
                scenario_states["late"], late_pension_monthly, late_start_age, age
            )
            nw = scenario_states["normal"].total
            nw_early = scenario_states["early"].total
            nw_normal = nw
            nw_late = scenario_states["late"].total
            mix_state = scenario_states["normal"]
        else:
            accum.step(inputs.monthly_contribution)
            nw = accum.total
            nw_early = nw
            nw_normal = nw
            nw_late = nw
            mix_state = accum

        coast_state.step()

        # Only add yearly points
        if m % 12 == 0:
            years_out = m // 12
            proj_month = current_month
            proj_year = current_year + years_out
            if proj_month > 12:
                proj_month -= 12
                proj_year += 1

            # Calculate age-specific FIRE numbers for this projection age
            proj_age = inputs.current_age + years_out
            proj_age_decimal = Decimal(proj_age)
            fire_number_at_age = calc_fire_number_for_projection_age(proj_age_decimal)
            coast_fire_number_at_age = calc_coast_fire_number_for_projection_age(
                proj_age_decimal
            )

            point = ProjectionPoint(
                age=proj_age,
                year=proj_year,
                month=proj_month,
                net_worth=_decimal_round(nw, 0),
                coast_net_worth=_decimal_round(coast_state.total, 0),
                blended_return_pct=_decimal_round(mix_state.blended_return_pct(), 2),
                fire_number_at_age=(
                    _decimal_round(fire_number_at_age, 0) if has_pension else None
                ),
                coast_fire_number_at_age=(
                    _decimal_round(coast_fire_number_at_age, 0) if has_pension else None
                ),
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


def calculate_fire(
    inputs: FireInputs, portfolio: PortfolioState | None = None
) -> FireResult:
    """Calculate all FIRE metrics from inputs.

    Pass a ``portfolio`` to compound each asset group at its own rate, so the
    mix drifts toward the faster groups. Without one the whole balance
    compounds at ``inputs.annual_return_pct``, which is the degenerate
    single-group case.
    """
    real_return_pct = real_return_from_nominal(
        inputs.annual_return_pct, inputs.inflation_pct
    )
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

        # FIRE number if you retired at the current age. Accounts for pension
        # accrued so far but not for future accrual, so it does not move when
        # the target retirement age changes. This is the headline figure —
        # "what you'd need to FIRE right now".
        fire_number_now = _decimal_round(
            calc_fire_number_for_age(
                Decimal(inputs.current_age),
                inputs.annual_expenses,
                inputs.safe_withdrawal_rate,
                real_return,
                pension_accrued,
                inputs.current_age,
                monthly_salary,
                accrual_rate,
                pension_full_age,
                guarantee_enabled,
                guarantee_amount,
            ),
            0,
        )

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
        # No pension: the FIRE number is independent of retirement age, so the
        # "retire now" figure is identical.
        fire_number_now = fire_number

    years_to_retirement = max(0, inputs.target_retirement_age - inputs.current_age)
    if has_pension and pension_result:
        coast_fire_number = pension_result.pension_coast_fire_number
    else:
        coast_fire_number = _decimal_round(
            calc_coast_fire_number(
                fire_number, real_return_pct, Decimal(years_to_retirement), portfolio
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
            portfolio,
        )
        years_to_fire = pension_aware_result[0] if pension_aware_result else None
    else:
        years_to_fire = calc_years_to_fire(
            inputs.current_net_worth,
            inputs.monthly_contribution,
            fire_number,
            real_return_pct,
            portfolio,
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
            portfolio,
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
    projections = generate_projections(
        inputs, projection_years, pension_result, fire_number, portfolio
    )

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
        fire_number_now=fire_number_now,
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
