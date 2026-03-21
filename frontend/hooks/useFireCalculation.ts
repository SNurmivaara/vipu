"use client";

import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { calculateFire } from "@/lib/api";
import {
  FireCalculateInput,
  FireResultAPI,
  FirePensionResultAPI,
} from "@/types";

// Internal types that match the component's expectations (camelCase)
export interface FireResult {
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
}

export interface ProjectionPoint {
  age: number;
  year: number;
  month: number;
  netWorth: number;
  coastNetWorth: number;
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

// Input type for the hook (camelCase, matching component usage)
export interface FireInputs {
  currentNetWorth: number;
  monthlyContribution: number;
  annualExpenses: number;
  annualReturnPct: number;
  inflationPct: number;
  currentAge: number;
  targetRetirementAge: number;
  safeWithdrawalRate: number;
  pensionAccruedMonthly?: number;
  pensionMonthlySalary?: number;
  pensionAccrualRate?: number;
  pensionFullAge?: number;
  pensionGuaranteeEnabled?: boolean;
  pensionGuaranteeAmount?: number;
  lifeExpectancy?: number;
}

// Convert camelCase input to snake_case for API
function toApiInput(inputs: FireInputs): FireCalculateInput {
  return {
    current_net_worth: inputs.currentNetWorth,
    monthly_contribution: inputs.monthlyContribution,
    annual_expenses: inputs.annualExpenses,
    annual_return_pct: inputs.annualReturnPct,
    inflation_pct: inputs.inflationPct,
    current_age: inputs.currentAge,
    target_retirement_age: inputs.targetRetirementAge,
    safe_withdrawal_rate: inputs.safeWithdrawalRate,
    pension_accrued_monthly: inputs.pensionAccruedMonthly ?? null,
    pension_monthly_salary: inputs.pensionMonthlySalary ?? null,
    pension_accrual_rate: inputs.pensionAccrualRate,
    pension_full_age: inputs.pensionFullAge,
    pension_guarantee_enabled: inputs.pensionGuaranteeEnabled,
    pension_guarantee_amount: inputs.pensionGuaranteeAmount,
    life_expectancy: inputs.lifeExpectancy,
  };
}

// Convert snake_case API response to camelCase for component
function fromApiResult(api: FireResultAPI): FireResult {
  const pension = api.pension ? fromApiPension(api.pension) : undefined;

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
      ...(p.net_worth_early != null && { netWorthEarly: p.net_worth_early }),
      ...(p.net_worth_normal != null && { netWorthNormal: p.net_worth_normal }),
      ...(p.net_worth_late != null && { netWorthLate: p.net_worth_late }),
    })),
    pension,
  };
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

// Default fallback result for loading/error states
const DEFAULT_RESULT: FireResult = {
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
};

interface UseFireCalculationOptions {
  enabled?: boolean;
  debounceMs?: number;
}

// Shorter debounce for more responsive feel
const DEFAULT_DEBOUNCE_MS = 200;

export function useFireCalculation(
  inputs: FireInputs,
  options: UseFireCalculationOptions = {}
) {
  const { enabled = true, debounceMs = DEFAULT_DEBOUNCE_MS } = options;

  // Serialize inputs for stable comparison
  const inputsKey = JSON.stringify(inputs);

  // Debounce the inputs using idiomatic useEffect pattern
  const [debouncedInputsKey, setDebouncedInputsKey] = useState(inputsKey);

  useEffect(() => {
    const timeout = setTimeout(() => {
      setDebouncedInputsKey(inputsKey);
    }, debounceMs);

    return () => clearTimeout(timeout);
  }, [inputsKey, debounceMs]);

  // Parse the debounced inputs
  const debouncedInputs: FireInputs = JSON.parse(debouncedInputsKey);

  const query = useQuery({
    queryKey: ["fire-calculation", debouncedInputsKey],
    queryFn: async () => {
      const apiInput = toApiInput(debouncedInputs);
      const apiResult = await calculateFire(apiInput);
      return fromApiResult(apiResult);
    },
    enabled,
    // FIRE calculations are deterministic - same inputs always produce same outputs
    // Use infinite staleTime to avoid refetching unless inputs change
    staleTime: Infinity,
    // Keep in cache for 5 minutes for when user switches tabs/views
    gcTime: 5 * 60 * 1000,
    // Keep showing previous data while fetching new results for smooth transitions
    placeholderData: (previousData) => previousData,
  });

  return {
    result: query.data ?? DEFAULT_RESULT,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
  };
}
