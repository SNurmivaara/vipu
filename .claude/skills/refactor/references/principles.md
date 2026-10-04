# Principles

Read this when designing the target structure of a plan, or when unsure whether a
change is worth making. The principles say where to go; `catalog.md` says how to
get there safely.

## Rules of refactoring

1. **Behavior is frozen.** Observable behavior (see `SKILL.md`) is identical after
   every step. Tests are the specification: their assertions do not change during
   a refactoring. Only imports and patch targets may follow moved code.
2. **Green to green.** Start from passing checks and pass them again after every
   step. A step that cannot be made green quickly is discarded, not repaired.
3. **Small steps.** One named refactoring per step and per commit. A large change
   is a sequence of small ones, each of which could be the last.
4. **One hat at a time.** Refactoring and changing behavior alternate; they never
   share a commit or a PR. To add a feature to awkward code, refactor first, then
   add the feature in a separate change.
5. **Tests first where there are none.** Before moving code that no test executes,
   pin its current behavior with characterization tests, bugs included. Fixing
   the bug is a later, separate change.
6. **Mechanical over clever.** Prefer edits whose safety follows from their form
   (rename every reference, move unchanged lines, extract with all inputs as
   parameters) over rewrites whose safety depends on reasoning.
7. **Measure.** Record size, complexity and coverage before and after. A
   refactoring that does not improve a measured or named problem is churn.
8. **Stop at good enough.** The goal is code that is easy to change for the work
   the project is actually doing, not an ideal design.

## SOLID in a function-and-module codebase

Vipu is a small Flask app, an MCP server and a Next.js frontend. Most code is
functions, modules, SQLAlchemy models and React function components; there are
few classes and almost no inheritance. Read SOLID with that in mind: "class" often
means "module" or "component", and "interface" often means "the parameters a
function takes" or "the props a component accepts".

### Single Responsibility (SRP)

A unit has one reason to change: one actor or one concern drives its edits.

- **In Vipu:** a route handler that parses the request, computes a projection and
  shapes the JSON has three reasons to change. `deadline_calc.py` is a good
  counterexample: it computes dates and movements from plain arguments and leaves
  persistence to callers.
- **Symptoms:** Divergent Change, Large Class or module, Long Function with phases
  separated by comments, a component that fetches, transforms and renders.
- **Refactorings:** Split Phase, Extract Function, Extract Class, Move Function,
  Split Module into Package, Extract React Component, Extract Custom Hook.
- **When not to:** do not split a 30-line function into five 6-line functions that
  are only ever called together. Responsibilities are about reasons to change, not
  line counts.

### Open/Closed (OCP)

Adding a case should mean adding code, not editing every place that switches on
the case.

- **In Vipu:** branching on `frequency_unit` (`"days"`, `"weeks"`, `"months"`,
  `"years"`) appears in `deadline_calc.py`, `routes/budget.py` and `summary.py`. A
  new unit would need edits in each.
- **Symptoms:** Repeated Switches, Shotgun Surgery when a new variant appears.
- **Refactorings:** Replace Conditional with Polymorphism, or in Python more often a
  dispatch table (a dict from the case to a function); Combine Functions into Class
  for the per-case behavior.
- **When not to:** a single `if`/`elif` over a closed set that has not changed in
  a year is fine. Introduce the dispatch when there are at least two switches on
  the same cases, or a new case is actually coming.

### Liskov Substitution (LSP)

Anything that stands in for a type must honor its contract: same accepted inputs,
same guarantees about outputs and side effects.

- **In Vipu:** subclasses of `TestingConfig` in tests, the `httpx` transports that
  replace the network in MCP tests, TypeScript union types such as `GoalType`
  and `FrequencyUnit`, and functions passed as callbacks to components.
- **Symptoms:** Refused Bequest, `isinstance` or `type` checks on something that
  should be substitutable, a union member that callers special-case.
- **Refactorings:** Replace Subclass with Delegate, Replace Superclass with
  Delegate, Extract Superclass only when all subtypes truly share behavior.
- **When not to:** do not invent a hierarchy to have something to substitute.

### Interface Segregation (ISP)

Callers depend only on what they use.

- **In Vipu:** a helper that takes a whole model or settings object but reads two
  fields; a component that takes the full `ForecastingSettings` to render one
  slider; an MCP tool module that imports the entire client to call one method.
