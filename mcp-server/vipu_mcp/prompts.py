"""Prompts for the monthly rituals.

Tools make things possible; prompts make them habitual. The point of an
AI-first Vipu is that the monthly ritual is one click and a conversation, not a
remembered sequence of tool calls.

Each prompt works with no arguments and takes one where it helps.
"""

from mcp.server.mcpserver import MCPServer

MONTHLY_REVIEW = """\
Walk me through where my finances stand{when}.

Do this in order:

1. Call get_financial_summary first. Everything below is a reading of that one \
document, not a fresh set of lookups.
2. Report the current position in plain terms: cash in the accounts, what the \
cards owe, what is still to happen before the next payday, and where the \
balance is projected to be at payday and at the end of the following period.
3. If cash_low_point is negative, lead with it. It means the account goes under \
before the pay that covers those bills arrives, so say when and by how much. If \
it is positive, say so in one line and move on.
4. Check each roadmap goal against its projected completion date, and each net \
worth goal against its pace. Where the linear pace and the FIRE projection \
disagree about a target, say which is which rather than picking one; goal math \
assumes no growth and FIRE compounds.
5. Finish with what has changed since the last budget snapshot. Use \
list_budget_snapshots for that, and read pay_period_change rather than \
change_from_previous when the question is how far through this period's money \
we are.

Be concrete about amounts and dates. Flag anything that looks like a mistake in \
the data rather than reporting it as fact.\
"""

RECORD_THE_MONTH = """\
Help me record{when}. Follow this order exactly, and do not skip ahead.

**1. Account balances first.** Ask me for the current balance of each account \
and card, in one message listing them all rather than one question at a time. \
Use get_budget to see what exists and what it currently says. Record each with \
set_account_balance. Card balances are negative: 450 owed is -450.

**2. Then the budget snapshot.** Only once every balance is updated, call \
record_budget_snapshot. It captures whatever the balances currently are, so \
snapshotting before updating them records stale figures with no error and no \
way to notice afterwards. Report the change_from_previous it returns.

**3. Then net worth.** Ask me for the categories that have moved. Call \
record_net_worth with just those, and let carry_forward_missing fill the rest \
from last month. Then tell me exactly which categories were carried forward, \
so I know which figures you did not actually ask me about. Liabilities are \
negative: a 180000 mortgage is -180000.

Finish by reporting the new net worth and its change from last month, and \
whether the cash low point moved into or out of negative territory.\
"""

WHAT_IF = """\
{opening}

Work it through like this:

1. Read the proposal and decide which project_fire parameters it maps to. \
"Save 300 more a month" is monthly_contribution raised by 300 from the current \
figure; "retire at 55" is target_retirement_age; "if returns are only 4%" is \
annual_return_pct. Call get_fire_projection first if you need the current \
figures to adjust from.
2. Call project_fire with only the parameters the proposal actually changes. \
Everything else defaults to my current situation.
3. Report the `delta` block, not the raw numbers. "That pulls FIRE forward by \
2.6 years" is the answer; "years_to_fire is 14.2" is not. Note that \
project_fire's absolute figures use a simpler model than the app's own \
projection, so quote the difference from project_fire and the levels from \
get_fire_projection.
4. Say plainly what the change would cost or require in practice, and whether \
it is the sort of change that has to hold for decades to pay off.

Nothing is stored, so try variations freely. Only call \
update_forecasting_settings if I ask you to make one of them permanent.\
"""


def register(server: MCPServer, read_only: bool = False) -> None:
    """Register the ritual prompts on ``server``."""

    @server.prompt(
        name="monthly_review",
        title="Monthly review",
        description=(
            "Walk through the current position, flag the cash low point, check "
            "goals against pace, and report what changed since the last budget "
            "snapshot."
        ),
    )
    def monthly_review(month: str = "") -> str:
        """The "how am I doing?" conversation, in a fixed order."""
        return MONTHLY_REVIEW.format(when=f" for {month}" if month else "")

    @server.prompt(
        name="what_if",
        title="What if",
        description=(
            "Take a proposed change in plain language, run it through "
            "project_fire, and report the delta rather than raw numbers."
        ),
    )
    def what_if(scenario: str = "") -> str:
        """The planning conversation, framed as a comparison."""
        opening = (
            f"I want to know what would happen if {scenario}."
            if scenario
            else "I want to try a what-if against my FIRE projection. Ask me "
            "what change I have in mind if I have not already said."
        )
        return WHAT_IF.format(opening=opening)

    if read_only:
        # Nothing to record with: the write tools are not registered, so
        # offering the ritual would be offering a dead end.
        return

    @server.prompt(
        name="record_the_month",
        title="Record the month",
        description=(
            "Update account balances, take a budget snapshot, then record net "
            "worth, in that order. Snapshotting before the balances are "
            "updated records stale figures silently."
        ),
    )
    def record_the_month(month: str = "") -> str:
        """The monthly recording ritual, in the only order that is correct."""
        return RECORD_THE_MONTH.format(when=f" {month}" if month else " this month")
