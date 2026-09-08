"""Record tools, against the real Flask app."""

import pytest
from mcp.client import Client

from tests.helpers import call, call_error, tool_named
from vipu_mcp.client import VipuClient
from vipu_mcp.server import build_server

WRITE_TOOLS = [
    "set_account_balance",
    "record_budget_snapshot",
    "record_net_worth",
    "settle_expense",
    "settle_income",
]


@pytest.mark.anyio
async def test_every_record_tool_is_registered(server):
    async with Client(server) as client:
        listing = await client.list_tools()
    assert set(WRITE_TOOLS) <= {tool.name for tool in listing.tools}


@pytest.mark.anyio
async def test_writes_are_annotated_as_non_destructive_writes(server):
    async with Client(server) as client:
        listing = await client.list_tools()

    for tool in listing.tools:
        if tool.name not in WRITE_TOOLS:
            continue
        assert tool.annotations is not None, tool.name
        assert tool.annotations.read_only_hint is False, tool.name
        assert tool.annotations.destructive_hint is False, tool.name

    upserting = {"record_budget_snapshot", "record_net_worth"}
    async with Client(server) as client:
        for name in upserting:
            tool = await tool_named(client, name)
            assert tool.annotations is not None
            assert tool.annotations.idempotent_hint is True, name


@pytest.mark.anyio
async def test_read_only_mode_hides_every_write_tool(client: VipuClient):
    """Insurance when pointing a new client at live data."""
    async with Client(build_server(client, read_only=True)) as mcp:
        listing = await mcp.list_tools()
    names = {tool.name for tool in listing.tools}
    assert names.isdisjoint(WRITE_TOOLS)
    assert "get_financial_summary" in names


class TestNameResolution:
    """No tool takes a database id."""

    @pytest.mark.anyio
    async def test_resolves_case_insensitively(self, seeded, seeded_server):
        async with Client(seeded_server) as client:
            result = await call(
                client, "set_account_balance", {"name": "cHeCkInG", "balance": 4200}
            )
        assert result["account"]["name"] == "Checking"
        assert result["account"]["balance"] == 4200.0

    @pytest.mark.anyio
    async def test_unknown_name_lists_what_exists(self, seeded_server):
        async with Client(seeded_server) as client:
            message = await call_error(
                client, "set_account_balance", {"name": "Offshore", "balance": 1}
            )
        assert "No account called 'Offshore'" in message
        assert "Checking" in message

    @pytest.mark.anyio
    async def test_ambiguity_names_the_candidates_rather_than_guessing(
        self, seeded, seeded_server, raw
    ):
        """Two accounts differing only in case must not be picked between."""
        raw.post("/api/accounts", json={"name": "checking", "balance": 10})

        async with Client(seeded_server) as client:
            message = await call_error(
                client, "set_account_balance", {"name": "CHECKING", "balance": 1}
            )
        assert "matches more than one account" in message
        assert "Ask which one was meant" in message

    @pytest.mark.anyio
    async def test_an_exact_match_wins_over_a_case_insensitive_one(
        self, seeded, seeded_server, raw
    ):
        """Ambiguity only in casing is still resolvable when one matches exactly."""
        raw.post("/api/accounts", json={"name": "checking", "balance": 10})

        async with Client(seeded_server) as client:
            result = await call(
                client, "set_account_balance", {"name": "Checking", "balance": 55}
            )
        assert result["account"]["name"] == "Checking"

    @pytest.mark.anyio
    async def test_archived_items_are_not_resolvable(self, seeded, seeded_server, raw):
        """An archived line is history; a write must not land on it silently."""
        expense = seeded.list_expenses()[0]
        raw.delete(f"/api/expenses/{expense['id']}")

        async with Client(seeded_server) as client:
            message = await call_error(
                client, "settle_expense", {"name": expense["name"]}
            )
        assert f"No expense called {expense['name']!r}" in message


