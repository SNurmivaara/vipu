# Refactoring catalog

Each entry is one step in a plan and one commit in execution. Names follow the
standard catalog so they are recognizable; the mechanics are written for Python
and TypeScript in this repository. Follow the mechanics in order: their order is
what keeps every intermediate state working.

## Proof levels

Every entry has a proof level. The plan's step names it, and the step's check must
meet it.

- **P1, mechanical.** Safety follows from the form of the edit: renaming every
  reference, moving lines unchanged, re-exporting. Proof: the type checker, the
  package tests and an empty interface snapshot diff.
- **P2, local.** Safety follows from reasoning about a few lines: extracting a
  function, introducing a variable. Proof: P1, plus tests that execute the
  changed lines (check coverage of those lines; add characterization tests first
  if they are not covered).
- **P3, semantic.** Safety depends on reasoning about evaluation order, aliasing,
  or equivalence of two algorithms. Proof: P2, plus characterization tests that
  cover every branch of the old code, written and committed in an earlier step,
  and the reasoning stated in the commit body. Mark P3 steps as higher risk in the
  plan.

General safety notes for every entry:

- Python has no compiler to catch missed call sites. After any rename or move,
  `git grep -n <old name>` across the repository (including tests, `mcp-server/`
  and string patch targets) must return only intended hits, and `mypy .` must pass.
- In TypeScript, `npm run typecheck` catches most missed references; string keys
  (query keys, form field names) are not checked and must be searched.
- Keep `float(...)` and `Decimal` conversions, rounding calls and `db.session`
  operations exactly where they were unless the entry says otherwise.

---

## Composing functions

### Extract Function (P2)
- **Use when:** a fragment can be named by what it does; a comment labels a block;
  the same fragment appears twice.
- **Mechanics:**
  1. Create the function, named for its intent, and copy the fragment into it.
  2. Variables the fragment reads become parameters; a variable it assigns and
     the caller later uses becomes the return value (return a tuple or small
     dataclass if there are several, or split the extraction).
  3. Keep the exact expressions, including types and conversions.
  4. Replace the fragment with a call. Run the checks.
  5. Look for other copies of the fragment and replace them in separate steps.
- **Safety:** watch for early `return`, `break` and `continue` inside the
  fragment, mutation of variables the caller still uses, and generators. In React,
  never extract a fragment containing hooks into a plain function; use Extract
  Custom Hook.

### Inline Function (P2)
- **Use when:** the body is as clear as the name; a forwarding layer adds nothing;
  before re-extracting differently.
- **Mechanics:** check it is not polymorphic, overridden, patched in tests or
  part of the interface inventory; replace each call with the body, adapting
  parameters; delete the function.
- **Safety:** default argument values and keyword arguments must be reproduced at
  each call site.

### Extract Variable (P2)
- **Use when:** an expression is hard to read or repeated within a function.
- **Mechanics:** ensure the expression has no side effects; assign it to a named
  variable just before its first use; replace uses.
- **Safety:** do not hoist an expression above a statement that changes its inputs
  (including `db.session.flush()` and model attribute assignments).

### Inline Variable (P1)
- **Use when:** the name says no more than the expression.
- **Mechanics:** confirm it is assigned once; replace each reference with the
  expression; remove the assignment.

### Change Function Declaration (P1, P2 when changing parameters)
- **Use when:** a function name or parameter list misleads; adding or removing a
  parameter; renaming.
- **Mechanics (simple):** change the declaration and every call site in one step,
  when callers are few and all in the repository.
- **Mechanics (migration):** extract the body into a new function with the new
  declaration; make the old function call the new one; move callers one by one
  (each a step if many); inline and delete the old function.
- **Safety:** route functions and MCP tool functions are part of the interface:
  their Python names may change, but routes, endpoint names used in `url_for`,
  tool names and parameter names visible in schemas may not. Check the snapshot.

### Rename Variable (P1)
- **Use when:** a local or module-level name misleads.
- **Mechanics:** for a local, rename all references in scope. For a module-level
  name, Encapsulate Variable first if it is widely used.

### Replace Temp with Query (P2)
- **Use when:** a local holds a value computed from other values that could be a
  function, so other functions can use it too.
- **Mechanics:** ensure the variable is assigned once and its inputs do not change
  afterwards; Extract Function for the right-hand side; Inline Variable.
