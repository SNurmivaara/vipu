"""The transport, the tool surface and the one tool on it."""

import pytest
from mcp.client import Client


@pytest.mark.anyio
async def test_lists_exactly_the_summary_tool(server):
    """The thin slice is one tool; breadth comes in later issues."""
    async with Client(server) as client:
        listing = await client.list_tools()
    assert [tool.name for tool in listing.tools] == ["get_financial_summary"]


@pytest.mark.anyio
async def test_summary_tool_is_annotated_read_only(server):
    """Nothing in GET /api/summary writes, and the annotation says so."""
    async with Client(server) as client:
        listing = await client.list_tools()
    tool = listing.tools[0]
    assert tool.annotations is not None
    assert tool.annotations.read_only_hint is True


@pytest.mark.anyio
async def test_description_carries_the_framing(server):
    """The description is the product: a model calling this in isolation still
    has to learn the caveats the digest itself states."""
    async with Client(server) as client:
        listing = await client.list_tools()
    description = listing.tools[0].description or ""
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
    assert result.content[0].text == expected
    assert "# Vipu financial snapshot" in expected


@pytest.mark.anyio
async def test_works_against_an_empty_backend(server):
    """An unseeded database is a valid state, not an error."""
    async with Client(server) as client:
        result = await client.call_tool("get_financial_summary", {})
    assert result.is_error is False
    assert "no net worth snapshots recorded yet" in result.content[0].text.lower()
