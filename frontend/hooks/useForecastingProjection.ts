"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchForecastingProjection } from "@/lib/api";
import {
  ForecastingProjectionAPI,
  FirePensionResultAPI,
  LiabilityTerm,
  ResolvedLiabilityTerm,
} from "@/types";

// React Query key — exported so settings updates can invalidate the projection.
export const FORECASTING_PROJECTION_KEY = ["forecasting-projection"] as const;

// camelCase result types consumed by the component
export interface ProjectionPoint {
  age: number;
  year: number;
  month: number;
  netWorth: number;
  coastNetWorth: number;
  /** Nominal return implied by the mix at this point; rises as the mix drifts */
  blendedReturnPct?: number;
  /** Capital backing the withdrawal, when groups are excluded from it */
  swrBase?: number;
  // Age-specific FIRE numbers (present when pension mode is active)
  fireNumberAtAge?: number;
  coastFireNumberAtAge?: number;
  // Pension drawdown projections (present when pension mode is active)
  netWorthEarly?: number;
  netWorthNormal?: number;
  netWorthLate?: number;
}

export interface PensionScenario {
  label: "early" | "normal" | "late";
  pensionStartAge: number;
  monthlyPension: number;
  annualPension: number;
  pensionFireNumber: number;
}

export interface PensionResult {
  projectedMonthlyPension: number;
  scenarios: [PensionScenario, PensionScenario, PensionScenario];
  pensionCoastFireNumber: number;
  guaranteeActive: boolean;
  guaranteeAmount: number;
  crossoverAge: number | null;
}

// FIRE inputs the backend derived from persisted settings + snapshots + budget
export interface DerivedInputs {
  currentNetWorth: number;
  monthlySavings: number;
  annualExpenses: number;
  weightedReturnPct: number;
  /**
   * Real return at the current mix, Fisher-converted by the backend so the
   * displayed figure is the one the projection compounds at.
   */
  realReturnPct: number;
  pensionMonthlySalary: number;
  pensionActive: boolean;
  byGroup: Record<string, number>;
  groupReturnRates: Record<string, number>;
  /** Where monthly savings land; null spreads them across the mix */
  contributionGroup: string | null;
  grossAssets: number;
  /** Amounts owed per liability group name, as positive magnitudes */
  liabilitiesByGroup: Record<string, number>;
  /** The same amounts per loan, with the group each sits under */
  liabilitiesByCategory: Record<string, { amount: number; group: string }>;
  liabilityTerms: Record<string, LiabilityTerm>;
  /** What the stated terms work out to: derived payment, derived payoff date */
  liabilityTermsResolved: Record<string, ResolvedLiabilityTerm>;
  /** Share of a withdrawal lost to capital gains tax, as a percentage */
  withdrawalTaxDragPct: number;
  /** Groups kept in net worth but held out of the withdrawal base */
  swrExcludedGroups: string[];
  /** Capital the withdrawal rate applies to, after exclusions and debt */
  swrBase: number;
  /** monthlySavings is a manual override, not the budget's monthly surplus */
  monthlySavingsIsOverride: boolean;
  /** annualExpenses is a manual override, not monthly expenses x 12 */
  annualExpensesIsOverride: boolean;
  targetRetirementAge: number;
}

export interface ForecastingProjection {
  fireNumber: number;
  // FIRE number if you retired now (at current age). Equals fireNumber in
  // non-pension mode; in pension mode it ignores the target retirement age.
  fireNumberNow: number;
  coastFireNumber: number;
  coastFireReached: boolean;
  yearsToFire: number | null;
  fireAge: number | null;
  coastFireAge: number | null;
  onTrack: boolean;
  portfolioDepletedAge: number | null;
  projections: ProjectionPoint[];
  pension?: PensionResult;
  /** Conditions the projection cannot model away, e.g. negative amortization */
  warnings: { code: string; name: string; group: string }[];
  derived: DerivedInputs;
}

function fromApiPension(api: FirePensionResultAPI): PensionResult {
  return {
    projectedMonthlyPension: api.projected_monthly_pension,
    scenarios: api.scenarios.map((s) => ({
      label: s.label,
      pensionStartAge: s.pension_start_age,
      monthlyPension: s.monthly_pension,
      annualPension: s.annual_pension,
      pensionFireNumber: s.pension_fire_number,
    })) as [PensionScenario, PensionScenario, PensionScenario],
    pensionCoastFireNumber: api.pension_coast_fire_number,
    guaranteeActive: api.guarantee_active,
    guaranteeAmount: api.guarantee_amount,
    crossoverAge: api.crossover_age,
  };
}

