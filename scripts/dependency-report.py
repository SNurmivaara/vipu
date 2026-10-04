#!/usr/bin/env python3
"""Report dependencies, runtimes and images that are a major version behind.

Builds a Markdown report and keeps one tracking issue up to date with it: the issue
is found by a hidden marker in its body, created when missing, edited otherwise and
reopened when it was closed. `.github/workflows/dependency-report.yml` runs this
monthly. Run it from the repository root with `gh` authenticated, plus npm and uv:

    python3 scripts/dependency-report.py --dry-run

`--dry-run` prints the report to stdout and leaves the issue alone. A failing
lookup becomes a line in the report instead of failing the run.

"A major behind" compares the first version component, so a 0.x package moving
from 0.16 to 0.17 does not count. `@types/node` is compared with the Node runtime
major (`frontend/.nvmrc`, else `frontend/Dockerfile`) rather than with its newest
release, because it should follow the runtime.
"""

from __future__ import annotations

import argparse
import calendar
import datetime as dt
import json
import os
import re
import subprocess
import sys
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKER = "<!-- vipu-dependency-report -->"
TITLE = "Dependency and runtime report"
LABEL = "dependencies"
EOL_API = "https://endoflife.date/api/v1/products/{product}"
NPM_LATEST = "https://registry.npmjs.org/{name}/latest"
ACT_SOON_MONTHS = 6
TIMEOUT = 30


class LookupFailed(Exception):
    """An upstream lookup (registry, GitHub or endoflife.date) failed."""


@dataclass
class Behind:
    name: str
    current: str
    latest: str
    note: str = ""
    failed: bool = False


@dataclass
class Section:
    """One block of the report, with its counts of items behind and failed lookups."""

    lines: list[str]
    behind: int = 0
    failures: int = 0


@dataclass
class Runtime:
    label: str
    product: str  # endoflife.date product id
    patterns: list[tuple[str, str]]  # (glob relative to ROOT, regex with one group)
    lts_only: bool = False
    pins: dict[str, list[str]] = field(default_factory=dict)  # version -> files


