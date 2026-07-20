"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchForecastingProjection } from "@/lib/api";
import { ForecastingProjectionAPI, FirePensionResultAPI } from "@/types";

// React Query key — exported so settings updates can invalidate the projection.
export const FORECASTING_PROJECTION_KEY = ["forecasting-projection"] as const;

// camelCase result types consumed by the component
export interface ProjectionPoint {
  age: number;
  year: number;
  month: number;
  netWorth: number;
  coastNetWorth: number;
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
  pensionMonthlySalary: number;
  pensionActive: boolean;
  byGroup: Record<string, number>;
  groupReturnRates: Record<string, number>;
}

export interface ForecastingProjection {
  fireNumber: number;
  coastFireNumber: number;
  coastFireReached: boolean;
  yearsToFire: number | null;
  fireAge: number | null;
  coastFireAge: number | null;
  onTrack: boolean;
  portfolioDepletedAge: number | null;
  projections: ProjectionPoint[];
  pension?: PensionResult;
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
      ...(p.fire_number_at_age != null && { fireNumberAtAge: p.fire_number_at_age }),
      ...(p.coast_fire_number_at_age != null && { coastFireNumberAtAge: p.coast_fire_number_at_age }),
      ...(p.net_worth_early != null && { netWorthEarly: p.net_worth_early }),
      ...(p.net_worth_normal != null && { netWorthNormal: p.net_worth_normal }),
      ...(p.net_worth_late != null && { netWorthLate: p.net_worth_late }),
    })),
    pension: api.pension ? fromApiPension(api.pension) : undefined,
    derived: {
      currentNetWorth: api.derived.current_net_worth,
      monthlySavings: api.derived.monthly_savings,
      annualExpenses: api.derived.annual_expenses,
      weightedReturnPct: api.derived.weighted_return_pct,
      pensionMonthlySalary: api.derived.pension_monthly_salary,
      pensionActive: api.derived.pension_active,
      byGroup: api.derived.by_group,
      groupReturnRates: api.derived.group_return_rates,
    },
  };
}

// Empty result for loading/error states.
const DEFAULT_RESULT: ForecastingProjection = {
  fireNumber: 0,
  coastFireNumber: 0,
  coastFireReached: false,
  yearsToFire: null,
  fireAge: null,
  coastFireAge: null,
  onTrack: false,
  portfolioDepletedAge: null,
  projections: [],
  pension: undefined,
  derived: {
    currentNetWorth: 0,
    monthlySavings: 0,
    annualExpenses: 0,
    weightedReturnPct: 7,
    pensionMonthlySalary: 0,
    pensionActive: false,
    byGroup: {},
    groupReturnRates: {},
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