- **Safety:** do not use it for expressions that read the database or the clock;
  calling them twice can change results.

### Split Variable (P2)
- **Use when:** one variable is reused for two meanings.
- **Mechanics:** rename the first assignment and its uses up to the second
  assignment; repeat.

### Replace Function with Command (P2)
- **Use when:** a very long calculation with many locals and phases is hard to
  extract from because every fragment needs half the locals.
- **Mechanics:** create a class whose constructor takes the function's parameters
  and whose `execute()` holds the body; locals become attributes as needed; the
  original function constructs and executes it. Now Extract Function into methods.
- **Safety:** keep the original function as the public entry point. Prefer this
  only when Split Phase and Introduce Parameter Object have not been enough.

### Split Phase (P2)
- **Use when:** code does two things in sequence (parse then compute, compute then
  format, load then calculate then serialize).
- **Mechanics:**
  1. Extract the second phase into a function.
  2. Introduce an intermediate data structure (dict, `TypedDict` or dataclass)
     passed between phases.
  3. Move each value the second phase reads from the first phase's locals or
     parameters into the intermediate structure, one at a time.
  4. Extract the first phase into a function returning the structure.
- **Vipu:** the main tool for route handlers and for moving calculations into a
  pure core that takes plain data and `today`.

### Combine Functions into Transform (P2)
- **Use when:** several functions derive values from the same record and callers
  call them in sequence.
- **Mechanics:** write a transform that takes the record and returns a copy with
  derived fields added; move each derivation into it; switch callers to read the
  derived field.
- **Safety:** return a copy (`{**record, ...}`, `dataclasses.replace`); do not
  mutate the input.

### Combine Functions into Class (P2)
- **Use when:** several functions share the same parameters and are always used on
  the same data.
- **Mechanics:** Encapsulate Record for the shared data; Move Function each function
  into the class; leave module-level wrappers if callers are many, and remove them
  in later steps.

### Substitute Algorithm (P3)
- **Use when:** a clearer algorithm gives the same results.
- **Mechanics:** decompose the old code until the part being replaced is one
  function; write characterization tests that cover every branch and edge
  (empty input, boundaries, negative numbers, dates at month ends); replace the
  body; run the tests.
- **Warning:** for anything financial or date-based, results must be identical to
  the last digit and day. If any test result differs, it is a behavior change.

---

## Moving features

### Move Function (P1 for an unchanged body)
- **Use when:** a function is more about another module's data or concept; a large
  module is being split.
- **Mechanics:**
  1. Check what the function uses from its current module; move those helpers
     first or import them.
  2. Copy the function unchanged to the target module.
  3. Make the old name a re-export (`from app.new_module import name`) or a
     forwarding function.
  4. Run checks. Commit.
  5. In later steps, move importers to the new path and remove the re-export.
- **Safety:** update `patch("old.module.name")` targets that look the name up in
  the old module: a patch on the old module no longer affects code that now lives
  in the new one. Avoid circular imports: a new module must not import the module
  it was split from.

### Move Field (P2)
- **Use when:** a field on one structure is always used with another.
- **Mechanics:** Encapsulate Record if needed; add the field to the target; make the
  accessor read from the new place; migrate writers; remove the old field.
- **Safety:** never on SQLAlchemy model columns: moving a column is a schema change
  with a migration, not a refactoring.

### Move Statements into Function (P2)
- **Use when:** every call site of a function runs the same statements before or
  after it.
- **Mechanics:** Slide Statements next to the call at each site; move them into
  the function; delete them at the call sites.

### Move Statements to Callers (P2)
- **Use when:** a function's statements now differ between callers.
- **Mechanics:** extract the statements that stay into a new function; move the
  rest to each caller; inline the old function.

### Replace Inline Code with Function Call (P2)
- **Use when:** code reimplements an existing helper.
- **Mechanics:** confirm the helper gives identical results for all inputs the
  code sees (including types, rounding and `None`); replace.

### Slide Statements (P2)
- **Use when:** related statements are far apart; preparing for Extract Function.
- **Mechanics:** move a statement past a neighbor only if neither writes anything
  the other reads, and neither has side effects.
- **Safety:** never slide across `db.session` operations, `commit()`, `flush()`,
  model attribute assignments, HTTP calls or React hook calls.

### Split Loop (P2)
- **Use when:** one loop computes several unrelated results.
- **Mechanics:** copy the loop; remove one result's work from each copy; Extract
  Function each loop.
