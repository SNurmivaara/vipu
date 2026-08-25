# Plan: Forecast returns overhaul

Issue: [#98 — Forecast: fixed blended return and arithmetic rate conversions understate projected growth](https://github.com/SNurmivaara/vipu/issues/98)

Branch: `forecast-drift`

## 1. Findings

Answers to the issue's "to determine from the code" questions, reported before
changing behavior.

### 1.1 Compounding base: net worth, not gross assets

`backend/app/routes/forecasting.py:289` feeds `NetWorthSnapshot.net_worth`
(assets plus negative liabilities, `backend/app/models.py:547`) into every
compounding loop (`backend/app/fire.py:767`, `:253`, `:564`). Meanwhile
`weighted_return()` skips non-positive balances (`fire.py:185-186`). An
asset-weighted rate is applied to a net base, so loan balances implicitly grow
at the portfolio return. Confirmed defect. Direction: overstates growth for
leveraged users — opposite to the drift defect.

### 1.2 Liabilities: opaque negative balances

`NetWorthGroup.group_type == "liability"` carries amounts only
(`models.py:405-407`). No interest rate or payment schedule exists on any
model, schema, or settings field. `by_group` — the forecast's allocation
input — excludes liability groups entirely (`models.py:592-601`).

### 1.3 Auto badges: budget line items, not transactions

`monthly_savings` defaults to `monthly_net_income − monthly_expenses` from
recurring income/expense items (`backend/app/routes/budget.py:123-184`,
consumed at `routes/forecasting.py:301-310`). Loan payments net out of the
surplus only when entered as expense items. The model never amortizes loans,
so there is no double count today — but loan payments are then perpetual
expenses, which also inflates the FIRE target.

### 1.4 Rate conversions: half right

Annual→monthly is already geometric everywhere:
`(1 + annual)^(1/12) − 1` at `fire.py:246`, `:275`, `:541`, `:605`.
Nominal→real is subtraction in both the projection (`fire.py:603`, `:820`)
and the display (`frontend/components/networth/ForecastingPanel.tsx:430`).
Only the Fisher conversion is missing.

### 1.5 Already correct — preserve

- **FIRE target dynamics.** Dynamic in pension mode: `calc_fire_number_for_age`
  (`fire.py:467-516`) is re-evaluated every simulated month
  (`fire.py:563-582`). Constant only in simple mode, where a constant real
  target is correct.
- **TyEL accrual stops at candidate retirement age.**
  `calc_projected_monthly_pension` (`fire.py:307-322`), locked by
  `backend/tests/test_fire.py:181`.
- **Pension treated as real.** Never deflated anywhere in the pipeline.
  Implicit today; make it an explicit code comment.
- **Takuueläke binding flag.** `max()` floor (`fire.py:493-498`) with UI
  banner when it binds (`guarantee_active`, `fire.py:922`;
  `ForecastingPanel.tsx:474-487`). The taper is out of scope; the flag
  satisfies the issue's requirement.

## 2. Design

### 2.1 `PortfolioState` simulation engine

Replace the scalar `nw` loops with one shared state class in
`backend/app/fire.py`, used by `calc_years_to_fire`, `calc_coast_fire_age`,
`calc_pension_aware_years_to_fire`, and `generate_projections`.

State:

- Per-asset-group balances from the latest snapshot.
- Per-liability-group balances (positive magnitudes) with rate and monthly
  payment from settings.
- Cumulative inflation factor (for deflating nominal liability balances into
  the real-terms projection space).

Monthly step:

1. Each asset group compounds at its own real monthly rate:
   `ρᵢ = (1 + rᵢ)/(1 + π) − 1` (Fisher), then `(1 + ρᵢ)^(1/12) − 1`.
2. The monthly contribution is added to the routed group. When
   `contribution_group` is unset, distribute pro-rata across current asset
   balances (reproduces current behavior).
3. Each liability amortizes nominally:
   `L ← L · (1 + (1 + i)^(1/12) − 1) − payment`, floored at zero. Real balance
   = nominal balance ÷ cumulative inflation factor.
4. On payoff (balance hits zero), the liability's monthly payment joins the
   contribution stream from the next month. Consistent with the budget-derived
   surplus, which already nets the payment out as an expense.

Derived values:

- `net_worth = Σ asset balances − Σ real liability balances`
- `swr_base = Σ non-excluded asset balances − Σ real liability balances`
- `blended_return_pct` = value-weighted nominal return of the current mix
  (diagnostic only; never used to compound).

Weight drift falls out of the per-group compounding — no blended rate in any
loop.

### 2.2 Fisher conversion

- Projection: per-group real rates as above. Remove
  `annual_return_pct - inflation_pct` at `fire.py:603` and `:820`.
- Display: backend computes `real_return_pct` (Fisher, at current mix) and
  exposes it in the `derived` block. The frontend stops computing
  `weighted − inflation` (`ForecastingPanel.tsx:430`) and renders the derived
  figure with an "at current mix" sublabel — a single real-return figure is
  a property of the mix at an instant, not of the plan.

### 2.3 Coast FIRE closed form

Coast check at month `m` with target at horizon `N` years:

```
Σᵢ bᵢ(m) · (1 + ρᵢ)^(N − m/12)  ≥  fire_number_at_target
```

This is the `Σ wᵢ(1+rᵢ)ⁿ` growth factor from the issue — strictly greater
than `(1 + r̄)ⁿ` by Jensen. Applies to:

- `calc_coast_fire_number`: coast number = `fire_number / Σ wᵢ(1+ρᵢ)ᴺ`
  with current-mix weights.
- `calc_coast_fire_age`: per-month check inside the simulation, using the
  simulated (drifted) mix at that month.
- Coast trajectory in `generate_projections`: per-group zero-contribution
  balances, each compounding at its own rate.

The scalar formula remains only for the degenerate single-group path.

### 2.4 Liability modeling

- Terms live in `ForecastingSettings.liability_terms` (JSON):
  `{group_name: {"rate_pct": x, "monthly_payment": y}}` — group-name keyed,
  mirroring `group_return_rates`. Group-level granularity; one group per loan
  when rates differ. Category-level terms are a follow-up.
- Liability groups with no terms configured: balance held constant in nominal
  terms (deflated in real terms). No invented amortization.
- **Negative amortization warning**: when `monthly_payment` < first-month
  interest, append a structured warning to `FireResult.warnings`
  (`{"code": "negative_amortization", "group": name}`). The simulation still
  terminates: solve loops keep their existing 100-year caps.
- Assumption to document in UI helper text: the configured monthly payment
  must correspond to a budget expense item, otherwise the surplus is
  overstated.
- Known limitation: the FIRE target (`annual_expenses`) still includes loan
  payments after payoff. Workaround exists today: expense items support
  `end_date`. Not solved in this change.

### 2.5 SWR exclusion flag

- `ForecastingSettings.swr_excluded_groups` (JSON list of group names).
- Excluded groups (owner-occupied home, ASO) stay in net worth and keep
  compounding, but FIRE and coast comparisons use `swr_base`.
- Drawdown (pension mode) withdraws pro-rata from non-excluded groups only.
- `ProjectionPoint` gains `swr_base`; the frontend surfaces it when it
  differs from net worth.

### 2.6 Contribution routing

- `ForecastingSettings.contribution_group` (nullable text). Null = pro-rata
  (current behavior, preserves the degenerate case).
- Routed contributions change the mix over time; drift handles the rest.

### 2.7 Pension mode integration

- `generate_pension_scenarios`, `calc_fire_number_for_age`, and the guarantee
  logic are unchanged — they operate on expenses and pension flows, not on
  the compounding base.
- Drawdown: at FIRE age, clone the `PortfolioState` three times
  (early/normal/late). Each month: grow groups, withdraw
  `monthly_expenses − pension` (once pension has started) pro-rata from
  non-excluded groups.
- `calc_pension_aware_years_to_fire` keeps its monthly re-evaluation of
  `fire_number_at_age`, comparing against `swr_base`.

## 3. Schema and API changes

### 3.1 Migration `012_forecast_returns`

```sql
ALTER TABLE forecasting_settings
    ADD COLUMN IF NOT EXISTS contribution_group TEXT;
ALTER TABLE forecasting_settings
    ADD COLUMN IF NOT EXISTS swr_excluded_groups JSONB NOT NULL DEFAULT '[]';
ALTER TABLE forecasting_settings
    ADD COLUMN IF NOT EXISTS liability_terms JSONB NOT NULL DEFAULT '{}';
```

Pattern: `backend/app/migrations.py` MIGRATIONS list. Model fields plus
`to_dict` in `backend/app/models.py:224-303`. PUT validation in
`routes/forecasting.py:147-226` (rate 0–30 %, payment ≥ 0, group names
strings; unknown group names accepted and ignored, matching
`group_return_rates` behavior).

### 3.2 `POST /api/forecasting/calculate` — back-compatible

- Existing scalar inputs keep working: scalar `annual_return_pct` becomes one
  synthetic asset group holding `current_net_worth`, no liabilities. Output
  matches the new engine's degenerate path.
- Optional new fields: `asset_groups` (name → balance), `group_return_rates`,
  `contribution_group`, `liabilities` (name → {balance, rate_pct,
  monthly_payment}), `swr_excluded_groups`.

### 3.3 `GET /api/forecasting/projection`

- Route derives asset groups from the snapshot as today, and additionally
  liability balances by group (new helper alongside `models.py:588-601`,
  which currently drops liability groups).
- `derived` block additions: `real_return_pct` (Fisher, current mix),
  `liability_by_group`, `contribution_group`, `swr_excluded_groups`,
  `liability_terms`.
- `FireResult` additions: `warnings` list; `ProjectionPoint` additions:
  `blended_return_pct`, `swr_base`.

## 4. Tests

`backend/tests/test_fire.py`, mapped 1:1 to the acceptance criteria:

1. **Drift monotonicity**: two groups at 8 % and 1 % nominal, zero
   contributions → `blended_return_pct` at year 20 strictly greater than at
   year 0.
2. **Routing**: contributions routed entirely to the above-average group →
   strictly higher terminal wealth than pro-rata on identical inputs.
3. **Fisher**: 8 % nominal at 3 % inflation → real = 0.04854 (not 0.05);
   `derived.real_return_pct` equals the rate the projection compounds at.
4. **Monthly compounding**: twelve monthly steps reproduce the annual rate to
   floating-point tolerance.
5. **Coast closed form**: matches a zero-contribution simulation to the same
   target age within tolerance.
6. **Pension**: accrual stops at candidate retirement age 45 (existing test,
   keep); assert no deflation of pension figures anywhere in the pipeline.
7. **Degenerate parity**: one asset group, no liabilities → per-group engine
   reproduces the scalar path exactly. Note: the Fisher fix intentionally
   shifts today's golden numbers; parity is between the new engine and the
   new scalar path, not against pre-change binaries.
8. **Negative amortization**: liability payment below interest → structured
   warning, no growing balance, solve terminates.

Regressions to preserve: `test_fire_number_now_ignores_target_retirement_age`
(`test_fire.py:490`), weighted-return 5.5 % golden
(`test_fire.py:704`). Golden values that embed the subtraction-based real
return get updated with a comment citing the Fisher fix.

## 5. Frontend

`frontend/components/networth/ForecastingPanel.tsx` plus types/api/hooks:

- Real-return card reads `derived.real_return_pct`; sublabel
  "Fisher, at current mix". Remove the local subtraction (`:430`).
- Group-rates section: contribution-destination selector (radio per asset
  group plus "Pro-rata" default); SWR-exclude toggle per asset group;
  rate + monthly-payment inputs for liability groups.
- Negative-amortization banner, following the guarantee banner pattern
  (`:474-487`).
- Plumbing: `frontend/types/index.ts` (`ForecastingSettings`,
  `ForecastingSettingsAPI`, `FireResultAPI`, `ForecastingProjectionAPI`),
  `frontend/lib/api.ts:431-480`, snake→camel mapping in
  `frontend/hooks/useForecastingProjection.ts:94-132`, settings mutation in
  `frontend/hooks/useForecastingSettings.ts`.

## 6. Commit sequence

1. Fisher conversion everywhere + rate-conversion test locks (small, isolated
   golden change).
2. `PortfolioState` engine: per-group drift, coast closed form, degenerate
   parity tests, `blended_return_pct` diagnostic.
3. Contribution routing: migration 012 (routing column), settings API, engine,
   UI selector.
4. Liability terms + amortization + negative-amortization warning (settings
   JSON, engine, UI inputs, banner).
5. SWR exclusion flag (settings JSON, `swr_base` in engine and points, UI
   toggle).
6. Frontend polish: real-return display, warnings, projection tooltip fields.

Each commit passes `./test.sh` (black, ruff, mypy, pytest; frontend lint, tsc,
build).

## 7. Out of scope — follow-up issues

- Realized-return display. No such figure exists in the app today. Constraint
  for any future addition: asset CAGR with contributions excluded, never
  net-worth CAGR.
- Takuueläke taper. Keep the `max()` approximation and the existing binding
  flag.
- Explicit TyEL indexation (palkkakerroin / TyEL index). Keep the
  implicit-real treatment; add a code comment making it explicit.
- Category-level liability terms.
- Reducing the FIRE target after loan payoff (expense `end_date` is the
  workaround).

## 8. Verification

- `./test.sh` from the repo root.
- End-to-end: run the app locally via the `verify` skill
  (`.claude/skills/verify/SKILL.md`) and check the forecast panel against the
  acceptance criteria with a two-group portfolio and one amortizing liability.
