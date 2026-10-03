---
name: new-issue
description: Turn a problem or idea for Vipu into a GitHub issue in the change-request format, or an epic with PR-sized child issues for larger work. Use when the user wants to file, draft, plan or spec an issue, bug, feature or task.
---

# File a Vipu issue

The issue is the specification that `@claude implement this` or a local session
builds from, so the acceptance criteria must be precise enough to test. Follow
these steps in order and do not file anything before the user approves the draft.

## 1. Understand the problem

Ask only what you cannot find out yourself: what happens today, what should happen
instead, and anything deliberately out of scope. One short round of questions at most.

## 2. Investigate before drafting

Read the code, tests and docs involved (see the navigation table in `AGENTS.md`).
Name the real files, functions and endpoints in the draft. For bugs, reproduce or
trace the cause far enough to describe it accurately; say so if you could not.
Check `gh issue list --state all --search "<keywords>"` for duplicates and related work.

Use synthetic figures only. Never copy balances, incomes or other real data from the
Vipu MCP tools, the database or screenshots into an issue: the repository is public.

## 3. Choose the shape

- One issue when the change fits one reviewable PR.
- Otherwise an epic plus one child issue per PR. The epic holds the goal, the settled
  decisions and the non-obvious domain rules, and a checklist linking the children.
  Each child starts with `Part of #<epic>.` and its prerequisites, and must be
  workable from `gh issue view <n>` alone.

## 4. Draft

Use the sections of `.github/ISSUE_TEMPLATE/change-request.md`, in order:

- **Problem and desired outcome**: observable behavior now and after. For bugs,
  reproduction steps with synthetic data.
- **Scope and non-goals**: files to touch, and what is deliberately excluded.
- **Acceptance criteria**: checkboxes, each an observable and testable outcome,
  including edge cases. Name exact expected values where it matters (dates, totals,
  rounding). Vague criteria such as "works correctly" cost a review round later.
- **Approach**: optional, only what the investigation settled.
- **Verification**: the commands and tests that prove each criterion. GitHub Actions
  runners have Docker, so `./scripts/test-docker.sh` (full stack and Playwright) and
  `./scripts/test-migrations-postgres.sh` run there; never tell the implementer to
  leave a check to CI. Note only what no runner can do, such as a visual check of
  the UI.
- **Rollout and recovery**: migrations, compatibility, backups, or "No special
  rollout or recovery steps".

Respect the financial conventions and migration rules in `AGENTS.md`; call out in the
issue any criterion that touches them.

Style: imperative title without a type prefix (`Fix ...`, `Add ...`), concise
sentences, no filler sections. Label with `bug`, `enhancement` or `documentation`.

## 5. Review with the user

Show the full draft (titles, labels, bodies). Revise until the user approves.

## 6. File

Write each body to a temporary file and run
`gh issue create --title "..." --label <label> --body-file <file>`. For an epic, file
it first, then the children, then edit the epic's checklist with the child numbers.
Reply with the issue links and say whether each issue suits `@claude implement this`
or a local session.