- **Safety:** iterating twice must not repeat side effects; lists only, not
  one-shot iterators or queries that run again.

### Replace Loop with Pipeline (P2)
- **Use when:** a loop filters, maps and accumulates.
- **Mechanics:** create a variable for the collection; replace each part of the
  loop body with a pipeline step (comprehension, `sum()`, `filter`/`map`/`reduce`
  in TypeScript); remove the loop.
- **Safety:** `sum()` over `Decimal` needs a `Decimal` start value
  (`sum(xs, Decimal("0"))`) to keep the type identical; summing floats in a
  different order can change the last digit, so keep the same order.

### Remove Dead Code (P1)
- **Use when:** nothing reaches the code.
- **Mechanics:** `git grep -n <name>` across the repository (including tests,
  `mcp-server/`, string patch targets, `url_for` endpoint names and the frontend for
  API routes); delete; run the checks.
- **Safety:** a route is never dead code just because the frontend does not call
  it; it is part of the API. Unused routes are a product decision.

---

## Organizing data and encapsulation

### Encapsulate Variable (P1)
- **Use when:** module-level or widely shared data is read and written directly.
- **Mechanics:** add getter and setter functions; replace each reference; restrict
  direct access (rename with a leading underscore).

### Encapsulate Record (P2)
- **Use when:** a dict or untyped object with a stable shape travels between
  functions.
- **Mechanics:** introduce a `TypedDict` (types only, runtime unchanged) or a
  dataclass. For a dataclass, convert at the boundary so serializers emit the
  identical dict (same keys, same `float` conversion, same `None` handling).
  In TypeScript, add an interface and annotate.
- **Safety:** `TypedDict` is P1. A dataclass is P2: check equality of the
  serialized output in tests.

### Encapsulate Collection (P2)
- **Use when:** callers mutate a list owned by another structure.
- **Mechanics:** add add and remove functions; make the getter return a copy or
  tuple; move mutating callers to the new functions.

### Replace Primitive with Object (P2)
- **Use when:** a bare string or number carries behavior (unit, frequency,
  percentage) that is reimplemented around it.
- **Mechanics:** Encapsulate Variable; create a small value class or a `Literal`
  type plus functions; change the accessor to return it; move behavior onto it.
- **Safety:** the JSON representation at the API boundary stays the same string or
  number.

### Replace Derived Variable with Query (P2; P3 in React)
- **Use when:** a variable stores what could be computed, and can get out of sync.
- **Mechanics:** find every assignment; write a function that computes the value;
  assert (in tests) that it equals the stored value; switch readers; remove the
  variable.
- **React:** replacing `useEffect` plus `setState` with a value computed during
  render changes render timing. Pin the rendered output with a component test.

### Change Reference to Value / Change Value to Reference (P2)
- **Use when:** a small object is shared and mutated (to value), or many copies
  must stay in sync (to reference).
- **Mechanics:** make the object immutable (frozen dataclass, `readonly`) and
  replace mutation with creation of a new value; or introduce a repository of
  shared instances.

### Extract Class (P2)
- **Use when:** a class or module holds two groups of data and behavior that change
  for different reasons; a subset of fields is always used together.
- **Mechanics:** create the new class (or module); give the old one a reference to
  it; Move Field for each field of the group, then Move Function for the behavior
  that uses them; decide whether to expose the new class or keep it internal.
- **Safety:** never on SQLAlchemy models (that is a schema change). In Python
  modules, this is usually Split Module into Package or Move Function.

### Inline Class (P2)
- **Use when:** a class no longer pulls its weight, or before redistributing its
  features differently.
- **Mechanics:** create forwarding functions on the absorbing class for each public
  member; move callers to them; Move Function and Move Field each member; delete
  the class.

### Hide Delegate (P2)
- **Use when:** callers navigate through one object to reach another
  (`settings.forecasting.rate`), coupling them to both.
- **Mechanics:** add a function on the server object that returns what callers
  need; replace the chains; remove the accessor if nothing else uses it.

### Remove Middle Man (P2)
- **Use when:** a module or class mostly forwards to another.
- **Mechanics:** expose the delegate; point callers at it directly; remove the
  forwarding functions, inlining them one at a time.

