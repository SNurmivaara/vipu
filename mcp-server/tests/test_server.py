"""The transport, the tool surface and the one tool on it."""

import pytest
from mcp.client import Client

from tests.helpers import text_of, tool_named


@pytest.mark.anyio
async def test_summary_tool_is_registered(server):
    """The entry point for any open-ended question."""
    async with Client(server) as client:
        listing = await client.list_tools()
    assert "get_financial_summary" in [tool.name for tool in listing.tools]


@pytest.mark.anyio
async def test_summary_tool_is_annotated_read_only(server):
    """Nothing in GET /api/summary writes, and the annotation says so."""
    async with Client(server) as client:
        tool = await tool_named(client, "get_financial_summary")
    assert tool.annotations is not None
    assert tool.annotations.read_only_hint is True


@pytest.mark.anyio
async def test_description_carries_the_framing(server):
    """The description is the product: a model calling this in isolation still
    has to learn the caveats the digest itself states."""
    async with Client(server) as client:
        tool = await tool_named(client, "get_financial_summary")
    description = tool.description or ""
    assert "Call this first" in description
    assert "charged once" in description
    assert "zero-growth linear" in description


@pytest.mark.anyio
async def test_returns_the_same_markdown_as_the_api(seeded, seeded_server):
    """The tool is a pass-through; any divergence is a bug in the wrapper."""
    expected = seeded.get_summary()["markdown"]
    async with Client(seeded_server) as client:
        result = await client.call_tool("get_financial_summary", {})
    assert result.is_error is False
    assert text_of(result) == expected
    assert "# Vipu financial snapshot" in expected


@pytest.mark.anyio
async def test_works_against_an_empty_backend(server):
    """An unseeded database is a valid state, not an error."""
    async with Client(server) as client:
        result = await client.call_tool("get_financial_summary", {})
    assert result.is_error is False
    assert "no net worth snapshots recorded yet" in text_of(result).lower()
