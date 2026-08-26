"""Tests for FIRE calculation utilities."""

from decimal import Decimal

from app.fire import (
    FireInputs,
    build_portfolio,
    calc_coast_fire_age,
    calc_coast_fire_number,
    calc_fire_number,
    calc_guarantee_crossover_age,
    calc_pension_adjustment,
    calc_pension_fire_number,
    calc_projected_monthly_pension,
    calc_years_to_fire,
    calculate_fire,
    default_return_for_group,
    generate_pension_scenarios,
    monthly_rate,
    pv_annuity,
    real_return_from_nominal,
    resolve_group_return_rates,
    weighted_return,
)


class TestRateConversions:
    """Nominal-to-real and annual-to-monthly rate conversions (issue #98)."""

    def test_fisher_conversion(self):
        """8% nominal at 3% inflation is 4.854% real, not the 5% of subtraction."""
        result = real_return_from_nominal(Decimal("8"), Decimal("3"))

        assert abs(result / 100 - Decimal("0.04854")) < Decimal("0.000005")
        assert result / 100 != Decimal("0.05")

    def test_fisher_is_below_subtraction(self):
        """Subtraction overstates the real return whenever inflation is positive."""
        for nominal, inflation in [("8", "3"), ("6.1", "3"), ("5.5", "2")]:
            fisher = real_return_from_nominal(Decimal(nominal), Decimal(inflation))
            assert fisher < Decimal(nominal) - Decimal(inflation)

    def test_fisher_zero_inflation_is_identity(self):
        assert real_return_from_nominal(Decimal("7"), Decimal("0")) == Decimal("7")

    def test_twelve_monthly_steps_reproduce_annual(self):
        """Monthly compounding round-trips to the annual rate."""
        for annual in [Decimal("8"), Decimal("4.854368932038835"), Decimal("-2")]:
            compounded = (1 + monthly_rate(annual)) ** 12 - 1
            assert abs(compounded - annual / 100) < Decimal("1e-12")

    def test_monthly_rate_is_geometric_not_arithmetic(self):
        """annual/12 skips intra-year compounding and overstates each step."""
        assert monthly_rate(Decimal("8")) < Decimal("8") / 100 / 12


class TestPortfolioDrift:
    """Per-group compounding and the weight drift it produces (issue #98)."""

    def _two_group_inputs(self, **overrides):
        defaults = dict(
            current_net_worth=Decimal("100000"),
            monthly_contribution=Decimal("0"),
            annual_expenses=Decimal("40000"),
            annual_return_pct=Decimal("4.5"),  # value-weighted 8% and 1%
            inflation_pct=Decimal("0"),
            current_age=30,
            target_retirement_age=65,
            safe_withdrawal_rate=Decimal("4"),
        )
        defaults.update(overrides)
        return FireInputs(**defaults)

    def _two_group_portfolio(self, base=Decimal("100000")):
        return build_portfolio(
            base,
            {"Equities": 50000, "Cash": 50000},
            {"Equities": 8, "Cash": 1},
            Decimal("0"),
        )

    def test_blended_return_rises_with_drift(self):
        """Zero contributions, 8% and 1%: the blended return climbs (issue #98).

        The faster group compounds into a larger share of the portfolio, so the
        return the mix implies rises even though no group's rate changes.
        """
        result = calculate_fire(self._two_group_inputs(), self._two_group_portfolio())

        by_age = {p.age: p.blended_return_pct for p in result.projections}

        assert by_age[30] == Decimal("4.50")
        assert by_age[50] > by_age[30]
        assert by_age[50] < Decimal("8")  # bounded by the fastest group

    def test_drift_beats_a_fixed_blended_rate(self):
        """Per-group compounding outgrows one held-constant blended rate."""
        inputs = self._two_group_inputs()

        drifted = calculate_fire(inputs, self._two_group_portfolio())
        fixed = calculate_fire(inputs)

        drifted_at_50 = next(p.net_worth for p in drifted.projections if p.age == 50)
        fixed_at_50 = next(p.net_worth for p in fixed.projections if p.age == 50)
        assert drifted_at_50 > fixed_at_50

    def test_coast_closed_form_matches_simulation(self):
        """Jensen's closed form agrees with a zero-contribution simulation."""
        portfolio = self._two_group_portfolio()
        years = Decimal("20")

        closed_form = portfolio.coast_value(years)

        simulated = portfolio.clone()
        for _ in range(int(years) * 12):
            simulated.step()

        assert abs(closed_form - simulated.total) / closed_form < Decimal("1e-9")

    def test_coast_value_exceeds_blended_rate_growth(self):
        """The Jensen gap: the mix grows faster than its blended rate implies."""
        portfolio = self._two_group_portfolio()
        years = Decimal("20")

        blended_growth = Decimal("100000") * (Decimal("1.045") ** 20)

        assert portfolio.coast_value(years) > blended_growth

    def test_single_group_reproduces_scalar_path(self):
        """Degenerate case: one group, no liabilities, matches the scalar model."""
        inputs = self._two_group_inputs(
            annual_return_pct=Decimal("7"), inflation_pct=Decimal("2")
        )
        portfolio = build_portfolio(
            Decimal("100000"), {"Investments": 100000}, {"Investments": 7}, Decimal("2")
        )

        with_portfolio = calculate_fire(inputs, portfolio)
        scalar = calculate_fire(inputs)

        assert with_portfolio.fire_number == scalar.fire_number
        assert with_portfolio.coast_fire_number == scalar.coast_fire_number
        assert with_portfolio.years_to_fire == scalar.years_to_fire
        assert [p.net_worth for p in with_portfolio.projections] == [
            p.net_worth for p in scalar.projections
        ]

    def test_routing_contributions_beats_the_portfolio_average(self):
        """Routing savings to an above-average group raises terminal wealth.

        Without a destination, new money is credited at the portfolio average,
        which is not where contributions actually go (issue #98).
        """
        inputs = self._two_group_inputs(monthly_contribution=Decimal("1000"))

        routed = calculate_fire(
            inputs,
            build_portfolio(
                Decimal("100000"),
                {"Equities": 50000, "Cash": 50000},
                {"Equities": 8, "Cash": 1},
                Decimal("0"),
                contribution_group="Equities",
            ),
        )
        pro_rata = calculate_fire(inputs, self._two_group_portfolio())

        routed_at_65 = next(p.net_worth for p in routed.projections if p.age == 65)
        pro_rata_at_65 = next(p.net_worth for p in pro_rata.projections if p.age == 65)
        assert routed_at_65 > pro_rata_at_65

    def test_routing_to_a_below_average_group_lowers_wealth(self):
        """Routing is directional, not a free uplift."""
        inputs = self._two_group_inputs(monthly_contribution=Decimal("1000"))

        to_cash = calculate_fire(
            inputs,
            build_portfolio(
                Decimal("100000"),
                {"Equities": 50000, "Cash": 50000},
                {"Equities": 8, "Cash": 1},
                Decimal("0"),
                contribution_group="Cash",
            ),
        )
        pro_rata = calculate_fire(inputs, self._two_group_portfolio())

        cash_at_65 = next(p.net_worth for p in to_cash.projections if p.age == 65)
        pro_rata_at_65 = next(p.net_worth for p in pro_rata.projections if p.age == 65)
        assert cash_at_65 < pro_rata_at_65

    def test_unknown_contribution_group_falls_back_to_pro_rata(self):
        """A stale group name must not silently swallow contributions."""
        portfolio = build_portfolio(
            Decimal("100000"),
            {"Equities": 50000, "Cash": 50000},
            {"Equities": 8, "Cash": 1},
            Decimal("0"),
            contribution_group="Deleted Group",
        )

        assert portfolio.contribution_group is None

        portfolio.step(Decimal("1000"))
        assert portfolio.total > Decimal("100000")

    def test_coast_number_is_lower_under_drift(self):
        """Drift means less capital is needed today to coast to the target."""
        portfolio = self._two_group_portfolio()

        with_drift = calc_coast_fire_number(
            Decimal("1000000"), Decimal("4.5"), Decimal("20"), portfolio
        )
        without = calc_coast_fire_number(
            Decimal("1000000"), Decimal("4.5"), Decimal("20")
        )

        assert with_drift < without


