# Plan template

Fill in every section. Write "None" rather than deleting a section, so a reader can
tell it was considered. Use synthetic values only: the repository is public.

## Plan document

````markdown
# Refactoring plan: <target>

## Goal and non-goals
<One paragraph: the problem in measurable terms (size, complexity, duplication,
change pain) and the intended end state. Non-goals: what this plan will not touch,
always including behavior, the API contract and migrations.>

## Baseline
- Commit: <sha>
- Checks: <commands run, all green>
- Size: <file: lines; largest functions or components with lines>
- Complexity: <ruff or eslint findings by rule, with counts>
- Coverage: <percent for the target; uncovered line ranges that later steps touch>
- Interface snapshot: `./scripts/snapshot-interfaces.sh /tmp/refactor-baseline`

## Interface inventory
| Kind | Item | Used by |
| --- | --- | --- |
| Route | `GET /api/...` | frontend `lib/api.ts`, MCP `tools/read.py` |
| Import | `app.<module>.<name>` | `<file>:<line>`, tests |
| Patch target | `"app.<module>.<name>"` | `tests/<file>:<line>` |
| MCP tool | `<tool>` | |
| Export | `<Component>` | `<file>` |

## Findings
| # | Smell | Location | Evidence | Cure |
| --- | --- | --- | --- | --- |
| F1 | Long Function | `app/x.py:120` | 140 lines, C901 = 18 | Split Phase, Extract Function |

## Target structure
<Module or component map: each unit, its single responsibility, and what it
depends on. Show dependency direction (pure core <- routes and tools). Say why each
new unit pays for itself, citing findings.>

## Steps
| # | Refactoring | Target | Precondition | Proof | Check | Est. lines | Risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| S1 | Characterization tests | `x()` branches A to C | none | n/a | `pytest tests/test_x.py` | +80 | low |
| S2 | Split Module into Package | `app/x.py` -> `app/x/` | S1 | P1 | `pytest`, `mypy .`, snapshot | +10 | low |
| S3 | Move Function | `foo`, `bar` -> `app/x/periods.py` | S2 | P1 | `pytest tests/test_x.py`, `mypy .` | 0 | low |

One row per commit. Every refactoring name exists in `catalog.md`. Precondition
names the step or coverage the step relies on.

## PR grouping
| Child | Steps | Est. changed lines (excluding pure moves) | Depends on |
| --- | --- | --- | --- |
| 1. Pin <behavior> with characterization tests | S1 | 80 | none |
| 2. Split <module> into a package | S2 to S5 | 120 | 1 |

## Expected outcome
- `<file>`: <before> -> at most <after> lines
- <rule> findings in `<path>`: <before> -> at most <after>
- Coverage of `<target>`: not below <baseline>%

## Suspected bugs (not fixed here)
<Behavior that looks wrong, with location and a synthetic reproduction. Each
becomes its own issue after the refactoring, or "None".>

## Risks
<P3 steps, traps from `SKILL.md` that apply, and how each is mitigated.>
````

## Epic issue

Title: `Refactor <target> into <end state>` (imperative, no type prefix).
Label: `refactor`.

```markdown
## Problem and desired outcome
<Goal paragraph from the plan, with the baseline numbers.>

This is a refactoring: observable behavior, the REST API, the MCP surface and the
database schema do not change. Each child follows the execute mode and Definition
of Done in `.claude/skills/refactor/SKILL.md`.

## Scope and non-goals
<Files in scope. Non-goals from the plan.>

## Plan
<Baseline, interface inventory, findings, target structure, steps and expected
outcome from the plan document. Suspected bugs, linked to their own issues.>

## Children
- [ ] #<n> <title>
- [ ] #<n> <title>

## Rollout and recovery
No special rollout or recovery steps: no schema, API or MCP change.
```

## Child issue

Title: imperative description of the PR (`Split app/fire.py into a package`).
Label: `refactor`. Must be workable from `gh issue view <n>` alone.

```markdown
Part of #<epic>. Prerequisites: #<n> (or none).

## Problem and desired outcome
<What this PR restructures and why, with the relevant baseline numbers.>

## Scope and non-goals
In scope: <files>. Not in scope: behavior changes, API, MCP surface, schema,
<anything later children do>.

## Acceptance criteria
- [ ] Steps S<a> to S<b> applied in order, one commit per step, each subject
  naming its refactoring (`refactor: <Refactoring> ...` or `test: pin ...`).
- [ ] `./scripts/snapshot-interfaces.sh` output identical before and after
  (`git diff --no-index` empty), and `docs/openapi.json` unchanged.
- [ ] No existing test assertion changed; tests differ only in imports, patch
  targets and added characterization tests.
- [ ] `<file>` is at most <n> lines.
- [ ] <rule> findings in `<path>` drop from <before> to at most <after>.
- [ ] Coverage of `<target>` is at least <baseline>%.
- [ ] `./test.sh` passes<, and `./scripts/test-docker.sh` passes>.

## Approach
| # | Refactoring | Target | Proof | Check |
| --- | --- | --- | --- | --- |
<the step rows for this child, copied from the plan>

Traps that apply: <from SKILL.md, for example patch targets that move>.

## Verification
<Exact commands, including the narrow check per step, the snapshot diff and the
metric commands.>

## Rollout and recovery
No special rollout or recovery steps.
```
