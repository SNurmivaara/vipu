# Smells

A smell is a surface sign that structure is getting in the way. It is evidence to
investigate, not a verdict. Each entry gives what it looks like in Vipu, how to
detect it, and the refactorings in `catalog.md` that usually cure it. A finding
in a plan cites the smell, a `file:line` and the evidence.

Commands assume the package directory (`backend/`, `mcp-server/` or `frontend/`).

## Naming and readability

### Mysterious Name
- **Looks like:** `data`, `res`, `tmp`, `x2`, `calc()`, `handle()`, `process_items()`;
  a name that contradicts the domain (`total` that is a monthly amount, `balance`
  that is a magnitude).
- **Detect:** read the inventory of public names; any name you had to read the
  body to understand.
- **Cure:** Change Function Declaration (rename), Rename Variable, Rename Field.
  A name that will not come is a sign the unit does more than one thing: Extract
  Function first.

### Comments
- **Looks like:** comments that label sections of a long function ("# Calculate
  totals"), or explain what an expression does.
- **Detect:** section comments inside function bodies.
- **Cure:** Extract Function named after the comment, Extract Variable,
  Introduce Assertion (only for invariants already guaranteed). Keep comments that
  explain why; that is the repository's style.

## Size and complexity

### Long Function
- **Looks like:** a route handler or calculation over 40 lines; a React component
  whose body mixes state, effects, derived values and markup for several panels.
- **Detect:** `ruff check --select C901,PLR0912,PLR0915`; eslint
  `max-lines-per-function` and `complexity`.
- **Cure:** Extract Function (most often), Replace Temp with Query, Introduce
  Parameter Object, Decompose Conditional, Split Loop, Split Phase, Replace
  Function with Command for very long calculations with many locals. Components:
  Extract React Component, Extract Custom Hook.

### Large Module (Large Class)
- **Looks like:** `app/fire.py`, `routes/networth.py`, `ForecastingPanel.tsx`:
  hundreds of lines covering several concepts with clusters of functions that only
  call each other.
- **Detect:** over 500 lines (`git grep -c '' -- <path>`); group functions by which names they call and which
  data they touch; clusters with few cross-links are separate modules.
- **Cure:** Split Module into Package, Move Function, Extract Class, Extract React
  Component, Extract Custom Hook.

### Long Parameter List
- **Looks like:** over five parameters, often the same group passed from one
  function to the next (`current_age`, `retirement_age`, `life_expectancy`, ...).
- **Detect:** ruff `PLR0913`.
- **Cure:** Introduce Parameter Object, Preserve Whole Object, Replace Parameter
  with Query, Remove Flag Argument, Combine Functions into Class.

### Complex Conditional
- **Looks like:** nested `if` three levels deep, long boolean expressions, early
  special cases buried at the end.
- **Detect:** ruff `C901`, `PLR0912`, `PLR0911`; indentation depth.
- **Cure:** Decompose Conditional, Consolidate Conditional Expression, Replace
  Nested Conditional with Guard Clauses, Introduce Special Case.

### Loops
- **Looks like:** a `for` loop that filters, transforms and accumulates several
  results at once.
- **Detect:** loops that assign to more than one accumulator.
- **Cure:** Split Loop, then Replace Loop with Pipeline (comprehension, `sum`,
  `map`/`filter` in TypeScript). Keep loops where order of side effects matters.

## Duplication and change patterns

### Duplicated Code
- **Looks like:** the same calculation in a route and in `summary.py`; the same
  fetch-and-transform in two components; near-identical test setup.
- **Detect:** search for distinctive expressions with `git grep -n`; compare
  functions with similar names across modules.
- **Cure:** Extract Function then Move Function to a shared module, Slide
  Statements to line up near-duplicates first, Parameterize Function when they
  differ only in a value, Pull Up Method for shared subclass code. Do not merge
  code that encodes different rules (for example the different rounding policies).

### Repeated Switches
- **Looks like:** branching on `frequency_unit` in `deadline_calc.py`,
  `routes/budget.py` and `summary.py`; switching on `GoalType` or group type in
  several components.
- **Detect:** `git grep -n -E '== "(days|weeks|months|years)"'`, and the same for
  other string enums.
- **Cure:** Replace Conditional with Polymorphism, usually as a dispatch table in
  Python and a `Record<Union, ...>` map in TypeScript; Combine Functions into
  Class when each case has several behaviors.

### Divergent Change
- **Looks like:** one module is edited for unrelated reasons (a new API field and
  a new projection rule both land in the same file).
- **Detect:** `git log --format=%s -- <file>` shows unrelated themes.
- **Cure:** Split Phase, Move Function, Extract Class, Split Module into Package.

### Shotgun Surgery
- **Looks like:** one change (a new frequency unit, a new account type) needs
  small edits in many files.
- **Detect:** `git log --name-only` for a past feature touched many files for one
  concept.
- **Cure:** Move Function and Move Field to gather the concept, Combine Functions
  into Class or Transform, Inline Function or Inline Class where the scattering
  came from over-splitting.

## Data

### Data Clumps
- **Looks like:** the same three or four values travel together (start and end of
  a period; age, retirement age and life expectancy; amount, frequency value and
  frequency unit).
- **Detect:** repeated parameter groups and repeated dict keys.
- **Cure:** Introduce Parameter Object, Extract Class, then Move Function onto it
  when behavior follows.

### Primitive Obsession
- **Looks like:** strings for units and types compared everywhere; amounts and
  percentages as bare numbers whose unit lives only in the name; ISO date strings
  parsed in several places in the frontend.
- **Detect:** string literal comparisons; parsing of the same string format in
  several places.
- **Cure:** Replace Primitive with Object, Replace Type Code with Subclasses (rare
  here), or a `Literal`/union type plus a dispatch table. Keep the JSON
  representation unchanged at the API boundary.

### Untyped Shapes
- **Looks like:** `dict[str, Any]` built in one function and read by key in
  another; `Record<string, string | number | boolean>` passed around the frontend.
- **Detect:** mypy `Any` in signatures; dict literals returned from functions that
  are not serializers.
- **Cure:** Encapsulate Record, as a `TypedDict` (no runtime change) or dataclass
  (convert back to the same dict at the boundary); a TypeScript interface.

### Mutable Data and Global Data
- **Looks like:** functions mutating a dict or list passed in; module-level
  mutable state; React state mutated in place.
- **Detect:** assignments to parameter attributes or keys; module-level lists or
  dicts that change after import.
- **Cure:** Encapsulate Variable, Separate Query from Modifier, Split Variable,
  Change Reference to Value, Replace Derived Variable with Query.

### Temporary Field
- **Looks like:** an attribute or dict key that is only meaningful in some cases.
- **Cure:** Extract Class, Introduce Special Case, Move Function.

### Data Class
- **Looks like:** a structure with fields and no behavior, while functions elsewhere
  compute everything from its fields. SQLAlchemy models with `to_dict` are fine;
  the smell is the calculation that lives far from its data.
- **Cure:** Move Function onto the data, Encapsulate Record. Often acceptable as
  is: a plain dataclass passed into pure functions is the intended DIP shape.

## Coupling

### Feature Envy
- **Looks like:** a function that reads many fields of another module's object and
  few of its own; a component that digs through a settings object to compute what
  another component shows.
- **Cure:** Move Function, Extract Function then Move Function.

### Insider Trading
- **Looks like:** modules importing each other's private helpers (`_name`); tests
  reaching into internals that the public functions already cover.
- **Detect:** `git grep -n -E "import _[a-z]"`, `from app.<module> import _`.
- **Cure:** Move Function, Hide Delegate, Extract Class for the shared part.

### Message Chains and Middle Man
- **Looks like:** `a.b().c().d` in callers (chains), or a module whose functions
  only forward to another (middle man).
- **Cure:** Hide Delegate for chains; Remove Middle Man and Inline Function for
  forwarders.

### Alternative Classes with Different Interfaces
- **Looks like:** two helpers or components that do the same job with different
  names and parameter orders.
- **Cure:** Change Function Declaration to align, then Extract Superclass or merge.

### Refused Bequest
- **Looks like:** a subclass that ignores or overrides most of what it inherits.
- **Cure:** Push Down Method or Field, Replace Subclass with Delegate, Replace
  Superclass with Delegate.

## Speculative and dead structure

### Speculative Generality
- **Looks like:** parameters always passed the same value, hooks or abstract base
  classes with one implementation, options nobody sets.
- **Detect:** `git grep -n` the call sites of each parameter and option.
- **Cure:** Inline Function, Inline Class, Collapse Hierarchy, Change Function
  Declaration to remove the parameter, Remove Dead Code.

### Lazy Element
- **Looks like:** a function, module or component that adds a name but no meaning.
- **Cure:** Inline Function, Inline Class, Collapse Hierarchy.

### Dead Code
- **Looks like:** unused functions, unreachable branches, commented-out code,
  exports nothing imports.
- **Detect:** `git grep -n <name>` across the repository including tests and the
  MCP server; `ruff check --select F401,F841`; for TypeScript, an export with no
  importer.
- **Cure:** Remove Dead Code.

## Frontend-specific

### God Component
- **Looks like:** a component over 250 lines with many `useState` hooks, several
  effects and markup for multiple panels (`ForecastingPanel.tsx`,
  `CategoryManager.tsx`, `SnapshotForm.tsx`).
- **Cure:** Extract React Component per panel, Extract Custom Hook for state and
  effects, Colocate State.

### Prop Drilling
- **Looks like:** props passed through two or more components that do not use them.
- **Cure:** Colocate State, Extract Custom Hook that the leaf calls directly (React
  Query hooks already share cached data), composition via `children`.

### Effect for Derived State
- **Looks like:** `useEffect` that sets state computed from props or other state.
- **Cure:** Replace Derived Variable with Query (compute during render, `useMemo`
  if it is expensive). This changes render timing: pin the rendered output with a
  Vitest component test first and treat it as higher risk.

### Data Access Outside Hooks
- **Looks like:** components calling `lib/api.ts` or `axios` directly, or
  duplicating query keys and invalidation.
- **Cure:** Extract Custom Hook into `frontend/hooks/`, Move Function into
  `lib/api.ts`. Keep query keys and invalidation identical.

## Vipu-specific: flag, do not fix

These look like smells but changing them changes behavior. Record them under
"Suspected bugs" or follow-ups in the plan, never as refactoring steps:

- Decimal and float mixed in one calculation, or a different rounding mode than
  a neighboring function.
- A read endpoint or read tool that writes.
- An inconsistent sign convention between two functions.
- A response field that is computed differently in two routes.
