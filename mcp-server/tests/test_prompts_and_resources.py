"""Prompts and resources, against the real Flask app."""

import json

import pytest
from mcp.client import Client

from vipu_mcp.client import VipuClient
from vipu_mcp.server import build_server

PROMPTS = ["monthly_review", "record_the_month", "what_if"]
RESOURCES = ["vipu://summary", "vipu://budget"]


async def prompt_named(client: Client, name: str):
    listing = await client.list_prompts()
    return next(prompt for prompt in listing.prompts if prompt.name == name)


async def rendered(client: Client, name: str, arguments: dict | None = None) -> str:
    result = await client.get_prompt(name, arguments or {})
    return "\n".join(
        message.content.text
        for message in result.messages
        if message.content.type == "text"
    )


class TestPrompts:
    @pytest.mark.anyio
    async def test_every_ritual_is_listed(self, server):
        async with Client(server) as client:
            listing = await client.list_prompts()
        assert {p.name for p in listing.prompts} == set(PROMPTS)

    @pytest.mark.anyio
    async def test_each_prompt_describes_itself(self, server):
        async with Client(server) as client:
            listing = await client.list_prompts()
        for prompt in listing.prompts:
            assert prompt.description, prompt.name
            assert prompt.title, prompt.name

    @pytest.mark.anyio
    async def test_arguments_are_optional(self, server):
        """Every one has to be usable straight from Desktop's picker."""
        async with Client(server) as client:
            listing = await client.list_prompts()
        for prompt in listing.prompts:
            for argument in prompt.arguments or []:
                assert argument.required is not True, (prompt.name, argument.name)

    @pytest.mark.parametrize("name", PROMPTS)
    @pytest.mark.anyio
    async def test_each_renders_with_and_without_its_argument(self, server, name):
        argument = "scenario" if name == "what_if" else "month"
        async with Client(server) as client:
            bare = await rendered(client, name)
            filled = await rendered(client, name, {argument: "2026-08"})
        assert bare.strip()
        assert filled.strip()
        assert bare != filled

    @pytest.mark.anyio
    async def test_monthly_review_names_its_starting_point(self, server):
        async with Client(server) as client:
            text = await rendered(client, "monthly_review")
        assert "Call get_financial_summary first" in text
        assert "If cash_low_point is negative, lead with it" in text
        assert "list_budget_snapshots" in text

    @pytest.mark.anyio
    async def test_record_the_month_fixes_the_order(self, server):
        """Snapshotting before the balances are updated records stale figures
        with no error, so the prompt has to say so where it cannot be missed."""
        async with Client(server) as client:
            text = await rendered(client, "record_the_month")

        balances = text.index("Account balances first")
        snapshot = text.index("Then the budget snapshot")
        net_worth = text.index("Then net worth")
        assert balances < snapshot < net_worth
        assert "no error and no way to notice" in text
        assert "which categories were carried forward" in text

    @pytest.mark.anyio
    async def test_what_if_carries_the_scenario_into_the_text(self, server):
        async with Client(server) as client:
            text = await rendered(client, "what_if", {"scenario": "I save 300 more"})
        assert "I save 300 more" in text
        assert "Report the `delta` block, not the raw numbers" in text

    @pytest.mark.anyio
    async def test_what_if_asks_when_given_nothing(self, server):
        async with Client(server) as client:
            text = await rendered(client, "what_if")
        assert "Ask me what change I have in mind" in text

    @pytest.mark.anyio
    async def test_read_only_mode_drops_the_recording_ritual(self, client: VipuClient):
        """Offering it with no write tools would be offering a dead end."""
        async with Client(build_server(client, read_only=True)) as mcp:
            listing = await mcp.list_prompts()
        names = {prompt.name for prompt in listing.prompts}
        assert "record_the_month" not in names
        assert {"monthly_review", "what_if"} <= names


class TestResources:
    @pytest.mark.anyio
    async def test_both_are_listed_with_their_types(self, server):
        async with Client(server) as client:
            listing = await client.list_resources()
        by_uri = {str(resource.uri): resource for resource in listing.resources}
        assert set(by_uri) == set(RESOURCES)
        assert by_uri["vipu://summary"].mime_type == "text/markdown"
        assert by_uri["vipu://budget"].mime_type == "application/json"
        for resource in listing.resources:
            assert resource.description

    @pytest.mark.anyio
    async def test_summary_is_the_digest(self, seeded, seeded_server):
        async with Client(seeded_server) as client:
            result = await client.read_resource("vipu://summary")
        text = result.contents[0].text
        assert text == seeded.get_summary()["markdown"]
        assert text.startswith("# Vipu financial snapshot")

    @pytest.mark.anyio
    async def test_budget_is_the_structured_payload(self, seeded, seeded_server):
        async with Client(seeded_server) as client:
            result = await client.read_resource("vipu://budget")
        payload = json.loads(result.contents[0].text)
        expected = seeded.get_budget()
        assert (
            payload["totals"]["cash_low_point"] == expected["totals"]["cash_low_point"]
        )
        assert [a["name"] for a in payload["accounts"]] == [
            a["name"] for a in expected["accounts"]
        ]

    @pytest.mark.anyio
    async def test_resources_stay_available_in_read_only_mode(self, client: VipuClient):
        async with Client(build_server(client, read_only=True)) as mcp:
            listing = await mcp.list_resources()
        assert {str(r.uri) for r in listing.resources} == set(RESOURCES)
