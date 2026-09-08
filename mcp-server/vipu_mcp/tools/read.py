"""Tools for reading and talking about the current position.

The descriptions here are the product, not an afterthought. A model calling one
of these in isolation still has to get the framing the digest would have given
it, so each one states the domain rules that make its numbers readable.
"""

from typing import Any

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

BUDGET_DESCRIPTION = """\
The full current budget: accounts, income and expense lines, both pay-period \
flows, the cash low point, and the per-occurrence lists for this period and the \
next.

Reading this performs housekeeping. It clears occurrence overrides the calendar \
has caught up with and archives one-time items whose day has passed, then \
commits. Nothing a user cares about is lost, but it is not a pure read, which \
is why it is not annotated read-only.

How to read the result:

- A card balance is charged once, on its first due day from today, not in every \
period. `card_debt` is what the cards owe; `cash_balance` is what is actually \
in the non-credit accounts.
- Settled occurrences stay in the occurrence lists, flagged `is_settled`, but \
are excluded from the period totals. The lines will not add up to the total, \
and that is correct.
- `cash_low_point.balance` below zero means the account goes under before the \
pay that covers those bills arrives. The period can still end comfortably.
- `total_expenses` and `net_income` are face-value sums of every active line. \
`monthly_expenses`, `monthly_net_income` and `monthly_surplus` are the \
frequency-normalized rates: a quarterly bill counts as a third, a yearly one as \
a twelfth, and one-time items are excluded entirely. The monthly rates are what \
fund the roadmap and FIRE; the face-value totals are not.\
"""

NET_WORTH_DESCRIPTION = """\
Net worth snapshots, newest first, with the latest one's group and category \
breakdown.

Snapshots are monthly, so this can lag the budget by weeks. For current cash \
prefer get_budget; the same account will legitimately show different figures in \
the two places, each correct as of its own date.

Liabilities are stored negative in `entries`. The `liabilities_by_group` and \
`liabilities_by_category` blocks restate them as positive magnitudes, since a \
forecast reads those as balances to pay down. `by_group` and `percentages` \
cover assets only, so the two breakdowns do not reconcile into one column.\
"""

GOALS_DESCRIPTION = """\
Every goal, in one result: the sequential roadmap with its projected completion \
dates, and the per-goal pace analysis.

Roadmap steps (savings_goal and debt_payoff) are funded in priority order by \
the monthly surplus, waterfall style: the whole surplus fills the first \
unfinished step, then cascades. Projected dates walk real pay periods, so a \
yearly bill delays the step it lands on rather than being smeared across every \
month.

The progress and required-monthly figures are zero-growth linear: they assume \
no investment return. get_fire_projection compounds instead, so the two can \
disagree about whether the same target is reachable. Neither is wrong; they \
answer different questions.\
"""

FIRE_DESCRIPTION = """\
The FIRE projection computed from the persisted settings, the latest net worth \
snapshot and the current budget. Nothing is stored; it is recomputed on each \
call.

The `derived` block names its own inputs and flags which are overrides. That \
matters: when `monthly_savings_is_override` is true, the figure driving the \
projection is a manual number and not the budget's own surplus, and the two \
will differ on screen for a reason.

Each asset group compounds at its own rate, so the mix drifts toward the faster \
groups and the blended return rises over the projection. `years_to_fire` is \
when the portfolio covers expenses, which is when work becomes optional, not \
the planned retirement age in `target_retirement_age`.\
"""

SNAPSHOTS_DESCRIPTION = """\
Recorded budget snapshots, newest first: the cash history behind "how did last \
month go?".

`change_from_previous` compares against the previous snapshot whenever it was \
taken. `pay_period_change` compares against the last snapshot of the previous \
pay period, so it answers "how far through this period's money are we?" rather \
than "what changed since I last looked?". `pay_period_start` is the payday that \
opened the period a snapshot belongs to.\
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

    @server.tool(
        name="get_budget",
        title="Current budget",
        description=BUDGET_DESCRIPTION,
        annotations=ToolAnnotations(
            # GET /api/budget/current commits housekeeping, so this is not a
            # read. It is idempotent: running it twice changes nothing further.
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
        ),
    )
    def get_budget() -> dict[str, Any]:
        """Accounts, income, expenses, both period flows and the low point."""
        return client.get_budget()

    @server.tool(
        name="get_net_worth",
        title="Net worth",
        description=NET_WORTH_DESCRIPTION,
        annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True),
    )
    def get_net_worth(limit: int = 12) -> dict[str, Any]:
        """Snapshots newest first, capped at ``limit``, plus the latest one."""
        snapshots = client.list_net_worth()
        capped = snapshots[: max(1, limit)] if snapshots else []
        return {
            "snapshots": capped,
            "latest": capped[0] if capped else None,
            "total": len(snapshots),
        }

    @server.tool(
        name="get_goals",
        title="Goals and roadmap",
        description=GOALS_DESCRIPTION,
        annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True),
    )
    def get_goals() -> dict[str, Any]:
        """Roadmap and per-goal progress merged into one result.

        Two backing calls is an implementation detail the model should not have
        to know about, so they are merged here rather than split into two tools.
        """
        roadmap = client.get_roadmap()
        return {
            "surplus_monthly": roadmap["surplus_monthly"],
            "starting_position": roadmap["starting_position"],
            "pending_one_time_net": roadmap["pending_one_time_net"],
            "shortfall_months": roadmap["shortfall_months"],
            "roadmap": roadmap["goals"],
            "progress": client.get_goal_progress(),
        }

    @server.tool(
        name="get_fire_projection",
        title="FIRE projection",
        description=FIRE_DESCRIPTION,
        annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True),
    )
    def get_fire_projection(include_monthly_points: bool = False) -> dict[str, Any]:
        """The stored projection.

        ``projections`` is a month-by-month walk to life expectancy, which is
        hundreds of rows of no use in a conversation, so it is dropped unless
        asked for.
        """
        projection = client.get_projection()
        if not include_monthly_points:
            points = projection.pop("projections", [])
            projection["projection_points_omitted"] = len(points)
        return projection

    @server.tool(
        name="list_budget_snapshots",
        title="Budget snapshots",
        description=SNAPSHOTS_DESCRIPTION,
        annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True),
    )
    def list_budget_snapshots(limit: int = 12, offset: int = 0) -> dict[str, Any]:
        """Recorded cash history, newest first."""
        return client.list_budget_snapshots(limit=limit, offset=offset)
