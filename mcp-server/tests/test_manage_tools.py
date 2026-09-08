"""Management tools, against the real Flask app."""

import pytest
from mcp.client import Client

from tests.helpers import call, call_error, tool_named
from vipu_mcp.client import VipuClient
from vipu_mcp.server import build_server

MANAGE_TOOLS = [
    "add_expense",
    "update_expense",
    "archive_expense",
    "add_income",
    "update_income",
    "archive_income",
    "add_account",
    "set_goal",
    "update_goal",
    "reorder_goals",
]


@pytest.mark.anyio
async def test_every_management_tool_is_registered(server):
    async with Client(server) as client:
        listing = await client.list_tools()
    assert set(MANAGE_TOOLS) <= {tool.name for tool in listing.tools}


@pytest.mark.anyio
async def test_only_the_archive_tools_are_destructive(server):
    async with Client(server) as client:
        listing = await client.list_tools()

    for tool in listing.tools:
        if tool.name not in MANAGE_TOOLS:
            continue
        assert tool.annotations is not None, tool.name
        assert tool.annotations.read_only_hint is False, tool.name
        expected = tool.name.startswith("archive_")
        assert tool.annotations.destructive_hint is expected, tool.name


@pytest.mark.anyio
async def test_read_only_mode_hides_them_all(client: VipuClient):
    async with Client(build_server(client, read_only=True)) as mcp:
        listing = await mcp.list_tools()
    assert {tool.name for tool in listing.tools}.isdisjoint(MANAGE_TOOLS)


class TestCadence:
    """Scheduling is the part a model gets wrong without help."""

    @pytest.mark.anyio
    async def test_a_named_cadence_maps_to_the_field_pair(self, seeded, seeded_server):
        async with Client(seeded_server) as client:
            result = await call(
                client,
                "add_expense",
                {
                    "name": "Water",
                    "amount": 40,
                    "due_day": 5,
                    "cadence": "quarterly",
                },
            )
        assert result["expense"]["frequency_value"] == 3
        assert result["expense"]["frequency_unit"] == "months"

    @pytest.mark.parametrize(
        ("phrase", "expected"),
        [
            ("daily", (1, "days")),
            ("weekly", (1, "weeks")),
            ("biweekly", (2, "weeks")),
            ("monthly", (1, "months")),
            ("quarterly", (3, "months")),
            ("yearly", (1, "years")),
            ("annually", (1, "years")),
            ("every 2 months", (2, "months")),
            ("every 6 weeks", (6, "weeks")),
            ("Every 3 Years", (3, "years")),
        ],
    )
    @pytest.mark.anyio
    async def test_cadence_phrases(self, seeded_server, phrase, expected):
        async with Client(seeded_server) as client:
            result = await call(
                client,
                "add_expense",
                {"name": f"Line {phrase}", "amount": 10, "cadence": phrase},
            )
        item = result["expense"]
        assert (item["frequency_value"], item["frequency_unit"]) == expected

    @pytest.mark.anyio
    async def test_an_unreadable_cadence_says_what_is_accepted(self, seeded_server):
        async with Client(seeded_server) as client:
            message = await call_error(
                client,
                "add_expense",
                {"name": "Mystery", "amount": 10, "cadence": "now and then"},
            )
        assert "Could not read 'now and then' as a cadence" in message
        assert "every N days/weeks/months/years" in message

    @pytest.mark.anyio
    async def test_a_week_cadence_gets_an_anchor(self, seeded, seeded_server):
        """Without one, the dates depend on the window they are generated in."""
        async with Client(seeded_server) as client:
            result = await call(
                client,
                "add_expense",
                {"name": "Cleaner", "amount": 60, "due_day": 8, "cadence": "weekly"},
            )

        start = result["expense"]["start_date"]
        assert start is not None
        assert start.endswith("-08")

    @pytest.mark.anyio
    async def test_a_month_cadence_needs_no_anchor(self, seeded_server):
        """Monthly is phase-anchored to due_day, so no start_date is invented."""
        async with Client(seeded_server) as client:
            result = await call(
                client,
                "add_expense",
                {"name": "Gym", "amount": 30, "due_day": 3, "cadence": "monthly"},
            )
        assert result["expense"]["start_date"] is None

    @pytest.mark.anyio
    async def test_a_quarterly_bill_lands_in_one_period_not_every_one(
        self, seeded, seeded_server
    ):
        async with Client(seeded_server) as client:
            await call(
                client,
                "add_expense",
                {
                    "name": "Water",
                    "amount": 400,
                    "due_day": 5,
                    "cadence": "quarterly",
                    "start_date": "2026-01-05",
                },
            )

        totals = seeded.get_budget()["totals"]
        appearances = [
            row
            for key in ("expenses_before_payday_list", "expenses_next_period_list")
            for row in totals[key]
            if row["name"] == "Water"
        ]
        assert len(appearances) <= 1

    @pytest.mark.anyio
    async def test_the_anchor_rule_is_in_the_description(self, server):
        async with Client(server) as client:
            tool = await tool_named(client, "add_expense")
        description = tool.description or ""
        assert "phase-anchored to `start_date`" in description
        assert "Day and week cadences must have an anchor" in description


