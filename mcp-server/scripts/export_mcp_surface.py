#!/usr/bin/env python3
"""Print the MCP surface (instructions, tools, prompts, resources) as JSON.

The surface is what a client sees, so a refactoring must leave this output
unchanged. Both the full and the read-only registrations are listed, since the
read-only flag changes which tools and prompts exist. Listing runs in memory
and never calls the backend.
"""

import json
import sys
from pathlib import Path
from typing import Any

import anyio
from mcp.client import Client

sys.path.insert(0, str(Path(__file__).parent.parent))

from vipu_mcp.client import VipuClient
from vipu_mcp.server import build_server


async def _surface(read_only: bool) -> dict[str, Any]:
    server = build_server(VipuClient(base_url="http://unused"), read_only=read_only)
    async with Client(server) as client:
        instructions = client.instructions
        tools = (await client.list_tools()).tools
        prompts = (await client.list_prompts()).prompts
        resources = (await client.list_resources()).resources
        templates = (await client.list_resource_templates()).resource_templates

    def dump(items: list[Any], key: str) -> list[dict[str, Any]]:
        dumped = [item.model_dump(mode="json", exclude_none=True) for item in items]
        return sorted(dumped, key=lambda item: str(item[key]))

    return {
        "instructions": instructions,
        "tools": dump(tools, "name"),
        "prompts": dump(prompts, "name"),
        "resources": dump(resources, "uri"),
        "resource_templates": dump(templates, "uriTemplate"),
    }


async def _main() -> None:
    surface = {
        "full": await _surface(read_only=False),
        "read_only": await _surface(read_only=True),
    }
    print(json.dumps(surface, indent=2, sort_keys=True))


if __name__ == "__main__":
    anyio.run(_main)
