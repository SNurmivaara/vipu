---
name: refactor
description: Plan or execute a behavior-preserving refactoring of Vipu code, guided by a smell catalog, a refactoring catalog, SOLID and Clean Code, with a TODO list and Definition of Done for every step. Use when the user asks to refactor, clean up, restructure, split a large file or component, reduce complexity, remove duplication, pay down tech debt, or apply SOLID or Clean Code, and when implementing an issue that is part of a refactoring epic.
---

# Refactor Vipu code

A refactoring changes the structure of code without changing its observable
behavior. Each step is a named refactoring from `references/catalog.md` whose
mechanics preserve behavior by construction, and each step is checked by tests that
were green before it and stay green after it. That pairing, not good intentions, is
what makes a refactoring safe. `AGENTS.md` stays the authority on conventions,
checks and migrations; this skill adds the refactoring discipline.

Load the references when a step below names them:

| File | Use it for |
| --- | --- |
| `references/principles.md` | Safety rules, SOLID and Clean Code applied to Vipu, thresholds |
| `references/smells.md` | Finding problems: each smell, how to detect it, which refactorings cure it |
| `references/catalog.md` | Doing the work: mechanics, safety notes and proof for each refactoring |
| `references/plan-template.md` | The plan document and the epic and child issue bodies |

## Observable behavior in Vipu

Everything below must be identical before and after a refactoring:

- HTTP status codes and parsed JSON bodies of every route, including numeric values
  (a `float` that differs in the last digit is a behavior change).
- Database state after each request, including writes made by reads:
  `GET /api/budget/current` archives expired items and clears stale overrides.
- The MCP surface (server instructions, tool names, titles, descriptions, input and
  output schemas, annotations, prompts, resources) and tool output text.
- What the UI renders and what each interaction sends to the API.
- Error types, messages and status codes that reach a client.

Not observable, and free to change: names and locations of internal functions,
classes and modules, private helpers, internal data structures, and comments.

**Two hats.** While refactoring you never change behavior. A bug found on the way
goes into the plan's "Suspected bugs" list or a new issue; it is fixed in its own
change, never inside a refactoring step. If a step can only be done by changing a
test assertion, it is not a refactoring: stop and report it.

## Choose the mode

- `/refactor plan <target>`: analyze a file, module, component or directory and
  produce a step-by-step plan. Nothing is edited. With no target, rank candidates
  (see "Picking a target") and ask the user which to plan.
- `/refactor <issue number>`: execute one child issue of a refactoring epic.
  `/implement-issue` defers to this mode for issues labeled `refactor` or listed
  in a refactoring epic, so `@claude implement this` follows the same rules.

## Plan mode

Work through this TODO list in order. Every item produces a section of the plan
(`references/plan-template.md`); do not skip one because it seems obvious.

- [ ] **Baseline.** Record `git rev-parse HEAD`, run the package checks and confirm
  they are green (a red baseline makes every later step unprovable: stop and
  report). Record for the target:
  - Size: `git grep -c '' -- <path>` (lines per file) and the longest functions
    or components.
  - Churn: `git log --since=6.months --oneline -- <path>`. Code that rarely
    changes earns a smaller plan; say so in the goal.
  - Complexity, Python (from the package directory):
    `uv run --locked ruff check --select C901,PLR0911,PLR0912,PLR0913,PLR0915 --statistics <path>`
    and the same without `--statistics` for the locations.
  - Complexity, TypeScript (from `frontend/`):
    `npx eslint --rule 'complexity: [warn, 10]' --rule 'max-lines-per-function: [warn, 80]' <path>`
  - Coverage, Python: run the whole package suite with the top-level package as
    the source and read the target's row:
    `uv run --locked pytest --cov=app --cov-report=term-missing` in `backend/`,
    `--cov=vipu_mcp` in `mcp-server/`. Do not pass a submodule such as
    `--cov=app.routes.networth`: it breaks SQLAlchemy's compiled cache keys and the
    tests fail with `TypeError: 'InternalTraversal' object is not callable`.
    Frontend: `npx vitest run --coverage --coverage.include=<path>`.
