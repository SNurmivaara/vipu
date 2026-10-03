---
name: implement-issue
description: Implement a Vipu GitHub issue end to end, from reading the issue through a branch, tests and checks to a pull request. Use when the user asks to implement, build, fix or pick up an issue by number or link.
---

# Implement a Vipu issue

This skill walks the lightweight change workflow in `AGENTS.md` with concrete
commands. `AGENTS.md` stays the authority on conventions, checks and migrations;
reread the relevant section there rather than relying on this summary.

## 1. Read the issue

```sh
gh issue view <n> --comments
```

If it starts with `Part of #<epic>.`, read the epic too and confirm the listed
prerequisites are closed (`gh issue view <prereq> --json state`). Stop and ask the
user when a prerequisite is open, the issue is still waiting on a decision (for
example "needs the maintainer's approval"), or an acceptance criterion is too vague
to test. Check for an existing branch or PR with `gh pr list --search "<n>"`.

## 2. Branch from main

Confirm `git status` is clean, then:

```sh
git fetch origin
git switch -c <type>/<n>-<short-slug> origin/main
```

Use the conventional commit type as the prefix (`feat`, `fix`, `docs`, `ci`, ...).

## 3. Investigate

Follow the navigation table in `AGENTS.md` to the code, tests and docs involved.
Before changing behavior, read the existing implementation and its tests. If the
investigation contradicts the issue, say so and agree the change with the user
before writing code. For calculations and migrations, check the financial
conventions and migration rules in `AGENTS.md` first.

## 4. Implement

Keep the change to the issue's scope. Add regression tests that fail without the
change, especially for financial calculations and migrations. For API changes,
regenerate `docs/openapi.json` and update `docs/api.html` and `docs/guide.html` as
`AGENTS.md` describes. A data-transforming migration also needs a test in
`backend/tests/test_migrations_postgres.py`.

## 5. Verify

Run the narrow checks for the touched package first, then `./test.sh`. Run the
PostgreSQL migration tests or Playwright smoke tests when the change needs them;
`AGENTS.md` lists the commands and their prerequisites. Map each acceptance
criterion to the evidence that proves it, and note anything you could not check.

## 6. Commit and open the PR

Commit with a conventional subject (`feat: ...`, `fix: ...`). Show the user the
diff summary and the PR draft before pushing, unless they already asked you to
open the PR.

```sh
git push -u origin HEAD
gh pr create --base main --title "<type>: <summary>" --body-file <file>
```

Write the body in the sections of `.github/pull_request_template.md`, starting with
`Closes #<n>` (or `Part of #<n>` when the PR does not finish the issue). Under
acceptance evidence, list the exact commands run and their results. Use synthetic
data only. Do not merge, release or deploy.

## 7. Hand off

Reply with the PR link, what was verified, and what remains. When work stops
before a PR, post the `AGENTS.md` handoff block as an issue comment with
`gh issue comment <n> --body-file <file>` if the user agrees, otherwise include
it in the reply.
