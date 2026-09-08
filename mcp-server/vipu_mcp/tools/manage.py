"""Tools for editing the plan itself: income, expenses, accounts and goals.

Completes the write surface. After this, anything the web UI can do the MCP
server can do, minus the endpoints that erase data outright.
"""

import re
from datetime import UTC, datetime
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from vipu_mcp import resolve
from vipu_mcp.client import VipuClient

VALID_UNITS = ("days", "weeks", "months", "years")

# Named cadences, since that is how the request will actually arrive.
NAMED_CADENCES = {
    "daily": (1, "days"),
    "weekly": (1, "weeks"),
    "biweekly": (2, "weeks"),
    "fortnightly": (2, "weeks"),
    "monthly": (1, "months"),
    "bimonthly": (2, "months"),
    "quarterly": (3, "months"),
    "semiannually": (6, "months"),
    "yearly": (1, "years"),
    "annually": (1, "years"),
}

EVERY_N = re.compile(r"^every\s+(\d+)\s+(day|week|month|year)s?$")

SCHEDULING_NOTES = """\
Scheduling. `cadence` takes a phrase: "monthly", "weekly", "quarterly", \
"yearly", or "every 3 months". `due_day` (1-31) is the day of the month it \
lands on. Months that are too short clamp to their last day.

Monthly and yearly cadences are phase-anchored to `start_date`, so a quarterly \
bill stays quarterly across windows. Day and week cadences must have an anchor: \
without `start_date` one is set to `due_day` of the current month, or the \
schedule's dates would depend on the window they happen to be generated in.

`one_time=true` is not the same as a recurring item with an end date. One-time \
items are excluded from the frequency-normalized monthly rates, and therefore \
from the roadmap surplus and every FIRE number, while still being charged \
against cash on their own day. Use it for a bonus or a single large bill; use \
an `end_date` for something genuinely recurring that stops.\
"""

VALIDATION_NOTES = """\
Names are at most 100 characters and amounts at most 1000000000. The backend \
validates and its message comes back verbatim; do not pre-empt it.\
"""

ADD_EXPENSE_DESCRIPTION = f"""\
Create a recurring or one-time expense.

{SCHEDULING_NOTES}

`is_savings_goal=true` marks a transfer to savings rather than a bill. It still \
leaves the account, but it is reported separately from bills in the period \
totals.

{VALIDATION_NOTES}\
"""

UPDATE_EXPENSE_DESCRIPTION = f"""\
Change an existing expense, found by name. Only the fields given are touched.

{SCHEDULING_NOTES}

{VALIDATION_NOTES}\
"""

ARCHIVE_DESCRIPTION = """\
Archive a {kind} so it stops counting toward any total, or restore an archived \
one with restore=true.

Archiving keeps the row and its history; it is how a {kind} that has ended is \
retired. Pass restore=true to bring one back.

Vipu's DELETE endpoints remove the row outright with no undo, and are \
deliberately not reachable from here. If the {kind} genuinely needs erasing \
rather than retiring, that is a job for the web UI.\
"""

ADD_INCOME_DESCRIPTION = f"""\
Create a recurring or one-time income line.

`is_taxed` (default true) applies the budget's default tax percentage unless \
`tax_percentage` gives this line its own rate.

`is_deduction=true` is different: it models a payroll deduction, subtracted \
from net pay after tax, and `tax_percentage` is then read as the share of \
`gross_amount` deducted. A lunch benefit at 75% of 200 is \
gross_amount=200, tax_percentage=75, is_deduction=true.

{SCHEDULING_NOTES}

{VALIDATION_NOTES}\
"""

UPDATE_INCOME_DESCRIPTION = f"""\
Change an existing income line, found by name. Only the fields given are \
touched.

{SCHEDULING_NOTES}

{VALIDATION_NOTES}\
"""

ADD_ACCOUNT_DESCRIPTION = """\
Create an account or a credit card.

`is_credit=true` makes it a card, and a card's balance is stored negative: -450 \
means 450 owed. `payment_due_day` is when the balance comes off the account; a \
card balance is charged once, on its first due day from today, not in every \
period. A card with no payment_due_day falls due immediately.

To change a balance afterwards, use set_account_balance.\
"""