### Rename Field (P1 inside the code, never at the boundary)
- **Use when:** an internal field name misleads.
- **Mechanics:** rename in the structure and every reader and writer.
- **Safety:** model columns, JSON keys, schema fields and TypeScript types that
  mirror the API are interface. Renaming them is an API or schema change.

---

## Simplifying conditional logic

### Decompose Conditional (P2)
- **Use when:** a condition and its branches are hard to read.
- **Mechanics:** Extract Function for the condition, then for each branch.

### Consolidate Conditional Expression (P2)
- **Use when:** several checks lead to the same result.
- **Mechanics:** check none of the conditions has side effects; combine with
  `or`/`and` in the same order; Extract Function for the combined condition.

### Replace Nested Conditional with Guard Clauses (P2)
- **Use when:** special cases are buried in nested `if`/`else`.
- **Mechanics:** pick the outermost special case and return early for it; repeat.
- **Safety:** each guard must return exactly what the original nested branch
  returned, including `None` versus a default.

### Replace Conditional with Polymorphism (P3)
- **Use when:** the same switch on a type code repeats (Repeated Switches).
- **Mechanics (Python, dispatch table):**
  1. Characterization tests cover every case and the fallthrough.
  2. Extract each branch into a function with a uniform signature.
  3. Build a dict from the case value to the function.
  4. Replace the switch with a lookup, reproducing the old fallthrough exactly
     (default value, exception type and message).
  5. Point the other switches on the same cases at the table in later steps.
- **Mechanics (classes):** create a subclass or strategy per case and move each
  branch into an overriding method, when each case has several behaviors.
- **TypeScript:** a `Record<Union, Handler>` map; the type checker then demands a
  handler for each member.

### Introduce Special Case (P2)
- **Use when:** many callers check for the same special value (`None`, an empty
  list, a missing setting) and then do the same thing.
- **Mechanics:** create a special-case object or function returning the shared
  behavior; replace the checks one by one.

### Introduce Assertion (P3)
- **Use when:** an invariant the code relies on is implicit.
- **Warning:** a failing assertion changes behavior. Only assert what is already
  guaranteed by validation upstream, and prefer expressing it as a test. Never add
  assertions in request paths where the guarantee is not proven.

---

## Refactoring APIs (internal functions)

These apply to internal function signatures. The public interface (routes, JSON,
MCP tools) never changes in a refactoring.

### Separate Query from Modifier (P3)
- **Use when:** a function both returns a value and changes state.
- **Mechanics:** copy the function as a pure query; make the original call the
  query for its return value and keep only the modification; move callers that
  only need the value to the query.
- **Warning:** in Vipu, reads that write (budget archiving, override clearing) are
  deliberate. The combined effect per request must stay identical: same writes, in
  the same order, before the same reads.

### Parameterize Function (P2)
- **Use when:** functions differ only in a literal value.
- **Mechanics:** pick one; Change Function Declaration to add the parameter; replace
  the literal; switch callers of the others; remove them.

### Remove Flag Argument (P2)
- **Use when:** a boolean parameter selects between two behaviors.
- **Mechanics:** create an explicit function per value, each calling the original
  with the literal; move callers; then inline or Decompose Conditional inside.
- **Safety:** a flag that is part of the API (query parameter, MCP tool argument)
  stays; only the internal function changes.

### Preserve Whole Object (P2)
- **Use when:** callers pull several fields from one object to pass them separately.
- **Mechanics:** add a parameter for the object (Change Function Declaration,
  migration form); read fields from it inside; remove the separate parameters.
- **Safety:** it widens the dependency; prefer it when the callee uses most of the
  object (see ISP in `principles.md`).

### Introduce Parameter Object (P2)
- **Use when:** a group of parameters travels together (Data Clumps).
- **Mechanics:** create a dataclass or `TypedDict` (an interface in TypeScript);
  Change Function Declaration to add it; move each parameter into it one at a time;
  then look for behavior to Move Function onto it.

### Replace Parameter with Query (P2)
- **Use when:** the callee can compute a parameter itself from what it has.
- **Mechanics:** Extract Function for the computation in the callee; replace the
  parameter's uses; remove the parameter.
- **Safety:** not for values the callee would have to fetch from the database or
  the clock: that undoes dependency inversion.

### Replace Query with Parameter (P2)
- **Use when:** a function reads global state, the clock or the database, making it
  impure (DIP).
