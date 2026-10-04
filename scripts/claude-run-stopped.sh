#!/usr/bin/env bash
# Comment on a PR or issue that a Claude workflow run stopped before finishing.
#
# Usage: scripts/claude-run-stopped.sh [--dry-run] <implement|review|ci-fix> <number>
#
# The Claude workflows run this from a failure step after the Claude step fails or
# times out. They fetch it from the default branch, so a branch cannot change what
# runs with the workflow token. --dry-run prints the comment instead of posting it.
#
# Environment:
#   RUN_URL         link to the stopped run (required)
#   REPO            owner/name of the repository (required unless --dry-run)
#   GH_TOKEN        token allowed to comment (required unless --dry-run)
#   EXECUTION_FILE  claude-code-action's execution_file output, if any; used to
#                   name the usage limit when the log shows it
#   PUSHED          ci-fix only: "true" when the run pushed commits before stopping
#   COMMENT_MARKER  appended to the comment so the workflow can find it later
set -euo pipefail

usage() {
  echo "Usage: $0 [--dry-run] <implement|review|ci-fix> <number>" >&2
  exit 2
}

dry_run=false
if [[ "${1:-}" == --dry-run ]]; then
  dry_run=true
  shift
fi
[[ $# == 2 ]] || usage
workflow=$1
number=$2
[[ "$number" =~ ^[0-9]+$ ]] || usage
: "${RUN_URL:?RUN_URL must link to the stopped run}"

# Best effort: the action records the API error in the execution file when the
# subscription limit stops Claude. A timeout or a crash may leave no file at all.
usage_limit() {
  [[ -n "${EXECUTION_FILE:-}" && -r "$EXECUTION_FILE" ]] || return 1
  jq -r '.[]? | objects | select(.type == "result" or .error != null) | .. | strings' \
    "$EXECUTION_FILE" 2> /dev/null |
    grep -qiE 'usage limit|hit your limit|rate_limit'
}

if usage_limit; then
  why="It reached the subscription usage limit."
  when=" after the limit resets"
else
  why="Its log shows why: an error, a timeout or the usage limit."
  when=""
fi

case "$workflow" in
  implement)
    body="Claude stopped before finishing this request ([run]($RUN_URL)). $why

To retry, comment the same \`@claude\` request again$when, for example \`@claude implement this\`. A retried implementation continues from the commits this run pushed to its \`claude/\` branch."
    ;;
  review)
    body="The Claude review stopped before finishing ([run]($RUN_URL)), so there is no \`REVIEW:\` summary. $why

To retry, comment \`@claude review\`$when."
    ;;
  ci-fix)
    body="Claude's CI fix attempt stopped before finishing ([run]($RUN_URL)). $why"
    if [[ "${PUSHED:-}" == true ]]; then
      body="$body It pushed commits before stopping, so this attempt counts. CI runs again on them, and if it fails the next attempt starts."
    else
      body="$body It pushed nothing, so this attempt does not count toward the automatic fix limit.

To retry$when, re-run the failed jobs of [this run]($RUN_URL) or push to the branch so CI runs again."
    fi
    ;;
  *)
    usage
    ;;
esac

if [[ -n "${COMMENT_MARKER:-}" ]]; then
  body="$body $COMMENT_MARKER"
fi

if [[ "$dry_run" == true ]]; then
  printf '%s\n' "$body"
  exit 0
fi

: "${REPO:?REPO must name the repository}"
# The issues endpoint takes comments on both issues and pull requests.
jq -n --arg body "$body" '{body: $body}' |
  gh api --method POST "repos/$REPO/issues/$number/comments" --input - --jq .html_url
