"""Tools for planning ahead: what-ifs, forecasts and the assumptions behind them.

Reading a projection is not planning. Planning is changing an assumption and
seeing what moves, which is what project_fire is for: it computes from a posted
body and stores nothing, so a scenario can be tried without committing to it.
"""

from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from vipu_mcp.client import VipuClient

PROJECT_FIRE_DESCRIPTION = """\
Try a what-if against the FIRE projection. Nothing is stored, so this is safe \
to run repeatedly with different assumptions.

Every parameter is optional and defaults to the figure the stored projection \
was built from, so "what if I save 300 more a month?" is one call with one \
argument. Report the `delta` block, not the raw numbers: "that pulls FIRE \
forward by 2.5 years" is the answer to the question that was asked.

The delta compares the scenario against a baseline run of the same simple \
model, both computed here, so it measures only what the change did. Those \
absolute figures will not match get_fire_projection: the app's headline \
projection compounds each asset group at its own rate and amortises debt \
separately, while this one grows a single pot at one rate. Trust the \
difference, and quote get_fire_projection for levels.

`annual_expenses` is the retirement spending the FIRE number is built from, not \
necessarily today's expenses. `years_to_fire` is when the portfolio covers it, \
which is when work becomes optional, not the planned retirement age.

To make a scenario permanent, call update_forecasting_settings.\
"""

FORECAST_NET_WORTH_DESCRIPTION = """\
Project net worth forward from the recent trend in the snapshot history.

This is a straight-line extrapolation of what has actually been happening, not \
a compounding model: `period` picks how far back to measure the monthly change \
rate (month, quarter, half_year, year) and that rate is then repeated forward. \
A short lookback tracks recent behaviour and a long one smooths it.

Different question from get_fire_projection, which compounds returns and \
assumes a savings rate. This one answers "if the last few months continue, \
where does that put me?".

`data_points_used` says how many snapshots the rate came from. With one or none \
there is no trend to project and the answer is flat.\
"""

FORECASTING_SETTINGS_DESCRIPTION = """\
Change the assumptions behind every FIRE number the app reports.

This is a write to stored settings, not a scenario: inflation, the safe \
withdrawal rate, ages, the savings and expenses overrides, the pension block \
and the per-group return rates all feed get_fire_projection, the wealth page \
and the summary. Changing one changes what the app says everywhere. For trying \
a figure out, use project_fire instead.

Two are overrides rather than values: `monthly_savings_override` replaces the \
budget's own monthly surplus, and `annual_expenses_override` replaces monthly \
expenses times twelve. Pass null to clear either and go back to the derived \
figure.

`group_return_rates` maps net worth group names to expected annual returns. \
Each group compounds at its own rate, so the mix drifts toward the faster \
groups over the projection.

Returns the settings plus the recomputed projection, so the effect is visible \
in the same call.\
"""

BUDGET_SETTINGS_DESCRIPTION = """\
Change the default tax percentage or the payday day of month.

`payday_day` is structural: the budget month rolls over on payday rather than \
on the 1st, so changing it moves the boundaries of both pay periods and \
therefore every period total and the cash low point. Returns the recomputed \
period boundaries so the shift is visible.

`tax_percentage` is the default applied to taxed income lines that do not carry \
their own rate.\
"""

# The stored settings each what-if parameter falls back to, and the key it goes
# under in the calculate body.
_SETTING_FALLBACKS = {
    "inflation_pct": "inflation_pct",
    "current_age": "current_age",
    "target_retirement_age": "target_retirement_age",
    "safe_withdrawal_rate": "safe_withdrawal_rate",
    "pension_accrual_rate": "pension_accrual_rate",
    "pension_full_age": "pension_full_age",
    "pension_guarantee_enabled": "pension_guarantee_enabled",
    "pension_guarantee_amount": "pension_guarantee_amount",
    "life_expectancy": "life_expectancy",
    "capital_gains_tax_pct": "capital_gains_tax_pct",
    "taxable_gain_pct": "taxable_gain_pct",
    "pension_tax_pct": "pension_tax_pct",
}


