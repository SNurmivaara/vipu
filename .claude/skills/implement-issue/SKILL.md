---
name: implement-issue
description: Implement a Vipu GitHub issue end to end, from reading the issue through a branch, tests and checks to a pull request. Use when the user asks to implement, build, fix or pick up an issue by number or link.
---

# Implement a Vipu issue

This skill walks the lightweight change workflow in `AGENTS.md` with concrete
commands. `AGENTS.md` stays the authority on conventions, checks and migrations;
reread the relevant section there rather than relying on this summary.

The same steps apply when `@claude` runs this in GitHub Actions. There, the trigger
comment is your only conversation with the user: put questions and the hand-off in
your comment, and treat `@claude implement this` as the request to open the PR.

## 1. Read the issue

```sh
gh issue view <n> --comments
```

If it starts with `Part of #<epic>.`, read the epic too and confirm the listed
prerequisites are closed (`gh issue view <prereq> --json state`). Stop and ask the
user when a prerequisite is open, the issue is still waiting on a decision (for
example "needs the maintainer's approval"), or an acceptance criterion is too vague
to test. Check for an existing branch or PR with `gh pr list --search "<n>"`.
In GitHub Actions, post the question in your comment and stop.

## 2. Branch from main

Confirm `git status` is clean, then:

```sh
git fetch origin
git switch -c <type>/<n>-<short-slug> origin/main
```

Use the conventional commit type as the prefix (`feat`, `fix`, `docs`, `ci`, ...).
In GitHub Actions the action has already created a `claude/` branch; stay on it,
unless an earlier run on this issue stopped before finishing. Its branch is named
`claude/issue-<n>-<timestamp>`. List those branches and their PRs, and continue the
newest one whose PR is open or that has no PR; ignore one whose PR is closed or
merged:

```sh
git ls-remote --heads origin 'refs/heads/claude/issue-<n>-*'
gh pr list --head <branch> --state all --json number,state
git fetch --unshallow origin main
git fetch origin <branch>
git switch -c <branch> FETCH_HEAD
git log --oneline origin/main..HEAD
```

Read those commits and the earlier run's comments on the issue, then resume at the
first milestone (step 4) the branch lacks. Build on the commits as they are: do not
redo them, rebase or force-push. When the branch has an open PR, update it at
step 6 instead of opening another.

## 3. Investigate

Follow the navigation table in `AGENTS.md` to the code, tests and docs involved.
Before changing behavior, read the existing implementation and its tests. If the
investigation contradicts the issue, say so and agree the change with the user
before writing code. For calculations and migrations, check the financial
conventions and migration rules in `AGENTS.md` first.

When the issue is labeled `refactor` or is a child of a refactoring epic, read
`.claude/skills/refactor/SKILL.md` and follow its execute mode for steps 3 to 6:
one catalog refactoring per commit, the interface snapshot diff, and its step and
PR Definition of Done. Locally, name the branch `refactor/<n>-<short-slug>`; in
GitHub Actions stay on the `claude/` branch, as step 2 says.

## 4. Implement

Keep the change to the issue's scope. Add regression tests that fail without the
change, especially for financial calculations and migrations. For API changes,
regenerate `docs/openapi.json` and update `docs/api.html` and `docs/guide.html` as
`AGENTS.md` describes. A data-transforming migration also needs a test in
`backend/tests/test_migrations_postgres.py`.

In GitHub Actions, commit and push with `git push -u origin HEAD` at each
milestone, so a run that stops early (usage limit, timeout, error) keeps its work
and a retry continues from it (step 2):

1. The regression tests are written.
2. The implementation passes the narrow checks of step 5.
3. The full checks of step 5 pass.

Skip a milestone with nothing new to commit. A push to a branch without a PR starts
no CI. Locally, push only at step 6.

## 5. Verify

Run the narrow checks for the touched package first, then `./test.sh`. When the
change touches `frontend/`, the API, startup or the Docker setup, also run
`./scripts/test-docker.sh`: it builds the production images, checks health and
migrations, and runs the Playwright smoke tests, including any you added. For
migration changes run `./scripts/test-migrations-postgres.sh`. Both need only
Docker, which GitHub Actions runners have, and take several minutes, so give the
command a long timeout. Never leave a new or changed test for CI to run first.

Map each acceptance criterion to the test or check that proves it. When a
criterion has no evidence, add the test; if you cannot, open the PR as a draft
(step 6) and say which criterion is missing and why. Report the checks you ran and
the evidence that is missing, not checks the change never needed.

## 6. Commit and open the PR

Commit with a conventional subject (`feat: ...`, `fix: ...`). Locally, show the
user the diff summary and the PR draft before pushing, unless they already asked
you to open the PR. In GitHub Actions, open it yourself instead of posting a
"Create PR" link, or update it with `gh pr edit` when the branch already has one.

```sh
git push -u origin HEAD
gh pr create --base main --title "<type>: <summary>" --body-file <file>
```

Write the body in the sections of `.github/pull_request_template.md`, starting with
`Closes #<n>` (or `Part of #<n>` when the PR does not finish the issue). Under
acceptance evidence, list each criterion with the test or check that proves it,
and the exact commands run with their results. Add `--draft` when a criterion
lacks evidence or a check fails. Add no "Generated with Claude Code" line. Use
synthetic data only. Do not merge, release or deploy.

After pushing more commits to an open PR, rewrite its body with
`gh pr edit <n> --body-file <file>` so the evidence matches the code, and run
`gh pr ready <n>` once every criterion has evidence and the checks pass.

## 7. Hand off

Reply with the PR link, what was verified, and what remains. When work stops
before a PR, post the `AGENTS.md` handoff block as an issue comment with
`gh issue comment <n> --body-file <file>` if the user agrees, otherwise include
it in the reply. In GitHub Actions the hand-off goes in your comment, together with
any tool call that was denied.
