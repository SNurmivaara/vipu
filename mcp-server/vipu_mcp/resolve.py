"""Name to id lookup, so no tool takes a database id.

A model has names, not ids, and a tool that demands an id forces a listing call
before every write. Resolution is exact first, then case-insensitive; an
ambiguous name is an error listing the candidates, so the model asks rather than
picking one.

Built out for accounts, expenses, income and net worth categories in the record
tools. This module holds the matching rule they all share.
"""


class ResolutionError(ValueError):
    """A name matched nothing, or matched more than one thing."""


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
