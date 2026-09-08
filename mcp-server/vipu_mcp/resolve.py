"""Name to id lookup, so no tool takes a database id.

A model has names, not ids, and a tool that demands an id forces a listing call
before every write. Resolution is exact first, then case-insensitive; an
ambiguous name is an error listing the candidates, so the model asks rather than
picking one.
"""

from mcp.server.mcpserver.exceptions import ToolError

from vipu_mcp.client import VipuClient


class ResolutionError(ToolError):
    """A name matched nothing, or matched more than one thing.

    A ToolError so the candidate list reaches the model, which is the whole
    point: it is what lets it ask which one was meant instead of guessing.
    """


def match_by_name(items: list[dict], name: str, kind: str) -> dict:
    """The one item called ``name``, or an error the model can act on.

    ``kind`` names the thing being looked for, so the message reads as
    "No expense called ..." rather than a generic not-found.
    """
    wanted = name.strip()
    exact = [item for item in items if item.get("name") == wanted]
    if len(exact) == 1:
        return exact[0]

    folded = wanted.casefold()
    loose = [item for item in items if str(item.get("name", "")).casefold() == folded]
    candidates = exact or loose

    if not candidates:
        known = ", ".join(sorted(str(item.get("name", "")) for item in items))
        raise ResolutionError(
            f"No {kind} called {name!r}."
            + (f" Known {kind}s: {known}." if known else f" There are no {kind}s yet.")
        )
    if len(candidates) > 1:
        names = ", ".join(sorted(str(item.get("name", "")) for item in candidates))
        raise ResolutionError(
            f"{name!r} matches more than one {kind}: {names}. "
            "Ask which one was meant."
        )
    return candidates[0]


def _active(items: list[dict]) -> list[dict]:
    """Archived items are history; a write should never land on one silently."""
    return [item for item in items if item.get("archived_at") is None]


def account(client: VipuClient, name: str) -> dict:
    """The account called ``name``."""
    return match_by_name(client.list_accounts(), name, "account")


def expense(client: VipuClient, name: str) -> dict:
    """The active expense called ``name``."""
    return match_by_name(_active(client.list_expenses()), name, "expense")


def income(client: VipuClient, name: str) -> dict:
    """The active income item called ``name``."""
    return match_by_name(_active(client.list_income()), name, "income item")


def net_worth_category(client: VipuClient, name: str) -> dict:
    """The net worth category called ``name``."""
    return match_by_name(client.list_net_worth_categories(), name, "net worth category")


def net_worth_categories(client: VipuClient, names: list[str]) -> dict[str, dict]:
    """Resolve several category names in one listing call.

    Every name is resolved before anything is written, so a typo in the fifth
    category does not leave the first four recorded.
    """
    catalogue = client.list_net_worth_categories()
    return {
        name: match_by_name(catalogue, name, "net worth category") for name in names
    }


def goal(client: VipuClient, name: str) -> dict:
    """The goal called ``name``."""
    return match_by_name(client.list_goals(), name, "goal")


def goals(client: VipuClient, names: list[str]) -> list[dict]:
    """Resolve several goal names in one listing call, in the order given."""
    catalogue = client.list_goals()
    return [match_by_name(catalogue, name, "goal") for name in names]
