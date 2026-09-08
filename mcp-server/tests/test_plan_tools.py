"""Planning tools, against the real Flask app."""

import pytest
from mcp.client import Client

from tests.helpers import call, call_error, tool_named
from vipu_mcp.client import VipuClient
from vipu_mcp.server import build_server

PLAN_TOOLS = [
    "project_fire",
    "forecast_net_worth",
    "update_forecasting_settings",
    "update_budget_settings",
]


@pytest.mark.anyio
async def test_every_plan_tool_is_registered(server):
    async with Client(server) as client:
        listing = await client.list_tools()
    assert set(PLAN_TOOLS) <= {tool.name for tool in listing.tools}


@pytest.mark.anyio
async def test_the_what_ifs_are_read_only_and_the_updates_are_not(server):
    """POST /api/forecasting/calculate stores nothing; PUT settings does."""
    async with Client(server) as client:
        for name in ("project_fire", "forecast_net_worth"):
            tool = await tool_named(client, name)
            assert tool.annotations is not None
            assert tool.annotations.read_only_hint is True, name
        for name in ("update_forecasting_settings", "update_budget_settings"):
            tool = await tool_named(client, name)
            assert tool.annotations is not None
            assert tool.annotations.read_only_hint is False, name
            assert tool.annotations.destructive_hint is False, name


@pytest.mark.anyio
async def test_read_only_mode_keeps_the_what_ifs_and_drops_the_writes(
    client: VipuClient,
):
    async with Client(build_server(client, read_only=True)) as mcp:
        listing = await mcp.list_tools()
    names = {tool.name for tool in listing.tools}
    assert {"project_fire", "forecast_net_worth"} <= names
    assert names.isdisjoint({"update_forecasting_settings", "update_budget_settings"})