class TestOneTimeItems:
    @pytest.mark.anyio
    async def test_a_one_off_does_not_move_the_monthly_rate(
        self, seeded, seeded_server
    ):
        before = seeded.get_budget()["totals"]["monthly_expenses"]

        async with Client(seeded_server) as client:
            result = await call(
                client,
                "add_expense",
                {
                    "name": "New laptop",
                    "amount": 2000,
                    "one_time": True,
                    "start_date": "2099-01-15",
                },
            )

        assert result["expense"]["is_ephemeral"] is True
        assert result["monthly_expenses"] == before

    @pytest.mark.anyio
    async def test_a_one_off_still_appears_in_its_period(self, seeded, seeded_server):
        totals = seeded.get_budget()["totals"]
        due = totals["period_current"]["end"]

        async with Client(seeded_server) as client:
            await call(
                client,
                "add_expense",
                {
                    "name": "Vet bill",
                    "amount": 300,
                    "one_time": True,
                    "start_date": due,
                    "due_day": int(due[-2:]),
                },
            )

        after = seeded.get_budget()["totals"]
        listed = [
            row
            for key in ("expenses_before_payday_list", "expenses_next_period_list")
            for row in after[key]
            if row["name"] == "Vet bill"
        ]
        assert listed
        assert after["monthly_expenses"] == totals["monthly_expenses"]

    @pytest.mark.anyio
    async def test_the_difference_from_an_end_date_is_in_the_description(self, server):
        async with Client(server) as client:
            tool = await tool_named(client, "add_expense")
        description = tool.description or ""
        assert "not the same as a recurring item with an end date" in description
        assert "excluded from the frequency-normalized monthly rates" in description


class TestExpenseLifecycle:
    @pytest.mark.anyio
    async def test_update_touches_only_the_fields_given(self, seeded, seeded_server):
        before = next(e for e in seeded.list_expenses() if e["name"] == "Rent")

        async with Client(seeded_server) as client:
            result = await call(
                client, "update_expense", {"name": "Rent", "amount": 1350}
            )

        after = result["expense"]
        assert after["amount"] == 1350.0
        assert after["due_day"] == before["due_day"]
        assert after["frequency_unit"] == before["frequency_unit"]
        assert result["changed"] == ["amount"]

    @pytest.mark.anyio
    async def test_archiving_drops_it_from_the_monthly_rate(
        self, seeded, seeded_server
    ):
        before = seeded.get_budget()["totals"]["monthly_expenses"]

        async with Client(seeded_server) as client:
            result = await call(client, "archive_expense", {"name": "Rent"})

        assert result["archived"] is True
        assert result["expense"]["archived_at"] is not None
        assert result["monthly_expenses"] < before

    @pytest.mark.anyio
    async def test_an_archived_expense_can_be_restored(self, seeded, seeded_server):
        before = seeded.get_budget()["totals"]["monthly_expenses"]

        async with Client(seeded_server) as client:
            await call(client, "archive_expense", {"name": "Rent"})
            result = await call(
                client, "archive_expense", {"name": "Rent", "restore": True}
            )

        assert result["archived"] is False
        assert result["expense"]["archived_at"] is None
        assert result["monthly_expenses"] == before

    @pytest.mark.anyio
    async def test_the_hard_delete_is_recorded_as_out_of_reach(self, server):
        async with Client(server) as client:
            tool = await tool_named(client, "archive_expense")
        description = tool.description or ""
        assert "no undo" in description
        assert "deliberately not reachable from here" in description


class TestIncome:
    @pytest.mark.anyio
    async def test_adding_taxed_income_moves_the_surplus(self, seeded, seeded_server):
        before = seeded.get_budget()["totals"]["monthly_surplus"]

        async with Client(seeded_server) as client:
            result = await call(
                client,
                "add_income",
                {"name": "Side gig", "gross_amount": 1000, "cadence": "monthly"},
            )

        assert result["income"]["is_taxed"] is True
        assert result["monthly_surplus"] > before

    @pytest.mark.anyio
    async def test_a_deduction_reduces_net_pay(self, seeded, seeded_server):
        before = seeded.get_budget()["totals"]["monthly_net_income"]

        async with Client(seeded_server) as client:
            result = await call(
                client,
                "add_income",
                {
                    "name": "Parking benefit",
                    "gross_amount": 200,
                    "tax_percentage": 50,
                    "is_deduction": True,
                    "cadence": "monthly",
                },
            )

        assert result["income"]["is_deduction"] is True
        assert result["monthly_net_income"] < before

    @pytest.mark.anyio
    async def test_income_can_be_archived_and_restored(self, seeded, seeded_server):
        before = seeded.get_budget()["totals"]["monthly_net_income"]

        async with Client(seeded_server) as client:
            archived = await call(client, "archive_income", {"name": "Salary"})
            assert archived["monthly_net_income"] < before
            restored = await call(
                client, "archive_income", {"name": "Salary", "restore": True}
            )

        assert restored["monthly_net_income"] == before

    @pytest.mark.anyio
    async def test_the_deduction_model_is_in_the_description(self, server):
        async with Client(server) as client:
            tool = await tool_named(client, "add_income")
        description = tool.description or ""
        assert "subtracted from net pay after tax" in description