def run(cmd: list[str], cwd: Path = ROOT) -> str:
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=300, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LookupFailed(f"`{' '.join(cmd)}`: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        last = detail[-1] if detail else f"exit code {result.returncode}"
        raise LookupFailed(f"`{' '.join(cmd)}`: {last}")
    return result.stdout


def fetch_json(url: str) -> object:
    request = urllib.request.Request(url, headers={"User-Agent": "vipu-dep-report"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.load(response)
    except (OSError, ValueError) as exc:
        raise LookupFailed(f"{url}: {exc}") from exc


def major(version: str) -> int | None:
    match = re.match(r"v?(\d+)", version.strip())
    return int(match.group(1)) if match else None


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", version))


def add_months(day: dt.date, months: int) -> dt.date:
    year, month = divmod(day.month - 1 + months, 12)
    year, month = day.year + year, month + 1
    last = calendar.monthrange(year, month)[1]
    return day.replace(year=year, month=month, day=min(day.day, last))


def failed(what: str, exc: LookupFailed) -> list[str]:
    print(f"warning: {what} lookup failed: {exc}", file=sys.stderr)
    return [f"> **Lookup failed** for {what}: {exc}", ""]


def table(header: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + " --- |" * len(header)]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return lines + [""]


def behind_section(
    title: str,
    nothing: str,
    lookup: Callable[[], list[Behind]],
    kind: str = "Package",
) -> Section:
    lines = [f"### {title}", ""]
    try:
        items = lookup()
    except LookupFailed as exc:
        return Section(lines + failed(title, exc), failures=1)
    if not items:
        return Section(lines + [nothing, ""])
    rows = [[f"`{i.name}`", i.current, i.latest, i.note] for i in items]
    failures = sum(item.failed for item in items)
    return Section(
        lines + table([kind, "Current", "Latest", "Note"], rows),
        len(items) - failures,
        failures,
    )


# --- Packages ---------------------------------------------------------------


def node_runtime_major() -> int | None:
    nvmrc = ROOT / "frontend" / ".nvmrc"
    if nvmrc.exists():
        return major(nvmrc.read_text())
    dockerfile = ROOT / "frontend" / "Dockerfile"
    match = re.search(r"^FROM\s+node:(\d+)", dockerfile.read_text(), re.M)
    return int(match.group(1)) if match else None


def npm_latest(name: str) -> str:
    data = fetch_json(NPM_LATEST.format(name=name.replace("/", "%2F")))
    if not isinstance(data, dict) or "version" not in data:
        raise LookupFailed(f"{name}: no version in the registry response")
    return str(data["version"])


def npm_behind() -> list[Behind]:
    # Reads the lockfile and the registry rather than `npm outdated`, which
    # skips devDependencies when node_modules is not installed.
    frontend = ROOT / "frontend"
    manifest = json.loads((frontend / "package.json").read_text())
    lock = json.loads((frontend / "package-lock.json").read_text())["packages"]
    declared = {
        **manifest.get("dependencies", {}),
        **manifest.get("devDependencies", {}),
    }
    names = sorted(name for name in declared if name != "@types/node")
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {name: pool.submit(npm_latest, name) for name in names}
    items, errors = [], []
    for name, future in futures.items():
        current = lock.get(f"node_modules/{name}", {}).get("version", "")
        try:
            latest = future.result()
        except LookupFailed as exc:
            errors.append(exc)
            print(f"warning: {name} lookup failed: {exc}", file=sys.stderr)
            items.append(Behind(name, current, "?", "lookup failed", failed=True))
            continue
        cur, new = major(current), major(latest)
        if cur is not None and new is not None and new > cur:
            items.append(Behind(name, current, latest))
    if names and len(errors) == len(names):
        raise LookupFailed(str(errors[0]))
    types_node = lock.get("node_modules/@types/node", {}).get("version")
    runtime = node_runtime_major()
    if types_node and runtime is not None and major(types_node) != runtime:
        items.append(
            Behind(
                "@types/node",
                types_node,
                f"{runtime}.x",
                f"follows the Node {runtime} runtime, not the newest release",
            )
        )
    return items


UV_LINE = re.compile(r"^[├└]── (?P<name>\S+) v(?P<version>\S+)(?P<rest>.*)$")


def uv_behind(package: str) -> list[Behind]:
    output = run(
        ["uv", "tree", "--outdated", "--depth", "1", "--frozen"], ROOT / package
    )
    items = []
    for line in output.splitlines():
        match = UV_LINE.match(line)
        latest = re.search(r"\(latest: v(\S+)\)", line)
        if not match or not latest:
            continue
        name = re.sub(r"\[.*\]$", "", match.group("name"))
        current, new = match.group("version"), latest.group(1)
        cur, lat = major(current), major(new)
        if cur is not None and lat is not None and lat > cur:
            extra = re.search(r"\(extra: (\S+)\)", match.group("rest"))
            note = f"`{extra.group(1)}` extra" if extra else ""
            items.append(Behind(name, current, new, note))
    return items


def actions_behind() -> list[Behind]:
    used: dict[str, set[str]] = {}
    for workflow in sorted((ROOT / ".github" / "workflows").glob("*.y*ml")):
        for action, ref in re.findall(
            r"uses:\s*['\"]?([^@\s'\"]+)@([^\s'\"]+)", workflow.read_text()
        ):
            if action.startswith(("./", "docker://")) or major(ref) is None:
                continue
            repo = "/".join(action.split("/")[:2])
            used.setdefault(repo, set()).add(ref)
    items, errors = [], []
    for repo, refs in sorted(used.items()):
        try:
            tag = run(
                ["gh", "api", f"repos/{repo}/releases/latest", "--jq", ".tag_name"]
            ).strip()
        except LookupFailed as exc:
            errors.append(exc)
            print(f"warning: {repo} lookup failed: {exc}", file=sys.stderr)
            items.append(
                Behind(repo, ", ".join(sorted(refs)), "?", "lookup failed", True)
            )
            continue
        latest = major(tag)
        oldest = min(major(ref) or 0 for ref in refs)
        if latest is not None and oldest < latest:
            items.append(Behind(repo, ", ".join(sorted(refs)), tag))
    if used and len(errors) == len(used):
        raise LookupFailed(str(errors[0]))
    return items


# --- Runtimes and images ----------------------------------------------------


RUNTIMES = [
    Runtime(
        "Node",
        "nodejs",
        [
            ("frontend/Dockerfile*", r"^FROM\s+node:(\d+)"),
            ("frontend/.nvmrc", r"^v?(\d+)"),
            (".github/workflows/*.yml", r"node-version:\s*['\"]?(\d+)"),
        ],
        lts_only=True,
    ),
    Runtime(
        "Python",
        "python",
        [
            ("*/Dockerfile*", r"^FROM\s+python:(\d+\.\d+)"),
            (".github/workflows/*.yml", r"python-version:\s*['\"]?(\d+\.\d+)"),
        ],
    ),
    Runtime(
        "PostgreSQL",
        "postgresql",
        [
            (pattern, r"\bpostgres:(\d{1,2})\b")
            for pattern in (
                "docker-compose*.yml",
                "deploy/docker-compose*.yml",
                ".github/workflows/*.yml",
                "scripts/*.sh",
            )
        ],
    ),
]


def find_pins(runtime: Runtime) -> None:
    for pattern, regex in runtime.patterns:
        for path in sorted(ROOT.glob(pattern)):
            for version in sorted(set(re.findall(regex, path.read_text(), re.M))):
                files = runtime.pins.setdefault(version, [])
                relative = str(path.relative_to(ROOT))
                if relative not in files:
                    files.append(relative)


def runtimes_section(today: dt.date) -> tuple[Section, list[str]]:
    """Return the runtime table and the "Act soon" lines."""
    cutoff = add_months(today, ACT_SOON_MONTHS)
    rows, soon, lines = [], [], ["## Runtimes and images", ""]
    behind = failures = 0
    for runtime in RUNTIMES:
        find_pins(runtime)
        try:
            data = fetch_json(EOL_API.format(product=runtime.product))
            releases = data["result"]["releases"]  # type: ignore[index]
        except (LookupFailed, KeyError, TypeError) as exc:
            error = exc if isinstance(exc, LookupFailed) else LookupFailed(repr(exc))
            lines += failed(f"{runtime.label} release data (endoflife.date)", error)
            failures += 1
            soon.append(f"- **{runtime.label}**: end of life unknown, lookup failed.")
            for version, files in runtime.pins.items():
                rows.append([runtime.label, version, "?", "?", in_files(files)])
            continue
        current = [
            r
            for r in releases
            if (r.get("releaseDate") or "9999") <= today.isoformat()
            and not r.get("isEol")
            and (not runtime.lts_only or (r.get("ltsFrom") or "9999") <= str(today))
        ]
        newest = max(current, key=lambda r: version_key(r["name"]), default=None)
        newest_name = newest["name"] if newest else "?"
        if newest and runtime.lts_only:
            newest_name += " (LTS)"
        by_name = {r["name"]: r for r in releases}
        for version, files in sorted(
            runtime.pins.items(), key=lambda p: version_key(p[0])
        ):
            eol = (by_name.get(version) or {}).get("eolFrom")
            eol_text = eol or "unknown"
            if eol and dt.date.fromisoformat(eol) < cutoff:
                verb = "reached" if dt.date.fromisoformat(eol) <= today else "reaches"
                soon.append(
                    f"- **{runtime.label} {version}** {verb} end of life on {eol}. "
                    f"Pinned in {in_files(files)}."
                )
                eol_text = f"**{eol}** (act soon)"
            if newest and version_key(version) < version_key(newest["name"]):
                behind += 1
            rows.append(
                [runtime.label, version, newest_name, eol_text, in_files(files)]
            )
    header = ["Runtime", "Pinned", "Newest", "Pinned end of life", "Pinned in"]
    return Section(lines + table(header, rows), behind, failures), soon


def in_files(files: list[str]) -> str:
    return ", ".join(f"`{f}`" for f in files)


# --- Dependabot -------------------------------------------------------------


def dependabot_section() -> Section:
    lines = ["## Dependabot PRs waiting for a manual merge", ""]
    try:
        prs = json.loads(
            run(
                [
                    "gh",
                    "pr",
                    "list",
                    "--state",
                    "open",
                    "--label",
                    LABEL,
                    "--limit",
                    "100",
                    "--json",
                    "number,title,createdAt,autoMergeRequest",
                ]
            )
        )
    except (LookupFailed, ValueError) as exc:
        error = exc if isinstance(exc, LookupFailed) else LookupFailed(str(exc))
        return Section(lines + failed("open Dependabot PRs", error), failures=1)
    manual = [pr for pr in prs if not pr.get("autoMergeRequest")]
    if not manual:
        return Section(lines + ["None. Every open `dependencies` PR auto-merges.", ""])
    lines += [
        f"- #{pr['number']} {pr['title']} (opened {pr['createdAt'][:10]})"
        for pr in sorted(manual, key=lambda pr: pr["number"])
    ]
    return Section(lines + [""])


# --- Report and issue -------------------------------------------------------


def build_report(today: dt.date) -> str:
    runtimes, soon = runtimes_section(today)
    packages = [
        behind_section(
            "npm (`frontend/`)",
            "No npm package in `frontend/` is a major version behind.",
            npm_behind,
        ),
        behind_section(
            "Python (`backend/`)",
            "No Python package in `backend/` is a major version behind.",
            lambda: uv_behind("backend"),
        ),
        behind_section(
            "Python (`mcp-server/`)",
            "No Python package in `mcp-server/` is a major version behind.",
            lambda: uv_behind("mcp-server"),
        ),
        behind_section(
            "GitHub Actions",
            "Every action is on its latest major.",
            actions_behind,
            kind="Action",
        ),
    ]
    dependabot = dependabot_section()

    server, repo, run_id = (
        os.environ.get(name)
        for name in ("GITHUB_SERVER_URL", "GITHUB_REPOSITORY", "GITHUB_RUN_ID")
    )
    source = (
        f"[workflow run]({server}/{repo}/actions/runs/{run_id})"
        if server and repo and run_id
        else "a local run of `scripts/dependency-report.py`"
    )
    sections = [runtimes, *packages, dependabot]
    total = sum(section.behind for section in sections)
    failures = sum(section.failures for section in sections)
    summary = (
        f"Behind their newest major or release line: {total}."
        if total
        else "Nothing is a major version behind."
    )
    if failures:
        summary += f" Failed lookups: {failures}, so this report is incomplete."
    cutoff = add_months(today, ACT_SOON_MONTHS)
    act_soon = soon or [f"Nothing reaches end of life before {cutoff}."]

    lines = [
        MARKER,
        f"Updated {today} by {source}. {summary}",
        "",
        "This issue is rewritten monthly by `.github/workflows/dependency-report.yml`;"
        " edits to it are lost. It lists what is behind and performs no upgrades.",
        "",
        f"## Act soon (end of life before {cutoff})",
        "",
        *act_soon,
        "",
        *runtimes.lines,
        "## Packages and actions a major version behind",
        "",
    ]
    for section in packages:
        lines += section.lines
    lines += dependabot.lines
    return "\n".join(lines).rstrip() + "\n"


def update_issue(body: str) -> None:
    issues = json.loads(
        run(
            [
                "gh",
                "issue",
                "list",
                "--state",
                "all",
                "--label",
                LABEL,
                "--limit",
                "500",
                "--json",
                "number,state,body",
            ]
        )
    )
    tracking = sorted(
        (issue for issue in issues if MARKER in (issue.get("body") or "")),
        key=lambda issue: issue["number"],
    )
    if not tracking:
        url = subprocess.run(
            ["gh", "issue", "create", "--title", TITLE, "--label", LABEL]
            + ["--body-file", "-"],
            cwd=ROOT,
            input=body,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        print(f"Created {url}")
        return
    number = str(tracking[0]["number"])
    subprocess.run(
        ["gh", "issue", "edit", number, "--body-file", "-"],
        cwd=ROOT,
        input=body,
        text=True,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    if tracking[0]["state"] != "OPEN":
        subprocess.run(["gh", "issue", "reopen", number], cwd=ROOT, check=True)
    print(f"Updated issue #{number}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the report to stdout instead of updating the tracking issue",
    )
    args = parser.parse_args()
    body = build_report(dt.date.today())
    if args.dry_run:
        print(body, end="")
    else:
        update_issue(body)


if __name__ == "__main__":
    main()
