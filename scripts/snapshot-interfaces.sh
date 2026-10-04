#!/bin/bash
# Write the public interfaces to a directory so a refactoring can prove it left
# them alone: snapshot before, snapshot after, and diff the two.
#
#   ./scripts/snapshot-interfaces.sh /tmp/refactor-before
#   ... refactor ...
#   ./scripts/snapshot-interfaces.sh /tmp/refactor-after
#   git diff --no-index /tmp/refactor-before /tmp/refactor-after
#
# openapi.json covers every REST route and schema; mcp-surface.json covers the
# MCP instructions, tools, prompts and resources in full and read-only mode. Regenerating
# the spec rewrites docs/openapi.json, as ./test.sh does.
set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Usage: $0 <output-dir>" >&2
    exit 2
fi

root="$(cd "$(dirname "$0")/.." && pwd)"
out="$1"
mkdir -p "$out"

uv --directory "$root/backend" run --locked python scripts/export_openapi.py > /dev/null
cp "$root/docs/openapi.json" "$out/openapi.json"

# Through a temporary file, so a failed export leaves no empty snapshot behind.
uv --directory "$root/mcp-server" run --locked python scripts/export_mcp_surface.py \
    > "$out/mcp-surface.json.tmp"
mv "$out/mcp-surface.json.tmp" "$out/mcp-surface.json"

echo "Interfaces written to $out"