SET_GOAL_DESCRIPTION = """\
Create a goal.

`goal_type` is one of:

- `savings_goal`: save up to a target. Appended to the end of the roadmap and \
funded from the monthly surplus in priority order. Link it to a net worth \
category with `category_name` and its progress tracks that category's balance \
instead of a manual figure.
- `debt_payoff`: pay off a debt of target_value. Also a roadmap step; progress \
comes from `current_amount`.
- `net_worth`: a target for total net worth, shown on the wealth page rather \
than in the roadmap. `category_name` is not valid for this type.

`target_date` gives it a deadline, which is what makes an on-track or behind \
status possible. That status is zero-growth linear and does not compound.\
"""

UPDATE_GOAL_DESCRIPTION = """\
Change an existing goal, found by name. Only the fields given are touched.

Changing `goal_type` into or out of a roadmap type moves the goal into or out \
of the plan, and reorders what is left. Set `is_active=false` to park a goal \
without deleting it.\
"""

REORDER_GOALS_DESCRIPTION = """\
Set the order the roadmap funds its steps in, by naming every roadmap goal in \
the sequence wanted.

The whole monthly surplus fills the first unfinished step before any of it \
reaches the second, so moving a step changes the projected completion date of \
every step below it, not just the one that moved. Say so when reporting the \
result.

Only savings_goal and debt_payoff goals have a place in the roadmap; naming a \
net_worth goal is an error.\
"""


def _cadence(
    cadence: str | None, frequency_value: int | None, frequency_unit: str | None
) -> dict[str, Any]:
    """Turn a cadence phrase, or an explicit pair, into schedule fields."""
    if cadence is None:
        fields: dict[str, Any] = {}
        if frequency_value is not None:
            fields["frequency_value"] = frequency_value
        if frequency_unit is not None:
            if frequency_unit not in VALID_UNITS:
                raise ToolError(
                    f"frequency_unit must be one of {', '.join(VALID_UNITS)}."
                )
            fields["frequency_unit"] = frequency_unit
        return fields

    phrase = cadence.strip().lower().replace("-", "").replace("_", "")
    if phrase in NAMED_CADENCES:
        value, unit = NAMED_CADENCES[phrase]
        return {"frequency_value": value, "frequency_unit": unit}

    match = EVERY_N.match(cadence.strip().lower())
    if match:
        return {
            "frequency_value": int(match.group(1)),
            "frequency_unit": f"{match.group(2)}s",
        }

    raise ToolError(
        f"Could not read {cadence!r} as a cadence. Use one of "
        "daily, weekly, biweekly, monthly, quarterly, yearly, "
        "or 'every N days/weeks/months/years'."
    )


def _schedule_fields(
    due_day: int | None,
    cadence: str | None,
    frequency_value: int | None,
    frequency_unit: str | None,
    start_date: str | None,
    end_date: str | None,
    one_time: bool | None,
) -> dict[str, Any]:
    """The scheduling half of a create or update body."""
    fields = _cadence(cadence, frequency_value, frequency_unit)
    if due_day is not None:
        fields["due_day"] = due_day
    if start_date is not None:
        fields["start_date"] = start_date
    if end_date is not None:
        fields["end_date"] = end_date
    if one_time is not None:
        fields["is_ephemeral"] = one_time
    return fields


def _archived_at(restore: bool) -> str | None:
    """The archived_at value for archiving, or for putting something back."""
    return None if restore else datetime.now(UTC).isoformat()