class TestLiabilities:
    """Debt carried with its own terms rather than as an opaque balance (#98)."""

    def _portfolio(self, rate_pct=3, payment=800, debt=120000):
        return build_portfolio(
            Decimal("200000"),
            {"Equities": 150000, "Cash": 50000},
            {"Equities": 8, "Cash": 1},
            Decimal("0"),
            liabilities_by_group={"Mortgage": debt},
            liability_terms={
                "Mortgage": {"rate_pct": rate_pct, "monthly_payment": payment}
            },
        )

    def test_net_worth_matches_the_snapshot_at_the_start(self):
        """Gross assets less debt reproduces the net worth it replaced."""
        portfolio = self._portfolio()

        assert portfolio.assets_total == Decimal("200000")
        assert portfolio.liabilities_total == Decimal("120000")
        assert portfolio.total == Decimal("80000")

    def test_debt_amortises_instead_of_compounding_at_the_asset_rate(self):
        """The balance falls. Applying the blended rate to net worth grew it."""
        portfolio = self._portfolio()

        for _ in range(12):
            portfolio.step()

        assert portfolio.liabilities_total < Decimal("120000")

    def test_payoff_frees_the_payment_into_contributions(self):
        """Once the loan clears, its payment starts compounding instead."""
        portfolio = build_portfolio(
            Decimal("10000"),
            {"Cash": 10000},
            {"Cash": 0},
            Decimal("0"),
            liabilities_by_group={"Loan": 1000},
            liability_terms={"Loan": {"rate_pct": 0, "monthly_payment": 500}},
        )

        portfolio.step()
        portfolio.step()
        assert portfolio.liabilities_total == Decimal("0")
        assets_at_payoff = portfolio.assets_total

        portfolio.step()
        assert portfolio.assets_total == assets_at_payoff + Decimal("500")

    def test_payment_below_interest_warns(self):
        """A balance that outgrows its payment is flagged, not projected."""
        portfolio = build_portfolio(
            Decimal("100000"),
            {"Cash": 100000},
            {"Cash": 1},
            Decimal("0"),
            liabilities_by_group={"Card": 1000},
            liability_terms={"Card": {"rate_pct": 20, "monthly_payment": 5}},
        )

        assert portfolio.liability_warnings() == [
            {"code": "negative_amortization", "group": "Card"}
        ]

    def test_serviceable_debt_does_not_warn(self):
        assert self._portfolio().liability_warnings() == []

    def test_negative_amortization_terminates_the_solve(self):
        """The solve returns unreachable rather than running away."""
        inputs = FireInputs(
            current_net_worth=Decimal("0"),
            monthly_contribution=Decimal("0"),
            annual_expenses=Decimal("40000"),
            annual_return_pct=Decimal("1"),
            inflation_pct=Decimal("0"),
            current_age=30,
            target_retirement_age=65,
            safe_withdrawal_rate=Decimal("4"),
        )
        portfolio = build_portfolio(
            Decimal("1000"),
            {"Cash": 1000},
            {"Cash": 1},
            Decimal("0"),
            liabilities_by_group={"Card": 10000},
            liability_terms={"Card": {"rate_pct": 20, "monthly_payment": 1}},
        )

        result = calculate_fire(inputs, portfolio)

        assert result.years_to_fire is None
        assert result.warnings == [{"code": "negative_amortization", "group": "Card"}]

    def test_untermed_debt_erodes_with_inflation(self):
        """A liability with no terms holds nominally, so inflation shrinks it."""
        portfolio = build_portfolio(
            Decimal("100000"),
            {"Cash": 100000},
            {"Cash": 0},
            Decimal("3"),
            liabilities_by_group={"Loan": 50000},
        )

        for _ in range(12):
            portfolio.step()

        assert portfolio.liabilities_total < Decimal("50000")
        assert portfolio.liabilities_total > Decimal("48000")


