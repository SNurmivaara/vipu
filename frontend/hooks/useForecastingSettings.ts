import { useRef, useCallback, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchForecastingSettings,
  updateForecastingSettings,
} from "@/lib/api";
import { ForecastingSettings, ForecastingSettingsAPI } from "@/types";

const QUERY_KEY = ["forecasting-settings"];
const DEBOUNCE_MS = 500;
const LEGACY_STORAGE_KEY = "vipu-forecasting-settings";
const MIGRATION_FLAG = "vipu-forecasting-migrated";

const CAMEL_TO_SNAKE: Record<keyof ForecastingSettings, keyof Omit<ForecastingSettingsAPI, "id" | "updated_at">> = {
  inflationPct: "inflation_pct",
  safeWithdrawalRate: "safe_withdrawal_rate",
  currentAge: "current_age",
  targetRetirementAge: "target_retirement_age",
  monthlySavingsOverride: "monthly_savings_override",
  annualExpensesOverride: "annual_expenses_override",
  pensionAccruedMonthly: "pension_accrued_monthly",
  pensionMonthlySalaryOverride: "pension_monthly_salary_override",
  pensionAccrualRate: "pension_accrual_rate",
  pensionFullAge: "pension_full_age",
  pensionGuaranteeEnabled: "pension_guarantee_enabled",
  pensionGuaranteeAmount: "pension_guarantee_amount",
  lifeExpectancy: "life_expectancy",
  groupReturnRates: "group_return_rates",
};

function apiToSettings(api: ForecastingSettingsAPI): ForecastingSettings {
  return {
    inflationPct: api.inflation_pct,
    safeWithdrawalRate: api.safe_withdrawal_rate,
    currentAge: api.current_age,
    targetRetirementAge: api.target_retirement_age,
    monthlySavingsOverride: api.monthly_savings_override,
    annualExpensesOverride: api.annual_expenses_override,
    pensionAccruedMonthly: api.pension_accrued_monthly,
    pensionMonthlySalaryOverride: api.pension_monthly_salary_override,
    pensionAccrualRate: api.pension_accrual_rate,
    pensionFullAge: api.pension_full_age,
    pensionGuaranteeEnabled: api.pension_guarantee_enabled,
    pensionGuaranteeAmount: api.pension_guarantee_amount,
    lifeExpectancy: api.life_expectancy,
    groupReturnRates: api.group_return_rates ?? {},
  };
}

function settingsToApi(settings: Partial<ForecastingSettings>): Partial<Omit<ForecastingSettingsAPI, "id" | "updated_at">> {
  const result: Partial<Omit<ForecastingSettingsAPI, "id" | "updated_at">> = {};
  for (const [camel, snake] of Object.entries(CAMEL_TO_SNAKE)) {
    if (camel in settings) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (result as any)[snake] = settings[camel as keyof ForecastingSettings];
    }
  }
  return result;
}

export function useForecastingSettings() {
  const queryClient = useQueryClient();
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const pendingUpdate = useRef<Partial<ForecastingSettings>>({});
  const mutateRef = useRef<typeof mutation.mutate>(undefined);

  const query = useQuery<ForecastingSettingsAPI, Error, ForecastingSettings>({
    queryKey: QUERY_KEY,
    queryFn: fetchForecastingSettings,
    select: apiToSettings,
  });

  const mutation = useMutation({
    mutationFn: (update: Partial<ForecastingSettings>) =>
      updateForecastingSettings(settingsToApi(update)),
    onSuccess: (data) => {
      queryClient.setQueryData(QUERY_KEY, data);
    },
    onError: () => {
      // Roll back optimistic update on failure
      queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
  });
  mutateRef.current = mutation.mutate;

  // One-time migration: push localStorage settings to backend, then clean up
  const migrated = useRef(false);
  useEffect(() => {
    if (migrated.current || !query.data || typeof window === "undefined") return;
    if (localStorage.getItem(MIGRATION_FLAG)) {
      migrated.current = true;
      return;
    }
    const raw = localStorage.getItem(LEGACY_STORAGE_KEY);
    if (raw) {
      try {
        const legacy = JSON.parse(raw) as Partial<ForecastingSettings>;
        migrated.current = true;
        updateForecastingSettings(settingsToApi(legacy))
          .then(() => {
            localStorage.removeItem(LEGACY_STORAGE_KEY);
            localStorage.setItem(MIGRATION_FLAG, "1");
            queryClient.invalidateQueries({ queryKey: QUERY_KEY });
          })
          .catch(() => {
            // API failed — allow retry on next load
            migrated.current = false;
          });
      } catch {
        // Corrupt localStorage — just mark as migrated
        localStorage.setItem(MIGRATION_FLAG, "1");
        migrated.current = true;
      }
    } else {
      localStorage.setItem(MIGRATION_FLAG, "1");
      migrated.current = true;
    }
  }, [query.data, queryClient]);

  const updateSetting = useCallback(
    <K extends keyof ForecastingSettings>(
      key: K,
      value: ForecastingSettings[K]
    ) => {
      // Optimistic update (immediate — UI stays snappy)
      queryClient.setQueryData(
        QUERY_KEY,
        (old: ForecastingSettingsAPI | undefined) => {
          if (!old) return old;
          const apiUpdate = settingsToApi({ [key]: value });
          return { ...old, ...apiUpdate };
        }
      );

      // Batch and debounce the API call
      pendingUpdate.current = { ...pendingUpdate.current, [key]: value };
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        const update = { ...pendingUpdate.current };
        pendingUpdate.current = {};
        mutateRef.current?.(update);
      }, DEBOUNCE_MS);
    },
    [queryClient]
  );

  return {
    settings: query.data,
    isLoading: query.isLoading,
    updateSetting,
  };
}