- **Symptoms:** Long Parameter List (the opposite failure), Feature Envy, wide
  props objects passed through several components (prop drilling).
- **Refactorings:** Introduce Parameter Object where fields travel together;
  Replace Parameter with Query or narrow the parameters to the fields used; split
  props; Extract Custom Hook so children read what they need.
- **When not to:** Preserve Whole Object is right when the callee uses most of the
  object or will grow to. Narrowing every signature to scalars produces Long
  Parameter Lists.

### Dependency Inversion (DIP)

Policy (financial calculation) does not depend on mechanism (Flask, SQLAlchemy,
HTTP, the clock). Both depend on plain data passed across a narrow boundary.

- **In Vipu:** `deadline_calc.py` functions take `today: date` instead of calling
  `date.today()`, which keeps them deterministic and testable. Code that calls
  `db.session` or `request` from inside a calculation, or reads the clock deep in a
  helper, inverts this.
- **Pattern:** functional core, imperative shell. Routes and MCP tools load data,
  call pure functions with plain values, then persist and serialize.
- **Symptoms:** tests that need a database or `patch("<module>.date")` to exercise
  arithmetic; calculations importing `db`; components calling `axios` directly
  instead of going through `lib/api.ts` and a hook.
- **Refactorings:** Split Phase (load, compute, respond), Replace Query with
  Parameter (pass `today` or loaded rows in), Move Function into a pure module,
  Extract Custom Hook for data access.
- **When not to:** do not add abstract repositories or service interfaces with a
  single implementation. Passing plain data is the inversion this codebase needs.

## Clean Code

- **Names reveal intent in the domain's words.** Use the vocabulary of
  `docs/guide.html` and the models: pay period, obligation, occurrence, snapshot,
  net worth, goal, roadmap. A name that needs a comment is the wrong name. Avoid
  `data`, `info`, `tmp`, `result2`, `handle`, `process`, `manager`.
- **Functions are small and at one level of abstraction.** A function either
  orchestrates other named steps or does one low-level thing. Comments that label
  sections of a function are extraction points.
- **Few parameters.** Zero to three is easy to read; more suggests a parameter
  object or a missing concept. Boolean flag parameters mean the function does two
  things: Remove Flag Argument.
- **Command-query separation.** A function either returns information or changes
  state. Vipu has deliberate exceptions (reads that archive and clear overrides).
  Note them, never "fix" them inside a refactoring.
- **No duplication of knowledge.** Duplicated rules (how a frequency becomes a
  monthly amount, how a period is bounded) must live in one place. Duplicated
  shapes of code that encode different rules are not duplication. Wait for the
  third occurrence before abstracting incidental similarity.
- **Comments explain why.** Keep the repository's style: docstrings and comments
  that explain decisions, constraints and non-obvious domain rules. Delete comments
  that restate the code; turn "what" comments into names.
- **Errors at the boundary.** Validation and error translation happen where input
  enters (schemas, route handlers, MCP tool wrappers). Core functions assume valid
  input and raise plain exceptions; they do not build HTTP responses.
- **No dead code.** Unused functions, parameters, branches and commented-out code
  go. Check that nothing imports or patches the name first, including tests and the
  MCP server.
- **Data has a shape.** Long-lived dicts passed between functions deserve a
  `TypedDict` or dataclass (Python) or an interface (TypeScript), introduced so the
  runtime values stay identical.
- **Tests are clean code too.** Fast, independent, repeatable, self-validating,
  and readable as a specification. Characterization tests name the behavior they
  pin.

## Thresholds

Signals that a smell is likely, not rules. Always read the code before acting.

| Signal | Threshold | Tool |
| --- | --- | --- |
| Module or component file | over 500 lines | `git grep -c '' -- <path>` |
| Function | over 40 lines | read, or `max-lines-per-function` |
| Cyclomatic complexity | over 10 | ruff `C901`, eslint `complexity` |
| Branches in one function | over 12 | ruff `PLR0912` |
| Statements in one function | over 50 | ruff `PLR0915` |
| Return statements | over 6 | ruff `PLR0911` |
| Parameters | over 5 | ruff `PLR0913` |
| React component | over 250 lines, or over 6 `useState` | read |
| Nesting depth | over 3 levels | read |