def register(server: MCPServer, client: VipuClient) -> None:
    """Register the management tools on ``server``."""

    write = ToolAnnotations(read_only_hint=False, destructive_hint=False)
    archive = ToolAnnotations(read_only_hint=False, destructive_hint=True)

    def budget_effect() -> dict[str, Any]:
        """What changed about the plan, once the edit has landed."""
        totals = client.get_budget()["totals"]
        return {
            "monthly_expenses": totals["monthly_expenses"],
            "monthly_net_income": totals["monthly_net_income"],
            "monthly_surplus": totals["monthly_surplus"],
            "period_current": totals["period_current"],
            "cash_low_point": totals["cash_low_point"],
        }

    @server.tool(
        name="add_expense",
        title="Add an expense",
        description=ADD_EXPENSE_DESCRIPTION,
        annotations=write,
    )
    def add_expense(
        name: str,
        amount: float,
        due_day: int = 1,
        cadence: str | None = None,
        frequency_value: int | None = None,
        frequency_unit: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        one_time: bool = False,
        is_savings_goal: bool = False,
    ) -> dict[str, Any]:
        """Create an expense line."""
        fields: dict[str, Any] = {
            "name": name,
            "amount": amount,
            "is_savings_goal": is_savings_goal,
            **_schedule_fields(
                due_day,
                cadence,
                frequency_value,
                frequency_unit,
                start_date,
                end_date,
                one_time,
            ),
        }
        return {"expense": client.create_expense(fields), **budget_effect()}

    @server.tool(
        name="update_expense",
        title="Update an expense",
        description=UPDATE_EXPENSE_DESCRIPTION,
        annotations=write,
    )
    def update_expense(
        name: str,
        new_name: str | None = None,
        amount: float | None = None,
        due_day: int | None = None,
        cadence: str | None = None,
        frequency_value: int | None = None,
        frequency_unit: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        one_time: bool | None = None,
        is_savings_goal: bool | None = None,
    ) -> dict[str, Any]:
        """Change an expense, resolved by name."""
        item = resolve.expense(client, name)
        fields = _schedule_fields(
            due_day,
            cadence,
            frequency_value,
            frequency_unit,
            start_date,
            end_date,
            one_time,
        )
        if new_name is not None:
            fields["name"] = new_name
        if amount is not None:
            fields["amount"] = amount
        if is_savings_goal is not None:
            fields["is_savings_goal"] = is_savings_goal
        updated = client.update_expense(item["id"], fields)
        return {"expense": updated, "changed": sorted(fields), **budget_effect()}

    @server.tool(
        name="archive_expense",
        title="Archive an expense",
        description=ARCHIVE_DESCRIPTION.format(kind="expense"),
        annotations=archive,
    )
    def archive_expense(name: str, restore: bool = False) -> dict[str, Any]:
        """Retire an expense, or bring an archived one back."""
        if restore:
            # Restoring looks only at archived rows: resolve.expense searches
            # the active ones, which by definition do not include this.
            candidates = [
                expense
                for expense in client.list_expenses()
                if expense["archived_at"] is not None
            ]
            item = resolve.match_by_name(candidates, name, "archived expense")
        else:
            item = resolve.expense(client, name)
        updated = client.update_expense(
            item["id"], {"archived_at": _archived_at(restore)}
        )
        return {"expense": updated, "archived": not restore, **budget_effect()}

    @server.tool(
        name="add_income",
        title="Add an income line",
        description=ADD_INCOME_DESCRIPTION,
        annotations=write,
    )
    def add_income(
        name: str,
        gross_amount: float,
        due_day: int = 1,
        cadence: str | None = None,
        frequency_value: int | None = None,
        frequency_unit: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        one_time: bool = False,
        is_taxed: bool = True,
        tax_percentage: float | None = None,
        is_deduction: bool = False,
    ) -> dict[str, Any]:
        """Create an income line."""
        fields: dict[str, Any] = {
            "name": name,
            "gross_amount": gross_amount,
            "is_taxed": is_taxed,
            "is_deduction": is_deduction,
            **_schedule_fields(
                due_day,
                cadence,
                frequency_value,
                frequency_unit,
                start_date,
                end_date,
                one_time,
            ),
        }
        if tax_percentage is not None:
            fields["tax_percentage"] = tax_percentage
        return {"income": client.create_income(fields), **budget_effect()}

    @server.tool(
        name="update_income",
        title="Update an income line",
        description=UPDATE_INCOME_DESCRIPTION,
        annotations=write,
    )
    def update_income(
        name: str,
        new_name: str | None = None,
        gross_amount: float | None = None,
        due_day: int | None = None,
        cadence: str | None = None,
        frequency_value: int | None = None,
        frequency_unit: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        one_time: bool | None = None,
        is_taxed: bool | None = None,
        tax_percentage: float | None = None,
        is_deduction: bool | None = None,
    ) -> dict[str, Any]:
        """Change an income line, resolved by name."""
        item = resolve.income(client, name)
        fields = _schedule_fields(
            due_day,
            cadence,
            frequency_value,
            frequency_unit,
            start_date,
            end_date,
            one_time,
        )
        if new_name is not None:
            fields["name"] = new_name
        if gross_amount is not None:
            fields["gross_amount"] = gross_amount
        if is_taxed is not None:
            fields["is_taxed"] = is_taxed
        if tax_percentage is not None:
            fields["tax_percentage"] = tax_percentage
        if is_deduction is not None:
            fields["is_deduction"] = is_deduction
        updated = client.update_income(item["id"], fields)
        return {"income": updated, "changed": sorted(fields), **budget_effect()}

    @server.tool(
        name="archive_income",
        title="Archive an income line",
        description=ARCHIVE_DESCRIPTION.format(kind="income line"),
        annotations=archive,
    )
    def archive_income(name: str, restore: bool = False) -> dict[str, Any]:
        """Retire an income line, or bring an archived one back."""
        if restore:
            candidates = [
                income
                for income in client.list_income()
                if income["archived_at"] is not None
            ]
            item = resolve.match_by_name(candidates, name, "archived income item")
        else:
            item = resolve.income(client, name)
        updated = client.update_income(
            item["id"], {"archived_at": _archived_at(restore)}
        )
        return {"income": updated, "archived": not restore, **budget_effect()}

    @server.tool(
        name="add_account",
        title="Add an account",
        description=ADD_ACCOUNT_DESCRIPTION,
        annotations=write,
    )
    def add_account(
        name: str,
        balance: float = 0,
        is_credit: bool = False,
        payment_due_day: int | None = None,
    ) -> dict[str, Any]:
        """Create an account or card."""
        fields: dict[str, Any] = {
            "name": name,
            "balance": balance,
            "is_credit": is_credit,
        }
        if payment_due_day is not None:
            fields["payment_due_day"] = payment_due_day
        account = client.create_account(fields)
        totals = client.get_budget()["totals"]
        return {
            "account": account,
            "cash_balance": totals["cash_balance"],
            "card_debt": totals["card_debt"],
            "cash_low_point": totals["cash_low_point"],
        }

    @server.tool(
        name="set_goal",
        title="Create a goal",
        description=SET_GOAL_DESCRIPTION,
        annotations=write,
    )
    def set_goal(
        name: str,
        goal_type: str,
        target_value: float,
        category_name: str | None = None,
        current_amount: float | None = None,
        target_date: str | None = None,
    ) -> dict[str, Any]:
        """Create a goal, linking a category by name where one is given."""
        fields: dict[str, Any] = {
            "name": name,
            "goal_type": goal_type,
            "target_value": target_value,
        }
        if category_name is not None:
            fields["category_id"] = resolve.net_worth_category(client, category_name)[
                "id"
            ]
        if current_amount is not None:
            fields["current_amount"] = current_amount
        if target_date is not None:
            fields["target_date"] = target_date
        return {"goal": client.create_goal(fields), **_roadmap_effect(client)}

    @server.tool(
        name="update_goal",
        title="Update a goal",
        description=UPDATE_GOAL_DESCRIPTION,
        annotations=write,
    )
    def update_goal(
        name: str,
        new_name: str | None = None,
        goal_type: str | None = None,
        target_value: float | None = None,
        category_name: str | None = None,
        current_amount: float | None = None,
        target_date: str | None = None,
        is_active: bool | None = None,
    ) -> dict[str, Any]:
        """Change a goal, resolved by name."""
        target = resolve.goal(client, name)
        fields: dict[str, Any] = {}
        if new_name is not None:
            fields["name"] = new_name
        if goal_type is not None:
            fields["goal_type"] = goal_type
        if target_value is not None:
            fields["target_value"] = target_value
        if category_name is not None:
            fields["category_id"] = resolve.net_worth_category(client, category_name)[
                "id"
            ]
        if current_amount is not None:
            fields["current_amount"] = current_amount
        if target_date is not None:
            fields["target_date"] = target_date
        if is_active is not None:
            fields["is_active"] = is_active
        updated = client.update_goal(target["id"], fields)
        return {
            "goal": updated,
            "changed": sorted(fields),
            **_roadmap_effect(client),
        }

    @server.tool(
        name="reorder_goals",
        title="Reorder the roadmap",
        description=REORDER_GOALS_DESCRIPTION,
        annotations=write,
    )
    def reorder_goals(names: list[str]) -> dict[str, Any]:
        """Set roadmap priority from a list of goal names, in order."""
        targets = resolve.goals(client, names)
        client.reorder_goals([goal["id"] for goal in targets])
        return {
            "order": [goal["name"] for goal in targets],
            **_roadmap_effect(client),
        }


def _roadmap_effect(client: VipuClient) -> dict[str, Any]:
    """The plan as it stands after a goal edit.

    Reordering changes every projected completion date below the moved step, so
    the whole waterfall comes back rather than the one goal that was touched.
    """
    roadmap = client.get_roadmap()
    return {
        "surplus_monthly": roadmap["surplus_monthly"],
        "roadmap": [
            {
                "name": step["goal"]["name"],
                "status": step["status"],
                "remaining": step["remaining"],
                "projected_completion_date": step["projected_completion_date"],
            }
            for step in roadmap["goals"]
        ],
    }
