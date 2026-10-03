"""PostToolUse hook: format Python files Claude edits in backend/ or mcp-server/.

Runs Ruff --fix and then Black with each package's own locked environment and
configuration. Failures never block the edit; ./test.sh reports what remains.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

PACKAGES = ("backend", "mcp-server")
# Keep imports Claude adds before the edit that uses them.
UNFIXABLE = "F401"


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return
    file_path = (event.get("tool_input") or {}).get("file_path")
    if not file_path or not file_path.endswith(".py"):
        return

    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or ".")
    path = Path(file_path)
    if not path.is_absolute():
        path = Path(event.get("cwd") or root) / path
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        return
    if relative.parts[0] not in PACKAGES or not path.is_file():
        return

    package = root / relative.parts[0]
    target = str(relative.relative_to(relative.parts[0]))
    for command in (
        ["ruff", "check", "--fix", "--unfixable", UNFIXABLE, "--quiet", target],
        ["black", "--quiet", target],
    ):
        try:
            subprocess.run(
                ["uv", "run", "--locked", *command],
                cwd=package,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=25,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return


if __name__ == "__main__":
    main()
