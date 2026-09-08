"""Read tools, against the real Flask app."""

import pytest
from mcp.client import Client

from tests.helpers import call, tool_named

READ_TOOLS = [
    "get_financial_summary",
    "get_budget",
    "get_net_worth",
    "get_goals",
    "get_fire_projection",
    "list_budget_snapshots",
]


@pytest.mark.anyio
async def test_every_read_tool_is_registered(server):
    async with Client(server) as client:
        listing = await client.list_tools()
    names = [tool.name for tool in listing.tools]
    assert set(READ_TOOLS) <= set(names)


@pytest.mark.anyio
async def test_only_get_budget_is_not_read_only(server):
    """GET /api/budget/current clears stale overrides and archives, then
    commits. Marking it read-only would be a lie."""
    async with Client(server) as client:
        listing = await client.list_tools()

    for tool in listing.tools:
        if tool.name not in READ_TOOLS:
            continue
        assert tool.annotations is not None, tool.name
        if tool.name == "get_budget":
            assert tool.annotations.read_only_hint is False
            assert tool.annotations.destructive_hint is False
            assert tool.annotations.idempotent_hint is True
        else:
            assert tool.annotations.read_only_hint is True, tool.name


@pytest.mark.anyio
async def test_get_budget_description_mentions_the_housekeeping(server):
    async with Client(server) as client:
        tool = await tool_named(client, "get_budget")
    description = tool.description or ""
    assert "housekeeping" in description
    assert "not a pure read" in description


@pytest.mark.parametrize(
    ("name", "phrase"),
    [
        ("get_budget", "charged once, on its first due day from today"),
        ("get_budget", "excluded from the period totals"),
        ("get_budget", "frequency-normalized rates"),
        ("get_net_worth", "monthly, so this can lag the budget by weeks"),
        ("get_net_worth", "stored negative"),
        ("get_goals", "zero-growth linear"),
        ("get_fire_projection", "flags which are overrides"),
    ],
)
@pytest.mark.anyio
async def test_descriptions_carry_the_domain_caveats(server, name, phrase):
    """A model calling one of these in isolation still needs the framing."""
    async with Client(server) as client:
        tool = await tool_named(client, name)
    assert phrase in (tool.description or "")


@pytest.mark.anyio
async def test_get_budget_matches_the_endpoint(seeded, seeded_server):
    """Specifically the cash low point, which nothing else recomputes."""
    expected = seeded.get_budget()
    async with Client(seeded_server) as client:
        result = await call(client, "get_budget")

    assert result["totals"]["cash_low_point"] == expected["totals"]["cash_low_point"]
    assert result["totals"]["period_current"] == expected["totals"]["period_current"]
    assert result["totals"]["period_next"] == expected["totals"]["period_next"]
    assert [a["name"] for a in result["accounts"]] == [
        a["name"] for a in expected["accounts"]
    ]


@pytest.mark.anyio
async def test_get_net_worth_is_newest_first_and_capped(seeded, seeded_server):
    async with Client(seeded_server) as client:
        result = await call(client, "get_net_worth", {"limit": 3})

    everything = seeded.list_net_worth()
    assert result["total"] == len(everything)
    assert len(result["snapshots"]) == 3
    assert result["latest"] == everything[0]

    months = [(s["year"], s["month"]) for s in result["snapshots"]]
    assert months == sorted(months, reverse=True)


@pytest.mark.anyio
async def test_get_net_worth_carries_the_latest_breakdown(seeded_server):
    """The group and category split is the reason to call this over the digest."""
    async with Client(seeded_server) as client:
        result = await call(client, "get_net_worth")
    latest = result["latest"]
    assert latest["by_group"]
    assert latest["entries"]
    assert "percentages" in latest


@pytest.mark.anyio
async def test_get_net_worth_survives_an_empty_history(server):
    async with Client(server) as client:
        result = await call(client, "get_net_worth")
    assert result == {"snapshots": [], "latest": None, "total": 0}


@pytest.mark.anyio
async def test_get_goals_merges_both_payloads_without_dropping_fields(
    seeded, seeded_server
):
    roadmap = seeded.get_roadmap()
    progress = seeded.get_goal_progress()

    async with Client(seeded_server) as client:
        result = await call(client, "get_goals")

    assert result["roadmap"] == roadmap["goals"]
    assert result["progress"] == progress
    for key in ("surplus_monthly", "starting_position", "pending_one_time_net"):
        assert result[key] == roadmap[key]
    assert result["shortfall_months"] == roadmap["shortfall_months"]


@pytest.mark.anyio
async def test_get_fire_projection_drops_the_monthly_walk_by_default(
    seeded, seeded_server
):
    """Hundreds of month rows are no use in a conversation."""
    stored = seeded.get_projection()
    assert len(stored["projections"]) > 12

    async with Client(seeded_server) as client:
        result = await call(client, "get_fire_projection")

    assert "projections" not in result
    assert result["projection_points_omitted"] == len(stored["projections"])
    assert result["fire_number"] == stored["fire_number"]
    assert result["derived"]["monthly_savings"] == stored["derived"]["monthly_savings"]


@pytest.mark.anyio
async def test_get_fire_projection_can_include_the_walk(seeded, seeded_server):
    async with Client(seeded_server) as client:
        result = await call(
            client, "get_fire_projection", {"include_monthly_points": True}
        )
    assert result["projections"] == seeded.get_projection()["projections"]


@pytest.mark.anyio
async def test_list_budget_snapshots_carries_pay_period_fields(seeded, seeded_server):
    """pay_period_change is the figure the digest cannot give you."""
    async with Client(seeded_server) as client:
        result = await call(client, "list_budget_snapshots", {"limit": 5})

    expected = seeded.list_budget_snapshots(limit=5)
    assert result["total"] == expected["total"]
    assert len(result["snapshots"]) == len(expected["snapshots"])
    for snapshot in result["snapshots"]:
        assert "pay_period_change" in snapshot
        assert "pay_period_start" in snapshot

    dates = [s["date"] for s in result["snapshots"]]
    assert dates == sorted(dates, reverse=True)


@pytest.mark.anyio
async def test_list_budget_snapshots_pages(seeded, seeded_server):
    async with Client(seeded_server) as client:
        first = await call(client, "list_budget_snapshots", {"limit": 2})
        second = await call(client, "list_budget_snapshots", {"limit": 2, "offset": 2})
    assert first["snapshots"] != second["snapshots"]
    assert first["total"] == second["total"]