def _delta(scenario: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    """What the scenario moves, against an unchanged run of the same model.

    Years are the headline: a FIRE number changing by 40 000 means little on its
    own, while "2.5 years earlier" is the answer to the question that was asked.
    """

    def difference(key: str) -> float | None:
        new, old = scenario.get(key), baseline.get(key)
        if new is None or old is None:
            return None
        return round(float(new) - float(old), 2)

    years = difference("years_to_fire")
    return {
        "years_to_fire": {
            "from": baseline.get("years_to_fire"),
            "to": scenario.get("years_to_fire"),
            "change": years,
            # Stated in words because the sign is easy to read backwards: a
            # negative change to years_to_fire is the good direction.
            "summary": (
                "not reachable in either case"
                if years is None and scenario.get("years_to_fire") is None
                else "now reachable" if years is None else _years_phrase(years)
            ),
        },
        "fire_age": {
            "from": baseline.get("fire_age"),
            "to": scenario.get("fire_age"),
            "change": difference("fire_age"),
        },
        "fire_number": {
            "from": baseline.get("fire_number"),
            "to": scenario.get("fire_number"),
            "change": difference("fire_number"),
        },
        "coast_fire_number": {
            "from": baseline.get("coast_fire_number"),
            "to": scenario.get("coast_fire_number"),
            "change": difference("coast_fire_number"),
        },
    }


def _years_phrase(change: float) -> str:
    if change == 0:
        return "no change"
    direction = "earlier" if change < 0 else "later"
    return f"{abs(change)} years {direction}"


def register(server: MCPServer, client: VipuClient, read_only: bool = False) -> None:
    """Register the planning tools on ``server``.

    The two what-if tools always register: they compute and store nothing. The
    two update_* tools write stored settings and stay behind the flag.
    """

    @server.tool(
        name="project_fire",
        title="What-if FIRE projection",
        description=PROJECT_FIRE_DESCRIPTION,
        annotations=ToolAnnotations(
            # POST /api/forecasting/calculate computes and stores nothing.
            read_only_hint=True,
            idempotent_hint=True,
        ),
    )
    def project_fire(
        monthly_contribution: float | None = None,
        annual_expenses: float | None = None,
        annual_return_pct: float | None = None,
        current_net_worth: float | None = None,
        inflation_pct: float | None = None,
        current_age: int | None = None,
        target_retirement_age: int | None = None,
        safe_withdrawal_rate: float | None = None,
        life_expectancy: int | None = None,
        pension_accrued_monthly: float | None = None,
        pension_monthly_salary: float | None = None,
    ) -> dict[str, Any]:
        """Run a scenario and report what it moves."""
        stored = client.get_projection()
        derived = stored["derived"]
        settings = client.get_forecasting_settings()

        overrides: dict[str, Any] = {
            "current_net_worth": current_net_worth,
            "monthly_contribution": monthly_contribution,
            "annual_expenses": annual_expenses,
            "annual_return_pct": annual_return_pct,
            "inflation_pct": inflation_pct,
            "current_age": current_age,
            "target_retirement_age": target_retirement_age,
            "safe_withdrawal_rate": safe_withdrawal_rate,
            "life_expectancy": life_expectancy,
            "pension_accrued_monthly": pension_accrued_monthly,
            "pension_monthly_salary": pension_monthly_salary,
        }

        # Everything not named falls back to what the stored projection was
        # actually computed from, so a one-argument call is a clean comparison
        # rather than a different projection with one field in common.
        body: dict[str, Any] = {
            "current_net_worth": derived["current_net_worth"],
            "monthly_contribution": derived["monthly_savings"],
            "annual_expenses": derived["annual_expenses"],
            "annual_return_pct": derived["weighted_return_pct"],
        }
        for field, setting in _SETTING_FALLBACKS.items():
            body[field] = settings[setting]
        if derived["pension_active"]:
            body["pension_accrued_monthly"] = settings["pension_accrued_monthly"]
            body["pension_monthly_salary"] = derived["pension_monthly_salary"]

        changed = {
            field: value for field, value in overrides.items() if value is not None
        }

        # Baseline through the same endpoint rather than the stored projection.
        # GET /api/forecasting/projection compounds each asset group at its own
        # rate and amortises debt separately; POST /api/forecasting/calculate
        # grows one pot at one rate. Comparing across the two would attribute
        # the difference between the models to the change being tested.
        baseline = client.calculate_fire(body)
        scenario = client.calculate_fire({**body, **changed}) if changed else baseline

        for result in (baseline, scenario):
            # The month-by-month walk is hundreds of rows of no use here.
            result.pop("projections", None)

        return {
            "scenario": scenario,
            "baseline": baseline,
            "inputs_used": {**body, **changed},
            "inputs_changed": changed,
            "delta": _delta(scenario, baseline),
            "stored_nothing": True,
            "stored_projection_years_to_fire": stored["years_to_fire"],
        }

    @server.tool(
        name="forecast_net_worth",
        title="Net worth forecast",
        description=FORECAST_NET_WORTH_DESCRIPTION,
        annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True),
    )
    def forecast_net_worth(
        period: str = "quarter", months_ahead: int = 12
    ) -> dict[str, Any]:
        """Straight-line projection from the recent snapshot trend."""
        return client.forecast_net_worth(period, months_ahead)

    if read_only:
        return

    @server.tool(
        name="update_forecasting_settings",
        title="Update FIRE assumptions",
        description=FORECASTING_SETTINGS_DESCRIPTION,
        annotations=ToolAnnotations(
            read_only_hint=False, destructive_hint=False, idempotent_hint=True
        ),
    )
    def update_forecasting_settings(
        inflation_pct: float | None = None,
        safe_withdrawal_rate: float | None = None,
        current_age: int | None = None,
        target_retirement_age: int | None = None,
        life_expectancy: int | None = None,
        monthly_savings_override: float | None = None,
        annual_expenses_override: float | None = None,
        clear_monthly_savings_override: bool = False,
        clear_annual_expenses_override: bool = False,
        pension_accrued_monthly: float | None = None,
        pension_monthly_salary_override: float | None = None,
        pension_accrual_rate: float | None = None,
        pension_full_age: int | None = None,
        pension_guarantee_enabled: bool | None = None,
        pension_guarantee_amount: float | None = None,
        capital_gains_tax_pct: float | None = None,
        taxable_gain_pct: float | None = None,
        pension_tax_pct: float | None = None,
        group_return_rates: dict[str, float] | None = None,
        contribution_group: str | None = None,
        swr_excluded_groups: list[str] | None = None,
    ) -> dict[str, Any]:
        """Change the stored FIRE assumptions and report the new projection."""
        fields: dict[str, Any] = {
            "inflation_pct": inflation_pct,
            "safe_withdrawal_rate": safe_withdrawal_rate,
            "current_age": current_age,
            "target_retirement_age": target_retirement_age,
            "life_expectancy": life_expectancy,
            "monthly_savings_override": monthly_savings_override,
            "annual_expenses_override": annual_expenses_override,
            "pension_accrued_monthly": pension_accrued_monthly,
            "pension_monthly_salary_override": pension_monthly_salary_override,
            "pension_accrual_rate": pension_accrual_rate,
            "pension_full_age": pension_full_age,
            "pension_guarantee_enabled": pension_guarantee_enabled,
            "pension_guarantee_amount": pension_guarantee_amount,
            "capital_gains_tax_pct": capital_gains_tax_pct,
            "taxable_gain_pct": taxable_gain_pct,
            "pension_tax_pct": pension_tax_pct,
            "group_return_rates": group_return_rates,
            "contribution_group": contribution_group,
            "swr_excluded_groups": swr_excluded_groups,
        }
        payload = {key: value for key, value in fields.items() if value is not None}

        # Clearing needs an explicit null, which an omitted argument cannot
        # express: None already means "leave it alone".
        if clear_monthly_savings_override:
            payload["monthly_savings_override"] = None
        if clear_annual_expenses_override:
            payload["annual_expenses_override"] = None

        before = client.get_projection()
        settings = client.update_forecasting_settings(payload)
        after = client.get_projection()
        after.pop("projections", None)

        return {
            "settings": settings,
            "changed": sorted(payload),
            "projection": after,
            "delta": _delta(after, before),
        }

    @server.tool(
        name="update_budget_settings",
        title="Update budget settings",
        description=BUDGET_SETTINGS_DESCRIPTION,
        annotations=ToolAnnotations(
            read_only_hint=False, destructive_hint=False, idempotent_hint=True
        ),
    )
    def update_budget_settings(
        tax_percentage: float | None = None, payday_day: int | None = None
    ) -> dict[str, Any]:
        """Change the default tax rate or the payday, and report the effect."""
        payload: dict[str, Any] = {}
        if tax_percentage is not None:
            payload["tax_percentage"] = tax_percentage
        if payday_day is not None:
            payload["payday_day"] = payday_day

        settings = client.update_budget_settings(payload)
        totals = client.get_budget()["totals"]
        return {
            "settings": settings,
            "changed": sorted(payload),
            "next_payday": totals["next_payday"],
            "period_current": totals["period_current"],
            "period_next": totals["period_next"],
            "monthly_surplus": totals["monthly_surplus"],
            "cash_low_point": totals["cash_low_point"],
        }