class TestSwrExclusion:
    """Groups that count toward net worth but cannot fund a withdrawal (#98)."""

    def _portfolio(self, excluded=None):
        return build_portfolio(
            Decimal("400000"),
            {"Investments": 200000, "Property": 200000},
            {"Investments": 7, "Property": 3},
            Decimal("0"),
            swr_excluded_groups=excluded,
        )

    def test_excluded_group_stays_in_net_worth(self):
        """A home is a real asset; it just does not back the 4%."""
        portfolio = self._portfolio(["Property"])

        assert portfolio.total == Decimal("400000")
        assert portfolio.swr_base == Decimal("200000")

    def test_no_exclusions_leaves_the_base_untouched(self):
        portfolio = self._portfolio()

        assert portfolio.swr_base == portfolio.total
        assert portfolio.has_swr_exclusions is False

    def test_excluding_a_group_delays_fire(self):
        """Less capital backs the withdrawal, so FIRE takes longer."""
        inputs = FireInputs(
            current_net_worth=Decimal("400000"),
            monthly_contribution=Decimal("1000"),
            annual_expenses=Decimal("40000"),
            annual_return_pct=Decimal("5"),
            inflation_pct=Decimal("0"),
            current_age=30,
            target_retirement_age=65,
            safe_withdrawal_rate=Decimal("4"),
        )

        included = calculate_fire(inputs, self._portfolio())
        excluded = calculate_fire(inputs, self._portfolio(["Property"]))

        assert included.years_to_fire is not None
        assert excluded.years_to_fire is not None
        assert excluded.years_to_fire > included.years_to_fire

    def test_excluded_group_still_compounds(self):
        """Exclusion is about drawing on it, not about freezing it."""
        portfolio = self._portfolio(["Property"])

        for _ in range(12):
            portfolio.step()

        assert portfolio.balances["Property"] > Decimal("200000")

    def test_withdrawals_come_from_eligible_groups_only(self):
        """Spending cannot be drawn out of the house."""
        withdrawn = self._portfolio(["Property"])
        control = self._portfolio(["Property"])

        withdrawn.step(Decimal("-1000"))
        control.step()

        # The house is untouched; the whole withdrawal hit the investments.
        assert withdrawn.balances["Property"] == control.balances["Property"]
        assert control.balances["Investments"] - withdrawn.balances[
            "Investments"
        ] == Decimal("1000")


class TestCalcFireNumber:
    """Tests for basic FIRE number calculation."""

    def test_basic_calculation(self):
        """4% SWR with 40k expenses = 1M FIRE number."""
        result = calc_fire_number(Decimal("40000"), Decimal("4"))
        assert result == Decimal("1000000")

    def test_3_percent_swr(self):
        """3% SWR with 30k expenses = 1M FIRE number."""
        result = calc_fire_number(Decimal("30000"), Decimal("3"))
        assert result == Decimal("1000000")

    def test_zero_swr_returns_infinity(self):
        """Zero SWR should return infinity."""
        result = calc_fire_number(Decimal("40000"), Decimal("0"))
        assert result == Decimal("Infinity")

    def test_negative_swr_returns_infinity(self):
        """Negative SWR should return infinity."""
        result = calc_fire_number(Decimal("40000"), Decimal("-1"))
        assert result == Decimal("Infinity")


class TestCalcCoastFireNumber:
    """Tests for Coast FIRE number calculation."""

    def test_basic_calculation(self):
        """Coast FIRE number discounts by compound growth."""
        fire_number = Decimal("1000000")
        real_return = Decimal("5")  # 5% real return
        years = Decimal("20")

        result = calc_coast_fire_number(fire_number, real_return, years)

        # 1M / (1.05^20) ≈ 376,889
        assert result > Decimal("370000")
        assert result < Decimal("385000")

    def test_zero_years_returns_fire_number(self):
        """Zero years to retirement means Coast FIRE = FIRE number."""
        fire_number = Decimal("1000000")
        result = calc_coast_fire_number(fire_number, Decimal("5"), Decimal("0"))
        assert result == fire_number

    def test_negative_years_returns_fire_number(self):
        """Negative years returns the FIRE number as-is."""
        fire_number = Decimal("1000000")
        result = calc_coast_fire_number(fire_number, Decimal("5"), Decimal("-5"))
        assert result == fire_number


class TestCalcYearsToFire:
    """Tests for years-to-FIRE simulation."""

    def test_already_fire(self):
        """Returns 0 if already at FIRE number."""
        result = calc_years_to_fire(
            current_net_worth=Decimal("1000000"),
            monthly_contribution=Decimal("1000"),
            fire_number=Decimal("1000000"),
            real_annual_return_pct=Decimal("5"),
        )
        assert result == Decimal("0")

    def test_above_fire(self):
        """Returns 0 if above FIRE number."""
        result = calc_years_to_fire(
            current_net_worth=Decimal("1500000"),
            monthly_contribution=Decimal("1000"),
            fire_number=Decimal("1000000"),
            real_annual_return_pct=Decimal("5"),
        )
        assert result == Decimal("0")

    def test_reasonable_scenario(self):
        """Typical scenario returns reasonable years."""
        result = calc_years_to_fire(
            current_net_worth=Decimal("100000"),
            monthly_contribution=Decimal("2000"),
            fire_number=Decimal("1000000"),
            real_annual_return_pct=Decimal("5"),
        )
        # Should be reachable in reasonable time
        assert result is not None
        assert result > Decimal("10")
        assert result < Decimal("30")

    def test_unreachable_returns_none(self):
        """Returns None for unreachable scenarios (100+ years)."""
        result = calc_years_to_fire(
            current_net_worth=Decimal("0"),
            monthly_contribution=Decimal("1"),  # Very low contribution
            fire_number=Decimal("100000000"),  # Very high target
            real_annual_return_pct=Decimal("1"),  # Low returns
        )
        assert result is None