function fromApiResult(api: ForecastingProjectionAPI): ForecastingProjection {
  return {
    fireNumber: api.fire_number,
    fireNumberNow: api.fire_number_now,
    coastFireNumber: api.coast_fire_number,
    coastFireReached: api.coast_fire_reached,
    yearsToFire: api.years_to_fire,
    fireAge: api.fire_age,
    coastFireAge: api.coast_fire_age,
    onTrack: api.on_track,
    portfolioDepletedAge: api.portfolio_depleted_age,
    projections: api.projections.map((p) => ({
      age: p.age,
      year: p.year,
      month: p.month,
      netWorth: p.net_worth,
      coastNetWorth: p.coast_net_worth,
      ...(p.blended_return_pct != null && { blendedReturnPct: p.blended_return_pct }),
      ...(p.swr_base != null && { swrBase: p.swr_base }),
      ...(p.fire_number_at_age != null && { fireNumberAtAge: p.fire_number_at_age }),
      ...(p.coast_fire_number_at_age != null && { coastFireNumberAtAge: p.coast_fire_number_at_age }),
      ...(p.net_worth_early != null && { netWorthEarly: p.net_worth_early }),
      ...(p.net_worth_normal != null && { netWorthNormal: p.net_worth_normal }),
      ...(p.net_worth_late != null && { netWorthLate: p.net_worth_late }),
    })),
    pension: api.pension ? fromApiPension(api.pension) : undefined,
    warnings: api.warnings ?? [],
    derived: {
      currentNetWorth: api.derived.current_net_worth,
      monthlySavings: api.derived.monthly_savings,
      annualExpenses: api.derived.annual_expenses,
      weightedReturnPct: api.derived.weighted_return_pct,
      realReturnPct: api.derived.real_return_pct,
      pensionMonthlySalary: api.derived.pension_monthly_salary,
      pensionActive: api.derived.pension_active,
      byGroup: api.derived.by_group,
      groupReturnRates: api.derived.group_return_rates,
      contributionGroup: api.derived.contribution_group,
      grossAssets: api.derived.gross_assets,
      liabilitiesByGroup: api.derived.liabilities_by_group ?? {},
      liabilitiesByCategory: api.derived.liabilities_by_category ?? {},
      liabilityTerms: api.derived.liability_terms ?? {},
      liabilityTermsResolved: api.derived.liability_terms_resolved ?? {},
      withdrawalTaxDragPct: api.derived.withdrawal_tax_drag_pct ?? 0,
      swrExcludedGroups: api.derived.swr_excluded_groups ?? [],
      swrBase: api.derived.swr_base,
      monthlySavingsIsOverride: api.derived.monthly_savings_is_override,
      annualExpensesIsOverride: api.derived.annual_expenses_is_override,
      targetRetirementAge: api.derived.target_retirement_age,
    },
  };
}

// Empty result for loading/error states.
const DEFAULT_RESULT: ForecastingProjection = {
  fireNumber: 0,
  fireNumberNow: 0,
  coastFireNumber: 0,
  coastFireReached: false,
  yearsToFire: null,
  fireAge: null,
  coastFireAge: null,
  onTrack: false,
  portfolioDepletedAge: null,
  projections: [],
  pension: undefined,
  warnings: [],
  derived: {
    currentNetWorth: 0,
    monthlySavings: 0,
    annualExpenses: 0,
    weightedReturnPct: 7,
    realReturnPct: 0,
    pensionMonthlySalary: 0,
    pensionActive: false,
    byGroup: {},
    groupReturnRates: {},
    contributionGroup: null,
    grossAssets: 0,
    liabilitiesByGroup: {},
    liabilitiesByCategory: {},
    liabilityTerms: {},
    liabilityTermsResolved: {},
    withdrawalTaxDragPct: 0,
    swrExcludedGroups: [],
    swrBase: 0,
    monthlySavingsIsOverride: false,
    annualExpensesIsOverride: false,
    targetRetirementAge: 0,
  },
};

/**
 * Fetch the FIRE projection computed entirely on the backend from persisted
 * settings, the latest net worth snapshot and the current budget. The frontend
 * no longer assembles inputs — it just displays the result.
 */
export function useForecastingProjection() {
  const query = useQuery({
    queryKey: FORECASTING_PROJECTION_KEY,
    queryFn: async () => fromApiResult(await fetchForecastingProjection()),
    // Deterministic given persisted state; invalidated when settings change.
    staleTime: Infinity,
    gcTime: 5 * 60 * 1000,
    placeholderData: (previousData) => previousData,
  });

  return {
    result: query.data ?? DEFAULT_RESULT,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
  };
}