class TestProjectFire:
    @pytest.mark.anyio
    async def test_no_arguments_is_a_no_op_against_its_own_baseline(
        self, seeded, seeded_server
    ):
        async with Client(seeded_server) as client:
            result = await call(client, "project_fire", {})

        assert result["inputs_changed"] == {}
        assert result["scenario"] == result["baseline"]
        assert result["delta"]["years_to_fire"]["change"] == 0.0
        assert result["delta"]["years_to_fire"]["summary"] == "no change"

    @pytest.mark.anyio
    async def test_it_takes_its_inputs_from_the_stored_projection(
        self, seeded, seeded_server
    ):
        """A one-argument call must otherwise be the user's own situation."""
        stored = seeded.get_projection()
        derived = stored["derived"]

        async with Client(seeded_server) as client:
            result = await call(client, "project_fire", {})

        used = result["inputs_used"]
        assert used["current_net_worth"] == derived["current_net_worth"]
        assert used["monthly_contribution"] == derived["monthly_savings"]
        assert used["annual_expenses"] == derived["annual_expenses"]
        assert used["annual_return_pct"] == derived["weighted_return_pct"]
        assert result["stored_projection_years_to_fire"] == stored["years_to_fire"]

    @pytest.mark.anyio
    async def test_the_baseline_is_the_same_model_as_the_scenario(
        self, seeded, seeded_server
    ):
        """The delta must measure the change, not the gap between two models.

        GET /api/forecasting/projection compounds each asset group at its own
        rate and amortises debt; POST /api/forecasting/calculate grows one pot
        at one rate. They disagree on levels for the same inputs, so the
        baseline has to come from the endpoint the scenario came from.
        """
        stored = seeded.get_projection()

        async with Client(seeded_server) as client:
            result = await call(client, "project_fire", {})

        assert result["baseline"]["years_to_fire"] != stored["years_to_fire"]
        assert result["delta"]["years_to_fire"]["from"] == (
            result["baseline"]["years_to_fire"]
        )

    @pytest.mark.anyio
    async def test_saving_more_pulls_fire_forward_and_says_so(
        self, seeded, seeded_server
    ):
        raised = seeded.get_projection()["derived"]["monthly_savings"] + 1000

        async with Client(seeded_server) as client:
            result = await call(
                client, "project_fire", {"monthly_contribution": raised}
            )

        assert result["scenario"]["years_to_fire"] < result["baseline"]["years_to_fire"]
        delta = result["delta"]["years_to_fire"]
        assert delta["change"] < 0
        assert delta["summary"].endswith("years earlier")
        assert result["inputs_changed"] == {"monthly_contribution": raised}

    @pytest.mark.anyio
    async def test_spending_more_pushes_fire_out(self, seeded, seeded_server):
        raised = seeded.get_projection()["derived"]["annual_expenses"] * 1.5

        async with Client(seeded_server) as client:
            result = await call(client, "project_fire", {"annual_expenses": raised})

        assert result["scenario"]["fire_number"] > result["baseline"]["fire_number"]
        assert result["delta"]["years_to_fire"]["summary"].endswith("years later")

    @pytest.mark.anyio
    async def test_it_persists_nothing(self, seeded, seeded_server):
        """A what-if the user did not commit to must not move the app."""
        before = seeded.get_projection()
        before_settings = seeded.get_forecasting_settings()

        async with Client(seeded_server) as client:
            await call(
                client,
                "project_fire",
                {"monthly_contribution": 99999, "annual_return_pct": 15},
            )

        assert seeded.get_projection() == before
        assert seeded.get_forecasting_settings() == before_settings

    @pytest.mark.anyio
    async def test_the_monthly_walk_is_dropped(self, seeded_server):
        async with Client(seeded_server) as client:
            result = await call(client, "project_fire", {})
        assert "projections" not in result["scenario"]

    @pytest.mark.anyio
    async def test_the_backends_validation_message_comes_through(self, seeded_server):
        async with Client(seeded_server) as client:
            message = await call_error(
                client, "project_fire", {"safe_withdrawal_rate": 99}
            )
        assert "Validation error" in message
        assert "safe_withdrawal_rate" in message

    @pytest.mark.anyio
    async def test_the_description_says_nothing_is_stored(self, server):
        async with Client(server) as client:
            tool = await tool_named(client, "project_fire")
        description = tool.description or ""
        assert "Nothing is stored" in description
        assert "pulls FIRE forward" in description
        assert "will not match get_fire_projection" in description


class TestForecastNetWorth:
    @pytest.mark.anyio
    async def test_projects_from_the_snapshot_trend(self, seeded, seeded_server):
        async with Client(seeded_server) as client:
            result = await call(
                client, "forecast_net_worth", {"period": "year", "months_ahead": 6}
            )

        assert result["period"] == "year"
        assert result["months_ahead"] == 6
        assert len(result["projections"]) == 6
        assert result["data_points_used"] > 1
        assert result == seeded.forecast_net_worth("year", 6)

    @pytest.mark.anyio
    async def test_defaults_to_a_quarter_and_a_year_ahead(self, seeded_server):
        async with Client(seeded_server) as client:
            result = await call(client, "forecast_net_worth", {})
        assert result["period"] == "quarter"
        assert result["months_ahead"] == 12

    @pytest.mark.anyio
    async def test_an_invalid_period_is_rejected_by_the_backend(self, seeded_server):
        async with Client(seeded_server) as client:
            message = await call_error(
                client, "forecast_net_worth", {"period": "fortnight"}
            )
        assert "period must be one of" in message

    @pytest.mark.anyio
    async def test_the_description_separates_it_from_fire(self, server):
        async with Client(server) as client:
            tool = await tool_named(client, "forecast_net_worth")
        description = tool.description or ""
        assert "not a compounding model" in description
        assert "Different question from get_fire_projection" in description


