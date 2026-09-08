"""Shared helpers for driving the server through the in-memory client."""

import json
from typing import Any

from mcp.client import Client
from mcp.types import CallToolResult, TextContent, Tool


def text_of(result: CallToolResult) -> str:
    """The one text block of a tool result."""
    block = result.content[0]
    assert isinstance(block, TextContent), block
    return block.text


async def tool_named(client: Client, name: str) -> Tool:
    """The one listed tool called ``name``."""
    listing = await client.list_tools()
    return next(tool for tool in listing.tools if tool.name == name)


async def call(
    client: Client, name: str, arguments: dict[str, Any] | None = None
) -> Any:
    """Call a tool, assert it succeeded, and return its result as data."""
    result = await client.call_tool(name, arguments or {})
    assert result.is_error is False, result.content
    if result.structured_content is not None:
        content = result.structured_content
        # The SDK wraps a scalar return in {"result": ...} and passes a dict
        # return through unchanged.
        return content.get("result", content) if "result" in content else content
    return json.loads(text_of(result))


async def call_error(
    client: Client, name: str, arguments: dict[str, Any] | None = None
) -> str:
    """Call a tool expecting it to fail, and return the message it gave."""
    result = await client.call_tool(name, arguments or {})
    assert result.is_error is True, result.content
    return text_of(result)