class TestCalcCoastFireAge:
    """Tests for Coast FIRE age calculation."""

    def test_already_coast_fire(self):
        """Returns current age if already at Coast FIRE."""
        result = calc_coast_fire_age(
            current_net_worth=Decimal("500000"),
            monthly_contribution=Decimal("1000"),
            fire_number=Decimal("1000000"),
            real_annual_return_pct=Decimal("5"),
            current_age=30,
            target_retirement_age=65,
        )
        # Should return current age since Coast FIRE is already achieved
        assert result == Decimal("30")

    def test_reachable_coast_fire(self):
        """Returns age when Coast FIRE is reached."""
        result = calc_coast_fire_age(
            current_net_worth=Decimal("50000"),
            monthly_contribution=Decimal("2000"),
            fire_number=Decimal("1000000"),
            real_annual_return_pct=Decimal("5"),
            current_age=25,
            target_retirement_age=65,
        )
        assert result is not None
        assert result > Decimal("25")
        assert result < Decimal("65")

    def test_unreachable_returns_none(self):
        """Returns None if Coast FIRE is unreachable before retirement."""
        result = calc_coast_fire_age(
            current_net_worth=Decimal("0"),
            monthly_contribution=Decimal("100"),
            fire_number=Decimal("10000000"),
            real_annual_return_pct=Decimal("2"),
            current_age=60,
            target_retirement_age=65,
        )
        assert result is None

    def test_zero_or_negative_total_months(self):
        """Returns None if already past retirement age."""
        result = calc_coast_fire_age(
            current_net_worth=Decimal("100000"),
            monthly_contribution=Decimal("1000"),
            fire_number=Decimal("1000000"),
            real_annual_return_pct=Decimal("5"),
            current_age=70,
            target_retirement_age=65,
        )
        assert result is None


class TestPensionIsReal:
    """TyEL is inflation-hedged, so it is never deflated (issue #98)."""

    def _inputs(self, inflation_pct):
        return FireInputs(
            current_net_worth=Decimal("100000"),
            monthly_contribution=Decimal("1000"),
            annual_expenses=Decimal("40000"),
            annual_return_pct=Decimal("7"),
            inflation_pct=inflation_pct,
            current_age=30,
            target_retirement_age=45,
            safe_withdrawal_rate=Decimal("4"),
            pension_accrued_monthly=Decimal("500"),
            pension_monthly_salary=Decimal("4000"),
            pension_accrual_rate=Decimal("1.5"),
            pension_full_age=68,
        )

    def test_pension_does_not_shrink_with_inflation(self):
        """The palkkakerroin and TyEL index already hedge it."""
        no_inflation = calculate_fire(self._inputs(Decimal("0")))
        high_inflation = calculate_fire(self._inputs(Decimal("5")))

        assert no_inflation.pension is not None
        assert high_inflation.pension is not None
        assert (
            no_inflation.pension.projected_monthly_pension
            == high_inflation.pension.projected_monthly_pension
        )

    def test_accrual_stops_at_the_retirement_age(self):
        """Retiring at 45 credits accrual to 45, not through to full age."""
        result = calculate_fire(self._inputs(Decimal("2")))

        assert result.pension is not None
        # 500 accrued + 15 years (30 -> 45) * 4000 * 1.5%
        assert result.pension.projected_monthly_pension == Decimal("1400.00")