class TestSetAccountBalance:
    @pytest.mark.anyio
    async def test_returns_the_recomputed_cash_position(self, seeded, seeded_server):
        """One call, and the effect can be narrated without a follow-up read."""
        was = next(a for a in seeded.list_accounts() if a["name"] == "Checking")

        async with Client(seeded_server) as client:
            result = await call(
                client, "set_account_balance", {"name": "Checking", "balance": 1000}
            )

        after = seeded.get_budget()["totals"]
        assert result["previous_balance"] == was["balance"]
        assert result["account"]["balance"] == 1000.0
        assert result["cash_balance"] == after["cash_balance"]
        assert result["card_debt"] == after["card_debt"]
        assert result["cash_low_point"] == after["cash_low_point"]

    @pytest.mark.anyio
    async def test_a_card_takes_a_negative_balance(self, seeded, seeded_server):
        async with Client(seeded_server) as client:
            result = await call(
                client, "set_account_balance", {"name": "Visa", "balance": -450}
            )
        assert result["account"]["balance"] == -450.0
        assert result["card_debt"] <= -450.0

    @pytest.mark.anyio
    async def test_the_backends_validation_message_comes_through(self, seeded_server):
        async with Client(seeded_server) as client:
            message = await call_error(
                client,
                "set_account_balance",
                {"name": "Checking", "balance": 2_000_000_000},
            )
        assert "balance exceeds maximum allowed value" in message


class TestRecordBudgetSnapshot:
    @pytest.mark.anyio
    async def test_captures_balances_and_reports_the_change(
        self, seeded, seeded_server
    ):
        async with Client(seeded_server) as client:
            await call(
                client, "set_account_balance", {"name": "Checking", "balance": 9000}
            )
            result = await call(client, "record_budget_snapshot", {"notes": "payday"})

        assert result["snapshot"]["notes"] == "payday"
        assert result["snapshot"]["current_balance"] == result["current_balance"]
        assert (
            result["cash_low_point"] == seeded.get_budget()["totals"]["cash_low_point"]
        )
        assert "change_from_previous" in result
        assert "pay_period_change" in result

    @pytest.mark.anyio
    async def test_a_second_snapshot_today_replaces_the_first(
        self, seeded, seeded_server
    ):
        before = seeded.list_budget_snapshots()["total"]

        async with Client(seeded_server) as client:
            first = await call(client, "record_budget_snapshot", {})
            second = await call(client, "record_budget_snapshot", {"notes": "again"})

        assert second["replaced_todays_snapshot"] is True
        assert second["snapshot"]["id"] == first["snapshot"]["id"]
        assert second["snapshot"]["notes"] == "again"
        # At most one row was added across the two calls, never two.
        assert seeded.list_budget_snapshots()["total"] <= before + 1

    @pytest.mark.anyio
    async def test_the_ordering_trap_is_stated_in_the_description(self, server):
        """Snapshotting before updating balances records stale figures
        silently, so the description has to say so."""
        async with Client(server) as client:
            tool = await tool_named(client, "record_budget_snapshot")
        description = tool.description or ""
        assert "update them first" in description
        assert "no error and no way" in description


