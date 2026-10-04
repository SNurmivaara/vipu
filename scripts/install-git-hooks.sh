#!/usr/bin/env bash
# Install the vipu git hooks into this clone. Run it as ./scripts/install-git-hooks.sh;
# running it again is safe. An existing, different pre-commit hook is backed up.

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(git -C "$script_dir" rev-parse --show-toplevel)"
src="$script_dir/git-hooks/pre-commit"

if [[ ! -f "$src" ]]; then
    echo "pre-commit hook source not found at $src" >&2
    exit 1
fi

# --git-path resolves the hooks directory git actually uses: the shared one in a
# worktree, or core.hooksPath when that is set.
hooks_dir="$(git -C "$repo_root" rev-parse --path-format=absolute --git-path hooks)"

if hooks_path="$(git -C "$repo_root" config --get core.hooksPath)"; then
    echo "Warning: core.hooksPath is set to '$hooks_path', so git runs hooks from" >&2
    echo "$hooks_dir instead of the repository's own hooks directory." >&2
    common_dir="$(git -C "$repo_root" rev-parse --path-format=absolute --git-common-dir)"
    case "$hooks_dir/" in
        "$repo_root"/* | "$common_dir"/*) ;;
        *)
            echo "That directory is outside this repository and may serve other" >&2
            echo "repositories too, so nothing was installed. Copy $src there" >&2
            echo "yourself, or unset core.hooksPath for this repository." >&2
            exit 1
            ;;
    esac
fi

mkdir -p "$hooks_dir"
dst="$hooks_dir/pre-commit"

if [[ -e "$dst" || -L "$dst" ]]; then
    if cmp -s "$src" "$dst" && [[ -x "$dst" ]]; then
        echo "pre-commit hook already up to date at $dst"
        exit 0
    fi
    if ! cmp -s "$src" "$dst"; then
        backup="$dst.backup.$(date +%Y%m%d%H%M%S)"
        mv "$dst" "$backup"
        echo "Backed up the existing pre-commit hook to $backup"
    fi
fi

cp "$src" "$dst"
chmod +x "$dst"
echo "Installed pre-commit hook at $dst"