class TestPensionCalculations:
    """Tests for pension-related calculations."""

    def test_calc_projected_monthly_pension(self):
        """Projects pension based on current accrual + future work."""
        result = calc_projected_monthly_pension(
            accrued_monthly=Decimal("500"),
            current_age=35,
            fire_age=Decimal("55"),
            monthly_salary=Decimal("4000"),
            accrual_rate_pct=Decimal("1.5"),
        )
        # 500 + 20 years * 4000 * 0.015 = 500 + 1200 = 1700
        assert result == Decimal("1700")

    def test_calc_projected_monthly_pension_no_future_work(self):
        """If fire_age <= current_age, no additional accrual."""
        result = calc_projected_monthly_pension(
            accrued_monthly=Decimal("500"),
            current_age=55,
            fire_age=Decimal("50"),
            monthly_salary=Decimal("4000"),
            accrual_rate_pct=Decimal("1.5"),
        )
        assert result == Decimal("500")

    def test_calc_pension_adjustment_early(self):
        """Early pension (before full age) reduces pension."""
        result = calc_pension_adjustment(
            projected_monthly=Decimal("1000"),
            pension_full_age=68,
            pension_start_age=65,
        )
        # 3 years early = 36 months * 0.4% = 14.4% reduction
        assert result < Decimal("1000")
        assert result > Decimal("850")

    def test_calc_pension_adjustment_normal(self):
        """Normal pension (at full age) is unchanged."""
        result = calc_pension_adjustment(
            projected_monthly=Decimal("1000"),
            pension_full_age=68,
            pension_start_age=68,
        )
        assert result == Decimal("1000")

    def test_calc_pension_adjustment_late(self):
        """Late pension (after full age) increases pension."""
        result = calc_pension_adjustment(
            projected_monthly=Decimal("1000"),
            pension_full_age=68,
            pension_start_age=71,
        )
        # 3 years late = 36 months * 0.4% = 14.4% bonus
        assert result > Decimal("1000")
        assert result < Decimal("1150")

    def test_pv_annuity_basic(self):
        """Present value of annuity calculation."""
        # 10 years of $10,000/year at 5%
        result = pv_annuity(
            annual_payment=Decimal("10000"),
            years=Decimal("10"),
            real_annual_return=Decimal("0.05"),
        )
        # PV ≈ $77,217
        assert result > Decimal("75000")
        assert result < Decimal("80000")

    def test_pv_annuity_zero_return(self):
        """Zero return means PV = payment * years."""
        result = pv_annuity(
            annual_payment=Decimal("10000"),
            years=Decimal("10"),
            real_annual_return=Decimal("0"),
        )
        assert result == Decimal("100000")

    def test_pv_annuity_zero_years_or_payment(self):
        """Zero years or zero payment returns 0."""
        zero = Decimal("0")
        d_10000 = Decimal("10000")
        d_10 = Decimal("10")
        d_005 = Decimal("0.05")
        assert pv_annuity(d_10000, zero, d_005) == zero
        assert pv_annuity(zero, d_10, d_005) == zero

    def test_calc_pension_fire_number(self):
        """Pension-adjusted FIRE number accounts for pension income."""
        # With 24k annual pension covering half of 48k expenses,
        # FIRE number should be much lower than without pension
        without_pension = calc_fire_number(Decimal("48000"), Decimal("4"))

        with_pension = calc_pension_fire_number(
            annual_expenses=Decimal("48000"),
            annual_pension=Decimal("24000"),
            fire_age=Decimal("55"),
            pension_start_age=65,
            swr_pct=Decimal("4"),
            real_annual_return=Decimal("0.05"),
        )

        assert with_pension < without_pension
        assert with_pension > Decimal("0")

    def test_calc_guarantee_crossover_age(self):
        """Finds age when pension exceeds guarantee."""
        result = calc_guarantee_crossover_age(
            accrued_monthly=Decimal("500"),
            current_age=35,
            monthly_salary=Decimal("4000"),
            accrual_rate_pct=Decimal("1.5"),
            guarantee_amount=Decimal("990"),
            max_age=71,
        )
        # Need 490 more, annual accrual = 60
        # Years needed = 490 / 60 ≈ 8.17
        assert result is not None
        assert result > Decimal("43")
        assert result < Decimal("44")

    def test_calc_guarantee_crossover_age_already_exceeded(self):
        """Returns current age if already above guarantee."""
        result = calc_guarantee_crossover_age(
            accrued_monthly=Decimal("1200"),
            current_age=35,
            monthly_salary=Decimal("4000"),
            accrual_rate_pct=Decimal("1.5"),
            guarantee_amount=Decimal("990"),
            max_age=71,
        )
        assert result == Decimal("35")

    def test_generate_pension_scenarios(self):
        """Generates early/normal/late scenarios."""
        scenarios = generate_pension_scenarios(
            projected_monthly_pension=Decimal("1000"),
            pension_full_age=68,
            fire_age=Decimal("55"),
            annual_expenses=Decimal("36000"),
            swr_pct=Decimal("4"),
            real_annual_return=Decimal("0.05"),
        )

        assert len(scenarios) == 3
        assert scenarios[0].label == "early"
        assert scenarios[1].label == "normal"
        assert scenarios[2].label == "late"

        # Early pension start should be 3 years before
        assert scenarios[0].pension_start_age == 65
        assert scenarios[1].pension_start_age == 68
        assert scenarios[2].pension_start_age == 71

        # Early pension is lower, late is higher
        assert scenarios[0].monthly_pension < scenarios[1].monthly_pension
        assert scenarios[1].monthly_pension < scenarios[2].monthly_pension