- [ ] **Interface inventory.** List everything outside the target that depends on
  it, because these are the things a refactoring must keep working:
  - Routes and their OpenAPI operations; MCP tools, prompts and resources.
  - Every name imported from the target and the importing files:
    `git grep -n -E "from app\.<module>( |\.)|import app\.<module>"` for Python,
    `git grep -n -E "from \"@/<path>\"" -- frontend` for the frontend.
  - Internals that tests import, and every `patch("...")` or `monkeypatch.setattr`
    target that names the target's module. These pin module paths: moving the
    patched name breaks the test without any behavior change, so the plan must
    keep a re-export or move the patch target in the same step.
- [ ] **Interface snapshot.** Run `./scripts/snapshot-interfaces.sh /tmp/refactor-baseline`
  to confirm the surface exports cleanly on the baseline. Execute mode takes its
  own before and after snapshots for each PR.
- [ ] **Findings.** Walk `references/smells.md` against the target. Each finding
  names the smell, a `file:line`, the evidence (metric, duplicated lines, call
  sites), and the cure from the catalog. Prefer a few well-evidenced findings over
  a long list of opinions.
- [ ] **Target structure.** Sketch where the code ends up: modules or components,
  one responsibility each, and which way dependencies point (pure calculation
  core, Flask, SQLAlchemy and React Query at the edges). Check it against
  `references/principles.md`, including the "when not to" notes: no abstraction
  without a smell that pays for it.
- [ ] **Sequence.** Order the steps so each one is a single catalog refactoring
  that leaves everything green. Put a characterization-test step (a test-only
  commit that pins current behavior) before any step that moves or changes lines
  the baseline shows as uncovered. Pure moves come before edits to the moved code,
  so reviewers see moves as moves. Each step names the narrow check that proves it.
- [ ] **Group into PRs.** One child issue per reviewable PR: one theme, and roughly
  400 changed lines or fewer excluding pure moves. Characterization tests may be
  their own first child. Order children so each starts from a green main.
- [ ] **Write and review.** Fill in `references/plan-template.md`, show the user
  the whole plan, and revise until they approve. Then file the epic and children
  the way the `/new-issue` skill does, with the `refactor` label (create it with
  `gh label create refactor --description "Behavior-preserving restructuring"`
  if `gh label list` lacks it). Never file before approval.

### Plan Definition of Done

- [ ] The baseline is recorded and was green.
- [ ] The interface inventory covers routes, MCP surface, importers, test imports
  and patch targets.
- [ ] Every step names exactly one refactoring from the catalog, its target, its
  precondition and the check that proves it.
- [ ] Uncovered code is pinned by characterization tests before it is moved.
- [ ] No step changes observable behavior; suspected bugs are listed separately.
- [ ] Targets are measurable: lines per file, complexity findings, coverage not
  lower than baseline.
- [ ] Each child issue is workable from `gh issue view <n>` alone and carries the
  PR Definition of Done below as its acceptance criteria.

## Execute mode

For one child issue. Steps 1 and 2 of `/implement-issue` (read the issue, branch
from `origin/main`) apply; name the branch `refactor/<n>-<slug>`.

- [ ] Read the child and its epic. Confirm prerequisites are closed and that the
  plan still matches the code (`git log origin/main -- <target>` since the plan's
  baseline commit). If the code moved on, update the steps in an issue comment
  before starting.
- [ ] Run the package checks: green, or stop.
  `./scripts/snapshot-interfaces.sh /tmp/refactor-before`. Record the baseline
  metrics the issue names.
- [ ] For each step, in order:
  1. Read the catalog entry and follow its mechanics.
  2. Run the step's narrow check (the touched test file or package `pytest`, plus
     `mypy .` or `npm run typecheck`).
  3. Green: commit with `refactor: <refactoring name> <what>`, for example
     `refactor: extract function for pay period bounds in deadline_calc`.
     Characterization-test commits use `test: pin <behavior>`.
  4. Red, and the cause is not obvious within a few minutes: set the step aside
     with `git stash push -u -m "failed: <step>"` (it stays available to inspect)
     and retry in smaller steps. Never debug forward on top of a broken
     refactoring.
- [ ] Run `./test.sh`. Also run `./scripts/test-docker.sh` when the frontend,
  routes, startup or the MCP server changed.
- [ ] `./scripts/snapshot-interfaces.sh /tmp/refactor-after` and
  `git diff --no-index /tmp/refactor-before /tmp/refactor-after`: it must print
  nothing.
