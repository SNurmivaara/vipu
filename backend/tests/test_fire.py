"""Tests for FIRE calculation utilities."""

from decimal import Decimal

from app.fire import (
    FireInputs,
    calc_coast_fire_age,
    calc_coast_fire_number,
    calc_fire_number,
    calc_guarantee_crossover_age,
    calc_pension_adjustment,
    calc_pension_fire_number,
    calc_projected_monthly_pension,
    calc_years_to_fire,
    calculate_fire,
    generate_pension_scenarios,
    pv_annuity,
)


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
