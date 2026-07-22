#!/usr/bin/env bash
# Install git hooks for the vipu project

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

HOOKS_DIR="$PROJECT_ROOT/.git/hooks"
HOOKS_SRC_DIR="$PROJECT_ROOT/scripts/git-hooks"

echo "Installing git hooks..."

# Create hooks directory if it doesn't exist
mkdir -p "$HOOKS_DIR"

# Install pre-commit hook
PRE_COMMIT_SRC="$HOOKS_SRC_DIR/pre-commit"
PRE_COMMIT_DST="$HOOKS_DIR/pre-commit"

if [ -f "$PRE_COMMIT_SRC" ]; then
    cp "$PRE_COMMIT_SRC" "$PRE_COMMIT_DST"
    chmod +x "$PRE_COMMIT_DST"
    echo "✓ Installed pre-commit hook"
else
    echo "✗ pre-commit hook source not found at $PRE_COMMIT_SRC"
    exit 1
fi

# Also install the hook directly for the current user
chmod +x "$PRE_COMMIT_SRC"

echo "Done! Git hooks installed successfully."
echo ""
echo "To use the hooks, run: source $PROJECT_ROOT/scripts/install-git-hooks.sh"
