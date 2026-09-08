"""Resources: state a client can attach to a conversation without a tool call.

That matters for the opening turn of any of the prompts, where the model would
otherwise have to spend a round trip fetching what it is about to discuss.
"""

import json

from mcp.server.mcpserver import MCPServer

from vipu_mcp.client import VipuClient

SUMMARY_DESCRIPTION = (
    "The whole of the user's finances as one markdown document: current "
    "position, monthly rates, every line, the roadmap, net worth and FIRE, "
    "with the caveats that make those figures readable. Same content as the "
    "get_financial_summary tool."
)

BUDGET_DESCRIPTION = (
    "The current budget as structured data: accounts, income, expenses, both "
    "pay-period flows, the cash low point and the occurrence lists. Reading it "
    "performs the same housekeeping GET /api/budget/current does, clearing "
    "occurrence overrides the calendar has caught up with and archiving past "
    "one-time items."
)


def register(server: MCPServer, client: VipuClient) -> None:
    """Register the state resources on ``server``."""

    @server.resource(
        "vipu://summary",
        name="summary",
        title="Financial summary",
        description=SUMMARY_DESCRIPTION,
        mime_type="text/markdown",
    )
    def summary() -> str:
        """The digest, as markdown."""
        return str(client.get_summary()["markdown"])

    @server.resource(
        "vipu://budget",
        name="budget",
        title="Current budget",
        description=BUDGET_DESCRIPTION,
        mime_type="application/json",
    )
    def budget() -> str:
        """The current budget, as JSON."""
        return json.dumps(client.get_budget(), indent=2)