class TestAccounts:
    @pytest.mark.anyio
    async def test_adding_an_account_reports_the_new_cash_position(
        self, seeded, seeded_server
    ):
        before = seeded.get_budget()["totals"]["cash_balance"]

        async with Client(seeded_server) as client:
            result = await call(
                client, "add_account", {"name": "Buffer", "balance": 2500}
            )

        assert result["account"]["is_credit"] is False
        assert result["cash_balance"] == before + 2500

    @pytest.mark.anyio
    async def test_adding_a_card(self, seeded, seeded_server):
        async with Client(seeded_server) as client:
            result = await call(
                client,
                "add_account",
                {
                    "name": "Amex",
                    "balance": -300,
                    "is_credit": True,
                    "payment_due_day": 20,
                },
            )
        assert result["account"]["payment_due_day"] == 20
        assert result["card_debt"] <= -300

    @pytest.mark.anyio
    async def test_the_backends_validation_message_comes_through(self, seeded_server):
        async with Client(seeded_server) as client:
            message = await call_error(
                client, "add_account", {"name": "Bad", "payment_due_day": 40}
            )
        assert "payment_due_day must be between 1 and 31" in message


class TestGoals:
    @pytest.mark.anyio
    async def test_creating_a_roadmap_goal_appends_it_to_the_plan(
        self, seeded, seeded_server
    ):
        before = [step["goal"]["name"] for step in seeded.get_roadmap()["goals"]]

        async with Client(seeded_server) as client:
            result = await call(
                client,
                "set_goal",
                {
                    "name": "New roof",
                    "goal_type": "savings_goal",
                    "target_value": 8000,
                },
            )

        assert result["goal"]["priority"] == len(before)
        assert [step["name"] for step in result["roadmap"]] == [*before, "New roof"]

    @pytest.mark.anyio
    async def test_a_category_is_linked_by_name(self, seeded, seeded_server):
        async with Client(seeded_server) as client:
            result = await call(
                client,
                "set_goal",
                {
                    "name": "Cash cushion",
                    "goal_type": "savings_goal",
                    "target_value": 10000,
                    "category_name": "Checking",
                },
            )
        assert result["goal"]["category"]["name"] == "Checking"

    @pytest.mark.anyio
    async def test_a_category_on_the_wrong_goal_type_is_refused(self, seeded_server):
        async with Client(seeded_server) as client:
            message = await call_error(
                client,
                "set_goal",
                {
                    "name": "Bad link",
                    "goal_type": "net_worth",
                    "target_value": 1000,
                    "category_name": "Checking",
                },
            )
        assert "category_id is only supported for savings_goal type" in message

    @pytest.mark.anyio
    async def test_updating_a_goal_by_name(self, seeded, seeded_server):
        async with Client(seeded_server) as client:
            result = await call(
                client,
                "update_goal",
                {"name": "Emergency fund", "target_value": 15000},
            )
        assert result["goal"]["target_value"] == 15000.0
        assert result["changed"] == ["target_value"]

    @pytest.mark.anyio
    async def test_reordering_moves_the_dates_below_the_moved_step(
        self, seeded, seeded_server
    ):
        before = {
            step["goal"]["name"]: step["projected_completion_date"]
            for step in seeded.get_roadmap()["goals"]
        }
        assert len(before) >= 3
        names = list(before)
        reversed_order = list(reversed(names))

        async with Client(seeded_server) as client:
            result = await call(client, "reorder_goals", {"names": reversed_order})

        assert result["order"] == reversed_order
        after = {
            step["name"]: step["projected_completion_date"]
            for step in result["roadmap"]
        }
        assert list(after) == reversed_order
        assert any(after[name] != before[name] for name in names)

    @pytest.mark.anyio
    async def test_a_non_roadmap_goal_cannot_be_ordered(self, seeded, seeded_server):
        async with Client(seeded_server) as client:
            await call(
                client,
                "set_goal",
                {"name": "Two million", "goal_type": "net_worth", "target_value": 2e6},
            )
            message = await call_error(
                client, "reorder_goals", {"names": ["Two million"]}
            )
        assert "Not roadmap goals" in message

    @pytest.mark.anyio
    async def test_the_cascade_is_in_the_description(self, server):
        async with Client(server) as client:
            tool = await tool_named(client, "reorder_goals")
        description = tool.description or ""
        assert "every step below it" in description