class TestRecordNetWorth:
    @pytest.mark.anyio
    async def test_records_a_month_and_reports_the_change(self, seeded, seeded_server):
        latest = seeded.list_net_worth()[0]
        year, month = (
            (latest["year"] + 1, 1)
            if latest["month"] == 12
            else (latest["year"], latest["month"] + 1)
        )

        async with Client(seeded_server) as client:
            result = await call(
                client,
                "record_net_worth",
                {"year": year, "month": month, "entries": {"Checking": 5000}},
            )

        assert result["replaced_existing_snapshot"] is False
        recorded = seeded.get_net_worth_month(year, month)
        assert recorded is not None
        assert result["net_worth"] == recorded["net_worth"]
        assert result["change_from_previous"] == recorded["change_from_previous"]

    @pytest.mark.anyio
    async def test_carries_forward_and_says_what_it_carried(
        self, seeded, seeded_server
    ):
        latest = seeded.list_net_worth()[0]
        year, month = (
            (latest["year"] + 1, 1)
            if latest["month"] == 12
            else (latest["year"], latest["month"] + 1)
        )

        async with Client(seeded_server) as client:
            result = await call(
                client,
                "record_net_worth",
                {"year": year, "month": month, "entries": {"Checking": 5000}},
            )

        previous_names = {e["category"]["name"] for e in latest["entries"]}
        assert result["carried_forward"]
        assert set(result["carried_forward"]) <= previous_names
        assert "Checking" not in result["carried_forward"]

    @pytest.mark.anyio
    async def test_carry_forward_keeps_liabilities_negative(
        self, seeded, seeded_server
    ):
        """GET .../previous-entries absolutizes; carrying from it would record
        every loan as an asset."""
        latest = seeded.list_net_worth()[0]
        liabilities = {
            e["category"]["name"]: e["amount"]
            for e in latest["entries"]
            if e["amount"] < 0
        }
        assert liabilities, "fixture needs a liability to be meaningful"

        year, month = (
            (latest["year"] + 1, 1)
            if latest["month"] == 12
            else (latest["year"], latest["month"] + 1)
        )
        async with Client(seeded_server) as client:
            await call(
                client,
                "record_net_worth",
                {"year": year, "month": month, "entries": {"Checking": 5000}},
            )

        recorded = seeded.get_net_worth_month(year, month)
        assert recorded is not None
        carried = {
            e["category"]["name"]: e["amount"]
            for e in recorded["entries"]
            if e["category"]["name"] in liabilities
        }
        assert carried == liabilities

    @pytest.mark.anyio
    async def test_carry_forward_can_be_turned_off(self, seeded, seeded_server):
        latest = seeded.list_net_worth()[0]
        year, month = (
            (latest["year"] + 1, 1)
            if latest["month"] == 12
            else (latest["year"], latest["month"] + 1)
        )

        async with Client(seeded_server) as client:
            result = await call(
                client,
                "record_net_worth",
                {
                    "year": year,
                    "month": month,
                    "entries": {"Checking": 5000},
                    "carry_forward_missing": False,
                },
            )

        assert result["carried_forward"] == []
        recorded = seeded.get_net_worth_month(year, month)
        assert recorded is not None
        assert len(recorded["entries"]) == 1

    @pytest.mark.anyio
    async def test_re_recording_a_month_replaces_it(self, seeded, seeded_server):
        latest = seeded.list_net_worth()[0]

        async with Client(seeded_server) as client:
            result = await call(
                client,
                "record_net_worth",
                {
                    "year": latest["year"],
                    "month": latest["month"],
                    "entries": {"Checking": 12345},
                    "carry_forward_missing": False,
                },
            )

        assert result["replaced_existing_snapshot"] is True
        recorded = seeded.get_net_worth_month(latest["year"], latest["month"])
        assert recorded is not None
        assert recorded["id"] == latest["id"]
        assert [e["amount"] for e in recorded["entries"]] == [12345.0]

    @pytest.mark.anyio
    async def test_signs_are_never_flipped(self, seeded, seeded_server):
        """A liability passed positive is recorded as an asset, as documented."""
        liability = next(
            e["category"]["name"]
            for e in seeded.list_net_worth()[0]["entries"]
            if e["amount"] < 0
        )
        async with Client(seeded_server) as client:
            await call(
                client,
                "record_net_worth",
                {
                    "year": 2099,
                    "month": 6,
                    "entries": {liability: 1000},
                    "carry_forward_missing": False,
                },
            )
        recorded = seeded.get_net_worth_month(2099, 6)
        assert recorded is not None
        assert recorded["entries"][0]["amount"] == 1000.0

    @pytest.mark.anyio
    async def test_an_unknown_category_writes_nothing(self, seeded, seeded_server):
        """Every name resolves before anything is recorded."""
        async with Client(seeded_server) as client:
            message = await call_error(
                client,
                "record_net_worth",
                {
                    "year": 2099,
                    "month": 7,
                    "entries": {"Checking": 1, "Doubloons": 2},
                },
            )
        assert "No net worth category called 'Doubloons'" in message
        assert seeded.get_net_worth_month(2099, 7) is None

    @pytest.mark.anyio
    async def test_the_sign_convention_is_in_the_description(self, server):
        async with Client(server) as client:
            tool = await tool_named(client, "record_net_worth")
        description = tool.description or ""
        assert "Liabilities are stored negative" in description
        assert "signs are never flipped" in description