class TestCalculateFire:
    """Tests for main calculate_fire function."""

    def test_basic_fire_calculation(self):
        """Basic FIRE calculation without pension."""
        inputs = FireInputs(
            current_net_worth=Decimal("100000"),
            monthly_contribution=Decimal("2000"),
            annual_expenses=Decimal("40000"),
            annual_return_pct=Decimal("7"),
            inflation_pct=Decimal("2"),
            current_age=30,
            target_retirement_age=55,
            safe_withdrawal_rate=Decimal("4"),
        )

        result = calculate_fire(inputs)

        assert result.fire_number == Decimal("1000000")
        assert result.years_to_fire is not None
        assert result.fire_age is not None
        assert len(result.projections) > 0
        assert result.pension is None

    def test_fire_with_pension(self):
        """FIRE calculation with pension enabled."""
        inputs = FireInputs(
            current_net_worth=Decimal("100000"),
            monthly_contribution=Decimal("2000"),
            annual_expenses=Decimal("40000"),
            annual_return_pct=Decimal("7"),
            inflation_pct=Decimal("2"),
            current_age=30,
            target_retirement_age=55,
            safe_withdrawal_rate=Decimal("4"),
            pension_accrued_monthly=Decimal("300"),
            pension_monthly_salary=Decimal("4000"),
            pension_accrual_rate=Decimal("1.5"),
            pension_full_age=68,
        )

        result = calculate_fire(inputs)

        # FIRE number should be lower with pension
        assert result.fire_number < Decimal("1000000")
        assert result.pension is not None
        assert len(result.pension.scenarios) == 3

    def test_already_fired(self):
        """Handles case where already at FIRE."""
        inputs = FireInputs(
            current_net_worth=Decimal("2000000"),
            monthly_contribution=Decimal("0"),
            annual_expenses=Decimal("40000"),
            annual_return_pct=Decimal("7"),
            inflation_pct=Decimal("2"),
            current_age=45,
            target_retirement_age=55,
            safe_withdrawal_rate=Decimal("4"),
        )

        result = calculate_fire(inputs)

        assert result.years_to_fire == Decimal("0")
        assert result.fire_age == Decimal("45")
        assert result.on_track is True
        assert result.coast_fire_reached is True

    def test_projections_have_correct_structure(self):
        """Projections have all required fields."""
        inputs = FireInputs(
            current_net_worth=Decimal("100000"),
            monthly_contribution=Decimal("2000"),
            annual_expenses=Decimal("40000"),
            annual_return_pct=Decimal("7"),
            inflation_pct=Decimal("2"),
            current_age=30,
            target_retirement_age=55,
            safe_withdrawal_rate=Decimal("4"),
        )

        result = calculate_fire(inputs)

        # Should have starting point + yearly projections
        assert len(result.projections) > 1

        first_point = result.projections[0]
        assert first_point.age == 30
        assert first_point.net_worth is not None
        assert first_point.coast_net_worth is not None

    def test_pension_projections_have_scenario_values(self):
        """Pension projections include early/normal/late scenario values."""
        inputs = FireInputs(
            current_net_worth=Decimal("100000"),
            monthly_contribution=Decimal("2000"),
            annual_expenses=Decimal("40000"),
            annual_return_pct=Decimal("7"),
            inflation_pct=Decimal("2"),
            current_age=30,
            target_retirement_age=55,
            safe_withdrawal_rate=Decimal("4"),
            pension_accrued_monthly=Decimal("300"),
            pension_monthly_salary=Decimal("4000"),
        )

        result = calculate_fire(inputs)

        first_point = result.projections[0]
        assert first_point.net_worth_early is not None
        assert first_point.net_worth_normal is not None
        assert first_point.net_worth_late is not None

    def test_projection_compounds_at_the_fisher_real_rate(self):
        """The projection grows at the same real rate the UI reports (issue #98).

        Zero contributions, so year one is exactly one application of the rate.
        Subtracting inflation instead would give 105000.
        """
        inputs = FireInputs(
            current_net_worth=Decimal("100000"),
            monthly_contribution=Decimal("0"),
            annual_expenses=Decimal("40000"),
            annual_return_pct=Decimal("8"),
            inflation_pct=Decimal("3"),
            current_age=30,
            target_retirement_age=55,
            safe_withdrawal_rate=Decimal("4"),
        )

        result = calculate_fire(inputs)

        year_one = result.projections[1]
        assert year_one.age == 31
        assert year_one.net_worth == Decimal("104854")

    def test_fire_number_now_equals_fire_number_without_pension(self):
        """Without pension the retire-now number matches the FIRE number."""
        inputs = FireInputs(
            current_net_worth=Decimal("100000"),
            monthly_contribution=Decimal("2000"),
            annual_expenses=Decimal("40000"),
            annual_return_pct=Decimal("7"),
            inflation_pct=Decimal("2"),
            current_age=30,
            target_retirement_age=55,
            safe_withdrawal_rate=Decimal("4"),
        )

        result = calculate_fire(inputs)

        assert result.fire_number_now == result.fire_number

    def test_fire_number_now_matches_current_age_projection(self):
        """In pension mode the retire-now number is the current-age FIRE line."""
        inputs = FireInputs(
            current_net_worth=Decimal("100000"),
            monthly_contribution=Decimal("2000"),
            annual_expenses=Decimal("40000"),
            annual_return_pct=Decimal("7"),
            inflation_pct=Decimal("2"),
            current_age=30,
            target_retirement_age=55,
            safe_withdrawal_rate=Decimal("4"),
            pension_accrued_monthly=Decimal("300"),
            pension_monthly_salary=Decimal("4000"),
        )

        result = calculate_fire(inputs)

        # The retire-now figure equals the leftmost point of the age-varying
        # FIRE line, and (since pension keeps accruing) is higher than the
        # number for retiring later at the target age.
        assert result.fire_number_now == result.projections[0].fire_number_at_age
        assert result.fire_number_now > result.fire_number

    def test_fire_number_now_ignores_target_retirement_age(self):
        """The retire-now number must not move with the retirement-age slider."""

        def build(target: int) -> FireInputs:
            return FireInputs(
                current_net_worth=Decimal("100000"),
                monthly_contribution=Decimal("2000"),
                annual_expenses=Decimal("40000"),
                annual_return_pct=Decimal("7"),
                inflation_pct=Decimal("2"),
                current_age=30,
                target_retirement_age=target,
                safe_withdrawal_rate=Decimal("4"),
                pension_accrued_monthly=Decimal("300"),
                pension_monthly_salary=Decimal("4000"),
            )

        result_55 = calculate_fire(build(55))
        result_60 = calculate_fire(build(60))

        # fire_number depends on the target age; fire_number_now does not.
        assert result_55.fire_number != result_60.fire_number
        assert result_55.fire_number_now == result_60.fire_number_now


class TestFireCalculateEndpoint:
    """Tests for the FIRE calculation API endpoint."""

    def test_basic_calculation(self, client):
        """POST /api/forecasting/calculate returns FIRE projections."""
        response = client.post(
            "/api/forecasting/calculate",
            json={
                "current_net_worth": 100000,
                "monthly_contribution": 2000,
                "annual_expenses": 40000,
                "annual_return_pct": 7,
                "inflation_pct": 2,
                "current_age": 30,
                "target_retirement_age": 55,
                "safe_withdrawal_rate": 4,
            },
        )

        assert response.status_code == 200
        data = response.json
        assert "fire_number" in data
        assert "coast_fire_number" in data
        assert "years_to_fire" in data
        assert "projections" in data
        assert data["fire_number"] == 1000000

    def test_with_pension_inputs(self, client):
        """POST /api/forecasting/calculate handles pension inputs."""
        response = client.post(
            "/api/forecasting/calculate",
            json={
                "current_net_worth": 100000,
                "monthly_contribution": 2000,
                "annual_expenses": 40000,
                "annual_return_pct": 7,
                "inflation_pct": 2,
                "current_age": 30,
                "target_retirement_age": 55,
                "safe_withdrawal_rate": 4,
                "pension_accrued_monthly": 300,
                "pension_monthly_salary": 4000,
                "pension_accrual_rate": 1.5,
                "pension_full_age": 68,
            },
        )

        assert response.status_code == 200
        data = response.json
        assert data["pension"] is not None
        assert len(data["pension"]["scenarios"]) == 3

    def test_missing_required_field(self, client):
        """POST /api/forecasting/calculate returns 400 for missing fields."""
        response = client.post(
            "/api/forecasting/calculate",
            json={
                "current_net_worth": 100000,
                # missing other required fields
            },
        )

        assert response.status_code == 400
        assert "error" in response.json

    def test_invalid_range(self, client):
        """POST /api/forecasting/calculate validates field ranges."""
        response = client.post(
            "/api/forecasting/calculate",
            json={
                "current_net_worth": 100000,
                "monthly_contribution": 2000,
                "annual_expenses": -5000,  # Invalid: negative
                "annual_return_pct": 7,
                "inflation_pct": 2,
                "current_age": 30,
                "target_retirement_age": 55,
                "safe_withdrawal_rate": 4,
            },
        )

        assert response.status_code == 400

    def test_no_body(self, client):
        """POST /api/forecasting/calculate returns 400 with no body."""
        response = client.post(
            "/api/forecasting/calculate", content_type="application/json"
        )

        assert response.status_code == 400

    def test_defaults_applied(self, client):
        """POST /api/forecasting/calculate uses defaults for optional fields."""
        response = client.post(
            "/api/forecasting/calculate",
            json={
                "current_net_worth": 100000,
                "monthly_contribution": 2000,
                "annual_expenses": 40000,
                "annual_return_pct": 7,
                "inflation_pct": 2,
                "current_age": 30,
                "target_retirement_age": 55,
                "safe_withdrawal_rate": 4,
                # pension_accrued_monthly not provided -> no pension mode
            },
        )

        assert response.status_code == 200
        assert response.json["pension"] is None


