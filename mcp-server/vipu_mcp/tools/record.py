"""Tools for recording what happened: balances, snapshots and occurrences.

Two of the four things this project exists to make conversational live here.
Every tool resolves items by name, and every write answers with the recomputed
state the user actually cares about, so the model can narrate the effect without
a second read.
"""

from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from vipu_mcp import resolve
from vipu_mcp.client import VipuClient

SET_BALANCE_DESCRIPTION = """\
Set one account's balance to what the bank actually says, by account name.

Credit cards are stored negative: -450 means 450 owed. Returns the recomputed \
cash_balance, card_debt and cash low point, so the effect can be reported \
without a follow-up read.

This is how spending gets recorded. Vipu is balance-based and has no \
transactions, so there is nothing to log line by line; the balance is the \
record.\
"""

RECORD_SNAPSHOT_DESCRIPTION = """\
Take a budget snapshot: freeze today's account balances as a point in the cash \
history.

It captures whatever the balances currently are, so update them first. \
Snapshotting stale balances records the wrong figures with no error and no way \
to notice afterwards.

Upserts on today's date: taking a second snapshot today overwrites the first \
rather than adding one.

Returns the new change_from_previous and pay_period_change alongside the \
recomputed cash low point.\
"""

RECORD_NET_WORTH_DESCRIPTION = """\
Record the month's net worth from a mapping of category name to amount.

Liabilities are stored negative: a 180000 mortgage is -180000. Amounts are \
taken exactly as given and signs are never flipped, so a liability passed as a \
positive number will be recorded as an asset.

carry_forward_missing (default true) fills any category not mentioned with last \
month's figure, which is what the web form does. The result lists which \
categories were carried forward, so the ones that were never actually asked \
about can be named rather than silently vouched for. Set it false to record \
only the categories given and leave the rest out of the snapshot entirely.

Upserts by month: recording a month that already has a snapshot replaces its \
entries.\
"""

SETTLE_DESCRIPTION = """\
Correct the timing of one {kind} occurrence without moving the schedule.

settled=true for money that has already moved ahead of its day. settled=false \
for a day that has passed without the money moving. Only that occurrence \
changes; later ones keep the original schedule.

occurrence_date must be either the item's next occurrence or the most recent \
one that has come due this pay period. Anything else is a schedule edit rather \
than a timing correction, and is rejected. Omit it to mean the next occurrence.

Returns the affected periods' recomputed net, so the effect on the period is \
visible immediately.\
"""


def _cash_state(client: VipuClient) -> dict[str, Any]:
    """The figures a write should report back, straight off the budget."""
    totals = client.get_budget()["totals"]
    return {
        "cash_balance": totals["cash_balance"],
        "card_debt": totals["card_debt"],
        "current_balance": totals["current_balance"],
        "cash_low_point": totals["cash_low_point"],
        "period_current_net": totals["period_current"]["net"],
        "period_next_net": totals["period_next"]["net"],
    }