class TestSettle:
    @pytest.mark.anyio
    async def test_settling_a_bill_drops_it_from_the_period_total(
        self, seeded, seeded_server
    ):
        totals = seeded.get_budget()["totals"]
        row = next(
            r
            for r in totals["expenses_before_payday_list"]
            if r["can_settle"] and not r["is_settled"]
        )
        before = totals["period_current"]["bills"]

        async with Client(seeded_server) as client:
            result = await call(
                client,
                "settle_expense",
                {"name": row["name"], "occurrence_date": row["next_occurrence_date"]},
            )

        after = seeded.get_budget()["totals"]
        assert after["period_current"]["bills"] < before
        assert result["period_current_net"] == after["period_current"]["net"]

        # It stays on the list, flagged, rather than disappearing.
        settled_row = next(
            r
            for r in after["expenses_before_payday_list"]
            if r["id"] == row["id"]
            and r["next_occurrence_date"] == row["next_occurrence_date"]
        )
        assert settled_row["is_settled"] is True

    @pytest.mark.anyio
    async def test_settling_defaults_to_the_next_occurrence(
        self, seeded, seeded_server
    ):
        totals = seeded.get_budget()["totals"]
        today = totals["period_current"]["start"]
        row = next(
            r
            for r in totals["expenses_before_payday_list"]
            if r["can_settle"] and r["next_occurrence_date"] > today
        )

        async with Client(seeded_server) as client:
            result = await call(client, "settle_expense", {"name": row["name"]})

        assert result["occurrence_date"] == row["next_occurrence_date"]
        assert result["occurrence_date"] > today

    @pytest.mark.anyio
    async def test_unsettling_puts_a_bill_back(self, seeded, seeded_server):
        totals = seeded.get_budget()["totals"]
        row = next(
            r
            for r in totals["expenses_before_payday_list"]
            if r["can_settle"] and r["is_settled"]
        )
        before = totals["period_current"]["bills"]

        async with Client(seeded_server) as client:
            await call(
                client,
                "settle_expense",
                {
                    "name": row["name"],
                    "occurrence_date": row["next_occurrence_date"],
                    "settled": False,
                },
            )

        after = seeded.get_budget()["totals"]
        assert after["period_current"]["bills"] > before

    @pytest.mark.anyio
    async def test_a_date_outside_the_window_gets_the_backends_own_message(
        self, seeded_server
    ):
        async with Client(seeded_server) as client:
            message = await call_error(
                client,
                "settle_expense",
                {"name": "Rent", "occurrence_date": "2030-01-01"},
            )
        assert (
            "occurrence_date must be this item's next occurrence or its most "
            "recent one this pay period" in message
        )

    @pytest.mark.anyio
    async def test_settling_income(self, seeded, seeded_server):
        row = next(r for r in seeded.get_budget()["income"] if r["can_settle"])

        async with Client(seeded_server) as client:
            result = await call(client, "settle_income", {"name": row["name"]})

        assert result["occurrence_date"] == row["next_occurrence_date"]
        assert result["income"]["settled_occurrence"] == row["next_occurrence_date"]
        assert result["period_current_net"] == (
            seeded.get_budget()["totals"]["period_current"]["net"]
        )

    @pytest.mark.anyio
    async def test_both_meanings_are_in_the_description(self, server):
        async with Client(server) as client:
            tool = await tool_named(client, "settle_expense")
        description = tool.description or ""
        assert "already moved ahead of its day" in description
        assert "passed without the money moving" in description