class TestDefaultReturnForGroup:
    """Tests for per-group default return assumptions (issue #56)."""

    def test_investments(self):
        assert default_return_for_group("Personal Investments") == Decimal("7")
        assert default_return_for_group("Stocks") == Decimal("7")
        assert default_return_for_group("ETF Portfolio") == Decimal("7")

    def test_real_estate(self):
        assert default_return_for_group("Property") == Decimal("3")
        assert default_return_for_group("Real Estate") == Decimal("3")
        assert default_return_for_group("My House") == Decimal("3")

    def test_cash(self):
        assert default_return_for_group("Cash") == Decimal("1")
        assert default_return_for_group("Savings Account") == Decimal("1")

    def test_crypto(self):
        assert default_return_for_group("Crypto") == Decimal("7")
        assert default_return_for_group("Bitcoin Wallet") == Decimal("7")

    def test_bonds(self):
        assert default_return_for_group("Bonds") == Decimal("3")
        assert default_return_for_group("Fixed Income") == Decimal("3")

    def test_fallback(self):
        assert default_return_for_group("Miscellaneous") == Decimal("5")
        assert default_return_for_group("") == Decimal("5")


class TestWeightedReturn:
    """Tests for portfolio-weighted return derivation (issue #56)."""

    def test_mixed_allocation_uses_defaults(self):
        # (10000*1 + 30000*7) / 40000 = 5.5
        by_group = {"Cash": 10000, "Investments": 30000}
        assert weighted_return(by_group, {}) == Decimal("5.5")

    def test_override_takes_precedence(self):
        # (10000*1 + 30000*10) / 40000 = 7.75
        by_group = {"Cash": 10000, "Investments": 30000}
        assert weighted_return(by_group, {"Investments": 10}) == Decimal("7.75")

    def test_liabilities_and_zero_ignored(self):
        # Only the positive Investments balance is weighted -> 7
        by_group = {"Investments": 10000, "Loans": -5000, "Empty": 0}
        assert weighted_return(by_group, {}) == Decimal("7")

    def test_empty_falls_back_to_seven(self):
        assert weighted_return({}, {}) == Decimal("7")
        assert weighted_return({"Loans": -100}, {}) == Decimal("7")


class TestResolveGroupReturnRates:
    """Tests for resolving effective per-group return rates (issue #56)."""

    def test_fills_defaults_and_overrides(self):
        by_group = {"Cash": 100, "Investments": 200}
        resolved = resolve_group_return_rates(by_group, {"Investments": 9})
        assert resolved == {"Cash": Decimal("1"), "Investments": Decimal("9")}