class TestUpdateForecastingSettings:
    @pytest.mark.anyio
    async def test_changing_an_assumption_moves_the_stored_projection(
        self, seeded, seeded_server
    ):
        before = seeded.get_projection()

        async with Client(seeded_server) as client:
            result = await call(
                client,
                "update_forecasting_settings",
                {
                    "monthly_savings_override": before["derived"]["monthly_savings"]
                    + 800
                },
            )

        after = seeded.get_projection()
        assert after["years_to_fire"] != before["years_to_fire"]
        assert result["projection"]["years_to_fire"] == after["years_to_fire"]
        assert result["delta"]["years_to_fire"]["change"] < 0
        assert result["changed"] == ["monthly_savings_override"]
        assert result["settings"]["monthly_savings_override"] is not None

    @pytest.mark.anyio
    async def test_an_override_can_be_cleared(self, seeded, seeded_server):
        """None means "leave it alone", so clearing needs its own argument."""
        async with Client(seeded_server) as client:
            await call(
                client,
                "update_forecasting_settings",
                {"annual_expenses_override": 40000},
            )
            assert seeded.get_projection()["derived"]["annual_expenses_is_override"]

            result = await call(
                client,
                "update_forecasting_settings",
                {"clear_annual_expenses_override": True},
            )

        assert result["settings"]["annual_expenses_override"] is None
        assert not seeded.get_projection()["derived"]["annual_expenses_is_override"]

    @pytest.mark.anyio
    async def test_group_return_rates_are_accepted(self, seeded, seeded_server):
        rates = seeded.get_projection()["derived"]["group_return_rates"]
        bumped = {group: 9.0 for group in rates}

        async with Client(seeded_server) as client:
            result = await call(
                client, "update_forecasting_settings", {"group_return_rates": bumped}
            )

        assert result["settings"]["group_return_rates"] == bumped
        assert result["projection"]["derived"]["weighted_return_pct"] == 9.0

    @pytest.mark.anyio
    async def test_an_out_of_range_value_is_refused_with_the_reason(
        self, seeded_server
    ):
        async with Client(seeded_server) as client:
            message = await call_error(
                client, "update_forecasting_settings", {"inflation_pct": 99}
            )
        assert "inflation_pct must be between 0 and 20" in message

    @pytest.mark.anyio
    async def test_the_description_warns_it_changes_everything(self, server):
        async with Client(server) as client:
            tool = await tool_named(client, "update_forecasting_settings")
        description = tool.description or ""
        assert "changes what the app says everywhere" in description
        assert "use project_fire instead" in description


class TestUpdateBudgetSettings:
    @pytest.mark.anyio
    async def test_moving_payday_moves_the_period_boundaries(
        self, seeded, seeded_server
    ):
        before = seeded.get_budget()["totals"]
        moved = 1 if before["period_current"]["end"][-2:] != "01" else 15

        async with Client(seeded_server) as client:
            result = await call(client, "update_budget_settings", {"payday_day": moved})

        after = seeded.get_budget()["totals"]
        assert result["settings"]["payday_day"] == moved
        assert result["period_current"] == after["period_current"]
        assert result["next_payday"] == after["next_payday"]
        assert after["next_payday"] != before["next_payday"]

    @pytest.mark.anyio
    async def test_changing_the_tax_rate_moves_the_surplus(self, seeded, seeded_server):
        before = seeded.get_budget()["totals"]["monthly_surplus"]

        async with Client(seeded_server) as client:
            result = await call(
                client, "update_budget_settings", {"tax_percentage": 45}
            )

        assert result["settings"]["tax_percentage"] == 45.0
        assert result["monthly_surplus"] < before
        assert result["monthly_surplus"] == (
            seeded.get_budget()["totals"]["monthly_surplus"]
        )

    @pytest.mark.anyio
    async def test_an_invalid_payday_is_refused_with_the_reason(self, seeded_server):
        async with Client(seeded_server) as client:
            message = await call_error(
                client, "update_budget_settings", {"payday_day": 45}
            )
        assert "payday_day must be between 1 and 31" in message

    @pytest.mark.anyio
    async def test_the_description_explains_the_rollover(self, server):
        async with Client(server) as client:
            tool = await tool_named(client, "update_budget_settings")
        description = tool.description or ""
        assert "rolls over on payday rather than" in description
