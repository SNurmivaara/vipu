"""Tools for reading and talking about the current position."""

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from vipu_mcp.client import VipuClient

SUMMARY_DESCRIPTION = """\
The whole of the user's finances as one markdown document. Call this first for \
any open-ended question about how they are doing; the more specific tools are \
for drilling in afterwards.

It covers the current cash position and the two pay periods ahead, the \
frequency-normalized monthly rates, every income, account and expense line, the \
financial roadmap, net worth and its trend, and the FIRE projection. It also \
states the caveats that make those figures readable: the budget section is live \
while the wealth section is a monthly snapshot and can lag it by weeks, a card \
balance is charged once rather than in every period, settled occurrences are \
listed but excluded from the period totals, and goal progress is zero-growth \
linear while FIRE compounds.\
"""


def register(server: MCPServer, client: VipuClient) -> None:
    """Register the read tools on ``server``."""

    @server.tool(
        name="get_financial_summary",
        title="Financial summary",
        description=SUMMARY_DESCRIPTION,
        annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True),
    )
    def get_financial_summary() -> str:
        """The whole app state as one markdown digest."""
        return str(client.get_summary()["markdown"])