def _previous_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def register(server: MCPServer, client: VipuClient) -> None:
    """Register the record tools on ``server``."""

    @server.tool(
        name="set_account_balance",
        title="Set account balance",
        description=SET_BALANCE_DESCRIPTION,
        annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False),
    )
    def set_account_balance(name: str, balance: float) -> dict[str, Any]:
        """Set one account's balance, resolved by name."""
        target = resolve.account(client, name)
        updated = client.update_account(target["id"], balance=balance)
        return {
            "account": updated,
            "previous_balance": target["balance"],
            **_cash_state(client),
        }

    @server.tool(
        name="record_budget_snapshot",
        title="Record budget snapshot",
        description=RECORD_SNAPSHOT_DESCRIPTION,
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            # Upserts on today's date, so a repeat is a no-op rather than a
            # second row.
            idempotent_hint=True,
        ),
    )
    def record_budget_snapshot(notes: str | None = None) -> dict[str, Any]:
        """Freeze today's balances into the cash history."""
        result = client.create_budget_snapshot(notes)
        snapshot = result["snapshot"]
        return {
            "snapshot": snapshot,
            "replaced_todays_snapshot": result["updated"],
            "change_from_previous": snapshot["change_from_previous"],
            "pay_period_change": snapshot["pay_period_change"],
            "pay_period_start": snapshot["pay_period_start"],
            **_cash_state(client),
        }

    @server.tool(
        name="record_net_worth",
        title="Record net worth",
        description=RECORD_NET_WORTH_DESCRIPTION,
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            # Upserts by month.
            idempotent_hint=True,
        ),
    )
    def record_net_worth(
        year: int,
        month: int,
        entries: dict[str, float],
        carry_forward_missing: bool = True,
    ) -> dict[str, Any]:
        """Record one month's net worth from category names to amounts."""
        # Resolve every name before writing anything, so a typo in the fifth
        # category does not leave the first four recorded.
        resolved = resolve.net_worth_categories(client, list(entries))
        amounts = {
            resolved[name]["id"]: float(amount) for name, amount in entries.items()
        }

        carried: list[str] = []
        if carry_forward_missing:
            # The previous snapshot itself, not GET .../previous-entries: that
            # endpoint returns absolute values, so carrying from it would record
            # every liability as an asset.
            previous = client.get_net_worth_month(*_previous_month(year, month))
            for entry in (previous or {}).get("entries", []):
                if entry["category_id"] in amounts:
                    continue
                amounts[entry["category_id"]] = entry["amount"]
                carried.append(entry["category"]["name"])

        payload = [
            {"category_id": category_id, "amount": amount}
            for category_id, amount in amounts.items()
        ]

        existing = client.get_net_worth_month(year, month)
        if existing:
            snapshot = client.update_net_worth_snapshot(existing["id"], payload)
        else:
            snapshot = client.create_net_worth_snapshot(year, month, payload)

        return {
            "snapshot": snapshot,
            "replaced_existing_snapshot": existing is not None,
            "net_worth": snapshot["net_worth"],
            "change_from_previous": snapshot["change_from_previous"],
            "change_percent": snapshot["change_percent"],
            # Named so the model can say which figures it did not actually ask
            # about rather than vouching for all of them.
            "carried_forward": sorted(carried),
        }

    @server.tool(
        name="settle_expense",
        title="Settle an expense occurrence",
        description=SETTLE_DESCRIPTION.format(kind="expense"),
        annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False),
    )
    def settle_expense(
        name: str, occurrence_date: str | None = None, settled: bool = True
    ) -> dict[str, Any]:
        """Mark one expense occurrence paid, or not paid after all."""
        item = resolve.expense(client, name)
        occurrence = occurrence_date or _default_expense_occurrence(client, item["id"])
        updated = client.set_expense_occurrence(item["id"], occurrence, settled)
        return {
            "expense": updated,
            "occurrence_date": occurrence,
            "settled": settled,
            **_cash_state(client),
        }

    @server.tool(
        name="settle_income",
        title="Settle an income occurrence",
        description=SETTLE_DESCRIPTION.format(kind="income"),
        annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False),
    )
    def settle_income(
        name: str, occurrence_date: str | None = None, settled: bool = True
    ) -> dict[str, Any]:
        """Mark one income occurrence received, or still expected."""
        item = resolve.income(client, name)
        occurrence = occurrence_date or _default_income_occurrence(client, item["id"])
        updated = client.set_income_occurrence(item["id"], occurrence, settled)
        return {
            "income": updated,
            "occurrence_date": occurrence,
            "settled": settled,
            **_cash_state(client),
        }


def _settleable_dates(rows: list[dict], item_id: int) -> list[str]:
    """The occurrence dates of ``item_id`` the backend will actually accept.

    can_settle marks exactly two: the next occurrence ahead of us and the last
    one to have come due this pay period. Anything else is a schedule edit and
    the backend rejects it.
    """
    return sorted(
        {
            str(row["next_occurrence_date"])
            for row in rows
            if row["id"] == item_id
            and row.get("can_settle")
            and row.get("next_occurrence_date")
        }
    )


def _default_expense_occurrence(client: VipuClient, item_id: int) -> str:
    """The expense occurrence to settle when the caller named no date.

    The next one, meaning strictly after today: a bill dated today has already
    debited as far as the budget is concerned. When there is no future
    occurrence in play the only settleable date left is the one that came due
    this period, which is the "did it actually land?" question, so use that.
    """
    budget = client.get_budget()
    totals = budget["totals"]
    # period_current opens on today, so the payload carries the backend's own
    # date and this does not have to trust the container's clock.
    today = str(totals["period_current"]["start"])
    rows = [
        *totals["expenses_before_payday_list"],
        *totals["expenses_next_period_list"],
        *totals["expenses_future_list"],
    ]

    dates = _settleable_dates(rows, item_id)
    ahead = [date for date in dates if date > today]
    if ahead:
        return ahead[0]
    if dates:
        return dates[-1]
    raise ToolError(
        "This item has no occurrence that can be settled right now. Pass "
        "occurrence_date explicitly, or check that the item is still active."
    )


def _default_income_occurrence(client: VipuClient, item_id: int) -> str:
    """The income occurrence to settle when the caller named no date.

    Income is listed one row per item rather than one per occurrence, and that
    row already carries the single occurrence whose state is in question.
    """
    for row in client.get_budget()["income"]:
        if row["id"] == item_id and row.get("next_occurrence_date"):
            return str(row["next_occurrence_date"])
    raise ToolError(
        "This item has no occurrence that can be settled right now. Pass "
        "occurrence_date explicitly, or check that the item is still active."
    )