- **Mechanics:** Extract Variable for the query in the callee; Change Function
  Declaration to take it as a parameter; move the query to callers.
- **Vipu:** passing `today: date` as `deadline_calc.py` does.

### Remove Setting Method (P2)
- **Use when:** a field should not change after construction.
- **Mechanics:** set it in the constructor; remove the setter; freeze the dataclass.

### Replace Constructor with Factory Function (P2)
- **Use when:** construction needs a meaningful name or varies by case.
- **Mechanics:** create the factory; move callers; keep the constructor private by
  convention.

### Replace Error Code with Exception / Replace Exception with Precheck (P3)
- **Use when:** internal functions return sentinel values or use exceptions for
  expected conditions.
- **Warning:** status codes and error messages that reach clients are interface.
  The route or tool boundary must translate to exactly the same response.

---

## Inheritance (rare in Vipu)

### Pull Up Method / Pull Up Field (P2)
- Identical methods or fields in sibling subclasses move to the parent. Check the
  bodies really are identical first.

### Push Down Method / Push Down Field (P2)
- Behavior used by only one subclass moves into it.

### Extract Superclass (P2)
- Two classes with shared behavior get a common parent. Prefer composition unless
  the subtypes are substitutable (LSP).

### Collapse Hierarchy (P2)
- A parent and child that are no longer different merge.

### Replace Subclass with Delegate / Replace Superclass with Delegate (P2)
- Inheritance used for reuse rather than substitutability becomes composition:
  hold an instance and forward to it.

### Replace Type Code with Subclasses (P3)
- A type field driving behavior becomes subclasses. In Vipu prefer a dispatch
  table (see Replace Conditional with Polymorphism), since the type codes are
  database values.

---

## Vipu-specific refactorings

### Split Module into Package (P1)
- **Use when:** a module over about 500 lines holds several concepts
  (`app/fire.py`, `app/routes/networth.py`).
- **Mechanics:**
  1. Plan the submodules from the function clusters (see Large Module in
     `smells.md`), with dependencies pointing one way and no cycles.
  2. For `app/fire.py`: create `app/fire/` with `__init__.py`, move the module's
     contents unchanged into `app/fire/core.py` (or similar) and re-export every
     public name, every name tests import and every patch target from
     `__init__.py`. Run checks. Commit. (`git mv` keeps history readable.)
  3. Move Function, one cluster per step, from `core.py` into its own submodule,
     keeping the re-exports in `__init__.py`.
  4. Last, point importers at the submodules if that is clearer, and trim
     re-exports nothing uses.
- **Safety:** `patch("app.fire.date")`-style targets must be retargeted to the
  submodule that now looks the name up. For blueprints in `app/routes/`, the
  blueprint object, its name and its registration in `create_app()` stay
  unchanged; routes can be split across modules that all register on the same
  blueprint.
- **Proof:** P1 plus `git diff -M --color-moved=zebra` showing moved, not changed,
  lines.

### Extract React Component (P2)
- **Use when:** part of a component's markup is a coherent panel, row or control.
- **Mechanics:**
  1. Pin the parent's rendered output with a Vitest test if it has none (roles,
     labels, values, and the callbacks fired on interaction).
  2. Create the component in the same file first, with props for exactly the
     values and callbacks the fragment uses; move the JSX unchanged.
  3. Replace the fragment with the component. Run the tests and typecheck.
  4. Move it to its own file in a later step if it is reused or large.
- **Safety:** keep `key` props, conditional rendering and element order identical.
  Do not move hooks into the child unless their state truly belongs there (that is
  Colocate State, a separate step).

### Extract Custom Hook (P2)
- **Use when:** a component's state, effects and derived values form a unit, or
  several components repeat them.
- **Mechanics:** move the hook calls and the code that depends only on them into a
  `useSomething` function (in `frontend/hooks/` if shared), returning what the
  component uses; call it from the component.
- **Safety:** hook call order must stay the same and unconditional. React Query
  keys, `enabled` flags and invalidations stay identical.

### Colocate State / Lift State (P2)
- **Use when:** state lives higher than any component that uses it (colocate), or
  siblings need to share it (lift).
- **Mechanics:** move the `useState` and its setters to the lowest common owner;
  pass values and callbacks; remove the old props.
- **Safety:** moving state changes when it resets (a remounted child loses its
  state). Pin with a component test that exercises the interaction.