- [ ] Check that tests changed only in imports, patch targets and new
  characterization tests:
  `git diff origin/main -- backend/tests mcp-server/tests 'frontend/*.test.*'`.
- [ ] Re-measure size, complexity and coverage. Help reviewers see moves:
  `git diff -M --color-moved=zebra origin/main --stat` and without `--stat`.
- [ ] Open the PR as in `/implement-issue` step 6. The body lists the refactorings
  applied in order, the before and after metrics, the empty snapshot diff, and
  states "No behavior change". Suspected bugs go in "Limitations and follow-ups".

### Step Definition of Done

- [ ] Exactly one catalog refactoring, applied by its mechanics.
- [ ] The step's narrow check and the type checker are green.
- [ ] No test assertion changed; only imports or patch targets, if anything.
- [ ] Committed on its own with a `refactor:` (or `test:`) subject.

### PR Definition of Done

- [ ] Every commit meets the step DoD.
- [ ] `./test.sh` is green, and `./scripts/test-docker.sh` too when it applies.
- [ ] The before and after interface snapshots are identical, and
  `docs/openapi.json` is unchanged.
- [ ] Tests changed only in imports, patch targets and added characterization tests.
- [ ] Coverage of the touched code is not below baseline.
- [ ] The issue's size and complexity targets are met, or the PR says why not.
- [ ] No new dependency, migration, API field or MCP tool.

## Vipu traps

These change behavior while looking like pure restructuring. Check the matching
section of `AGENTS.md` before touching such code.

- **Decimal and float.** Monetary values are `Decimal` in models and become
  `float` in serializers. Extracting a helper that converts earlier, sums in a
  different order, or returns `float` where callers expected `Decimal` changes
  results in the last digit. Keep conversion points exactly where they are.
- **Rounding.** Rounding is context-specific (`ROUND_HALF_UP` in summaries,
  Decimal context rounding and `ROUND_CEILING` in FIRE, Python `round` elsewhere).
  Never unify rounding as a "deduplication"; that is a behavior change.
- **Signs.** Balances are signed; some projection inputs carry positive
  magnitudes. Merging two similar functions across that boundary flips signs.
- **Reads that write.** Some GET handlers and MCP read tools archive or clear data.
  Separate Query from Modifier is a behavior change there unless both halves still
  run in the same order on the same request.
- **Order of effects.** In routes, the order of `db.session` writes, `commit()` and
  reads determines what a response contains. Slide Statements only across
  statements that do not touch the session or shared state.
- **SQLAlchemy loading.** Moving query code out of a request can detach instances
  or turn one query into many. Keep functions that query inside the same session
  scope and keep their loading options.
- **Migrations.** Released migration IDs and SQL are never edited, moved or
  "cleaned up". They are out of scope for any refactoring.
- **Patch targets.** `patch("app.routes.budget_snapshots.date")` and similar pin
  where a name is looked up. Moving the code that uses it means moving the patch
  target in the same step.
- **Splitting modules.** When a module becomes a package or loses functions, keep
  the old import path working with re-exports until every importer has moved, so
  each step stays small and green.
- **API contract.** Response keys, `null` versus missing, status codes and error
  messages are all contract. The snapshot catches schema drift, not value drift;
  tests catch values.
- **Route docstrings and names.** A route function's docstring becomes its
  OpenAPI summary and description, and the blueprint name plus the function name
  form the endpoint name used by `url_for`. Moving a route is safe; rewording its
  docstring or renaming it changes the spec. Keep both, and let the snapshot
  confirm.

## Picking a target

With no target, rank candidates and let the user choose:

```sh
git grep -c '' -- 'backend/app/*.py' 'mcp-server/vipu_mcp/*.py' 'frontend/*.ts' 'frontend/*.tsx' \
  | sort -t: -k2 -rn | head -15
uv --directory backend run --locked ruff check --select C901,PLR0912,PLR0915 --statistics app
```

Prefer code that is both large or complex and changing often
(`git log --since=6.months --format= --name-only | sort | uniq -c | sort -rn | head`),
since that is where structure costs the most. Frontend targets need Vitest
coverage first; plan a characterization-test child when they have none.