class TestForecastingProjection:
    """Tests for GET /api/forecasting/projection (backend-derived FIRE)."""

    def test_no_data(self, client):
        """With no snapshot/budget, derived inputs are zero and return is 7%."""
        resp = client.get("/api/forecasting/projection")
        assert resp.status_code == 200
        derived = resp.json["derived"]
        assert derived["current_net_worth"] == 0
        assert derived["monthly_savings"] == 0
        assert derived["annual_expenses"] == 0
        assert derived["weighted_return_pct"] == 7
        assert derived["pension_active"] is False
        assert resp.json["pension"] is None

    def test_with_snapshot_and_budget(self, client):
        """Derives net worth, weighted return, savings and expenses from state."""
        client.post("/api/networth/categories/seed")
        # Cash 10000 (cat 1) + Investments 30000 (cat 5) -> NW 40000, return 5.5
        client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2025,
                "entries": [
                    {"category_id": 1, "amount": 10000},
                    {"category_id": 5, "amount": 30000},
                ],
            },
        )
        # Untaxed income 4000 net; 1000 expenses
        client.post(
            "/api/income",
            json={"name": "Salary", "gross_amount": 4000, "is_taxed": False},
        )
        client.post("/api/expenses", json={"name": "Rent", "amount": 1000})

        resp = client.get("/api/forecasting/projection")
        assert resp.status_code == 200
        derived = resp.json["derived"]
        assert derived["current_net_worth"] == 40000
        assert derived["weighted_return_pct"] == 5.5
        assert derived["monthly_savings"] == 3000  # 4000 - 1000
        assert derived["annual_expenses"] == 12000  # 1000 * 12
        assert derived["group_return_rates"] == {"Cash": 1, "Investments": 7}

    def test_real_return_is_fisher_derived(self, client):
        """Real return comes from the backend's Fisher conversion (issue #98).

        The frontend used to compute "weighted - inflation" itself, so the
        displayed figure disagreed with the one the projection compounded at.
        """
        client.post("/api/networth/categories/seed")
        client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2025,
                "entries": [
                    {"category_id": 1, "amount": 10000},
                    {"category_id": 5, "amount": 30000},
                ],
            },
        )

        derived = client.get("/api/forecasting/projection").json["derived"]

        # Weighted 5.5% at the default 2% inflation -> 3.431%, not 3.5%
        assert derived["weighted_return_pct"] == 5.5
        assert abs(derived["real_return_pct"] - 3.43137) < 0.0001
        assert derived["real_return_pct"] != 3.5

    def test_overrides_applied(self, client):
        """Persisted overrides take precedence over budget-derived values."""
        client.put(
            "/api/forecasting/settings",
            json={"monthly_savings_override": 1500, "annual_expenses_override": 20000},
        )
        resp = client.get("/api/forecasting/projection")
        assert resp.status_code == 200
        derived = resp.json["derived"]
        assert derived["monthly_savings"] == 1500
        assert derived["annual_expenses"] == 20000
        # Flagged so a reader can tell these apart from the budget's own figures
        assert derived["monthly_savings_is_override"] is True
        assert derived["annual_expenses_is_override"] is True

    def test_override_flags_false_when_budget_derived(self, client):
        """Without overrides the flags say the figures came from the budget."""
        client.post(
            "/api/income",
            json={"name": "Salary", "gross_amount": 4000, "is_taxed": False},
        )
        client.post("/api/expenses", json={"name": "Rent", "amount": 1000})

        derived = client.get("/api/forecasting/projection").json["derived"]
        assert derived["monthly_savings"] == 3000
        assert derived["monthly_savings_is_override"] is False
        assert derived["annual_expenses_is_override"] is False

    def test_target_retirement_age_exposed(self, client):
        """The configured retirement age rides along for reporting."""
        client.put(
            "/api/forecasting/settings",
            json={"target_retirement_age": 62},
        )
        derived = client.get("/api/forecasting/projection").json["derived"]
        assert derived["target_retirement_age"] == 62

    def test_contribution_group_round_trips(self, client):
        """The contribution destination persists and reaches the projection."""
        client.post("/api/networth/categories/seed")
        client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2025,
                "entries": [
                    {"category_id": 1, "amount": 10000},
                    {"category_id": 5, "amount": 30000},
                ],
            },
        )

        resp = client.put(
            "/api/forecasting/settings", json={"contribution_group": "Investments"}
        )
        assert resp.status_code == 200
        assert resp.json["contribution_group"] == "Investments"

        derived = client.get("/api/forecasting/projection").json["derived"]
        assert derived["contribution_group"] == "Investments"

    def test_contribution_group_defaults_to_pro_rata(self, client):
        """Unset means contributions spread across the mix."""
        derived = client.get("/api/forecasting/projection").json["derived"]
        assert derived["contribution_group"] is None

    def test_contribution_group_rejects_non_string(self, client):
        resp = client.put("/api/forecasting/settings", json={"contribution_group": 7})
        assert resp.status_code == 400

    def _seed_with_liability(self, client):
        """Cash 10000 + Investments 30000, less a 5000 student loan."""
        client.post("/api/networth/categories/seed")
        client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2025,
                "entries": [
                    {"category_id": 1, "amount": 10000},
                    {"category_id": 5, "amount": 30000},
                    {"category_id": 10, "amount": -5000},  # Student Loan
                ],
            },
        )

    def test_liabilities_are_carried_separately(self, client):
        """Gross assets and debt are exposed, and still net to the same worth."""
        self._seed_with_liability(client)

        derived = client.get("/api/forecasting/projection").json["derived"]

        assert derived["gross_assets"] == 40000
        assert derived["liabilities_by_group"] == {"Loans": 5000}
        assert derived["current_net_worth"] == 35000

    def test_liability_terms_round_trip_and_warn(self, client):
        """Terms persist, and a payment below interest surfaces a warning."""
        self._seed_with_liability(client)

        resp = client.put(
            "/api/forecasting/settings",
            json={"liability_terms": {"Loans": {"rate_pct": 20, "monthly_payment": 5}}},
        )
        assert resp.status_code == 200
        assert resp.json["liability_terms"]["Loans"]["rate_pct"] == 20

        result = client.get("/api/forecasting/projection").json
        assert result["warnings"] == [
            {"code": "negative_amortization", "group": "Loans"}
        ]

    def test_serviceable_liability_has_no_warning(self, client):
        self._seed_with_liability(client)
        client.put(
            "/api/forecasting/settings",
            json={
                "liability_terms": {"Loans": {"rate_pct": 2, "monthly_payment": 200}}
            },
        )

        assert client.get("/api/forecasting/projection").json["warnings"] == []

    def test_liability_terms_reject_bad_values(self, client):
        assert (
            client.put(
                "/api/forecasting/settings",
                json={"liability_terms": {"Loans": {"rate_pct": 99}}},
            ).status_code
            == 400
        )
        assert (
            client.put(
                "/api/forecasting/settings",
                json={"liability_terms": {"Loans": {"monthly_payment": -5}}},
            ).status_code
            == 400
        )

    def test_swr_exclusion_round_trips(self, client):
        """An excluded group leaves net worth alone but shrinks the SWR base."""
        client.post("/api/networth/categories/seed")
        client.post(
            "/api/networth",
            json={
                "month": 1,
                "year": 2025,
                "entries": [
                    {"category_id": 5, "amount": 30000},
                    {"category_id": 9, "amount": 20000},  # House/Apartment
                ],
            },
        )

        resp = client.put(
            "/api/forecasting/settings", json={"swr_excluded_groups": ["Property"]}
        )
        assert resp.status_code == 200

        derived = client.get("/api/forecasting/projection").json["derived"]
        assert derived["current_net_worth"] == 50000
        assert derived["swr_excluded_groups"] == ["Property"]
        assert derived["swr_base"] == 30000

    def test_swr_exclusion_rejects_non_list(self, client):
        resp = client.put(
            "/api/forecasting/settings", json={"swr_excluded_groups": "Property"}
        )
        assert resp.status_code == 400

    def test_pension_mode_activated(self, client):
        """Setting pension_accrued_monthly activates pension mode."""
        client.put(
            "/api/forecasting/settings",
            json={"pension_accrued_monthly": 500},
        )
        resp = client.get("/api/forecasting/projection")
        assert resp.status_code == 200
        assert resp.json["derived"]["pension_active"] is True
        assert resp.json["pension"] is not None
