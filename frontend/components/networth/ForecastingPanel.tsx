"use client";

import { useMemo, useState, useRef, useCallback } from "react";
import {
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ComposedChart,
  ReferenceLine,
  Area,
} from "recharts";
import {
  ForecastingSettings,
  LiabilityTerm,
  ResolvedLiabilityTerm,
} from "@/types";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { formatCurrencyRounded, cn } from "@/lib/utils";
import { useForecastingProjection } from "@/hooks/useForecastingProjection";
import { useForecastingSettings } from "@/hooks/useForecastingSettings";

const DEFAULT_SETTINGS: ForecastingSettings = {
  inflationPct: 2,
  safeWithdrawalRate: 4,
  currentAge: 30,
  targetRetirementAge: 65,
  monthlySavingsOverride: null,
  annualExpensesOverride: null,
  pensionAccruedMonthly: null,
  pensionMonthlySalaryOverride: null,
  pensionAccrualRate: 1.5,
  pensionFullAge: 68,
  pensionGuaranteeEnabled: false,
  pensionGuaranteeAmount: 990,
  lifeExpectancy: 95,
  groupReturnRates: {},
  contributionGroup: null,
  liabilityTerms: {},
  swrExcludedGroups: [],
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ForecastingPanel() {
  const {
    settings: apiSettings,
    isLoading: settingsLoading,
    updateSetting,
  } = useForecastingSettings();
  const [showSettings, setShowSettings] = useState(false);

  const settings = apiSettings ?? DEFAULT_SETTINGS;

  // All FIRE inputs are derived on the backend from persisted settings,
  // the latest net worth snapshot and the current budget.
  const { result, isLoading: fireLoading, isFetching } =
    useForecastingProjection();
  const derived = result.derived;

  // Pension mode follows the persisted setting so the UI toggles instantly.
  const pensionActive = settings.pensionAccruedMonthly !== null;

  // Asset groups (with allocations) for the per-group return inputs.
  const latestByGroup = derived.byGroup;

  // Build chart data
  const chartData = useMemo(() => {
    const targetAge = settings.targetRetirementAge;
    return result.projections.map((p) => ({
      label: `${p.age}`,
      age: p.age,
      netWorth: p.netWorth,
      coastNetWorth: p.coastNetWorth,
      ...(p.blendedReturnPct !== undefined && {
        blendedReturnPct: p.blendedReturnPct,
      }),
      ...(p.swrBase !== undefined && { swrBase: p.swrBase }),
      // Use age-specific FIRE numbers when available (pension mode)
      // Stop drawing FIRE/Coast FIRE lines after target retirement age
      ...(p.age <= targetAge && {
        fireNumber: p.fireNumberAtAge ?? result.fireNumber,
        coastFireNumber: p.coastFireNumberAtAge ?? result.coastFireNumber,
      }),
      ...(p.netWorthEarly !== undefined && { netWorthEarly: p.netWorthEarly }),
      ...(p.netWorthNormal !== undefined && { netWorthNormal: p.netWorthNormal }),
      ...(p.netWorthLate !== undefined && { netWorthLate: p.netWorthLate }),
    }));
  }, [result, settings.targetRetirementAge]);

  // Y-axis domain
  const yDomain = useMemo(() => {
    const vals = chartData.flatMap((d) => {
      const v: number[] = [d.netWorth, d.coastNetWorth];
      if (d.fireNumber !== undefined) v.push(d.fireNumber);
      if (d.coastFireNumber !== undefined) v.push(d.coastFireNumber);
      if ("netWorthEarly" in d) v.push(d.netWorthEarly as number);
      if ("netWorthNormal" in d) v.push(d.netWorthNormal as number);
      if ("netWorthLate" in d) v.push(d.netWorthLate as number);
      return v;
    });
    const max = Math.max(...vals);
    const min = Math.min(0, ...vals);
    const pad = (max - min) * 0.05;
    return [Math.floor(min - pad), Math.ceil(max + pad)] as const;
  }, [chartData]);

  const xInterval = useMemo(() => {
    const len = chartData.length;
    if (len <= 10) return 0;
    if (len <= 20) return 1;
    if (len <= 40) return 4;
    return Math.floor(len / 8) - 1;
  }, [chartData.length]);

  const formatYAxis = (value: number) => {
    if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
    if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(0)}k`;
    return `${value}`;
  };

  const CustomTooltip = ({
    active,
    payload,
  }: {
    active?: boolean;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    payload?: Array<{ payload: Record<string, any> }>;
  }) => {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    const hasPensionLines = "netWorthEarly" in d;
    const hasFireNumbers = d.fireNumber !== undefined || d.coastFireNumber !== undefined;
    return (
      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg p-3 text-sm">
        <p className="font-medium text-gray-900 dark:text-gray-100 mb-1">
          Age {d.age}
        </p>
        {hasPensionLines ? (
          <>
            <p style={{ color: "#009E73" }}>
              Portfolio: {formatCurrencyRounded(d.netWorthNormal)}
            </p>
            {d.netWorthEarly !== d.netWorthNormal && (
              <>
                <p style={{ color: "#E69F00" }}>
                  If pension at {settings.pensionFullAge - 3}: {formatCurrencyRounded(d.netWorthEarly)}
                </p>
                <p style={{ color: "#56B4E9" }}>
                  If pension at {settings.pensionFullAge + 3}: {formatCurrencyRounded(d.netWorthLate)}
                </p>
              </>
            )}
            {hasFireNumbers && (
              <>
                <p style={{ color: "#D55E00" }}>
                  FIRE target: {formatCurrencyRounded(d.fireNumber)}
                </p>
                <p style={{ color: "#CC79A7" }}>
                  Coast FIRE: {formatCurrencyRounded(d.coastFireNumber)}
                </p>
              </>
            )}
          </>
        ) : (
          <>
            <p style={{ color: "#009E73" }}>
              Portfolio: {formatCurrencyRounded(d.netWorth)}
            </p>
            <p style={{ color: "#CC79A7" }}>
              Coast (no savings): {formatCurrencyRounded(d.coastNetWorth)}
            </p>
            {hasFireNumbers && (
              <p style={{ color: "#D55E00" }}>
                FIRE target: {formatCurrencyRounded(d.fireNumber)}
              </p>
            )}
          </>
        )}
        {d.swrBase !== undefined && (
          <p className="text-gray-500 dark:text-gray-400">
            Drawable: {formatCurrencyRounded(d.swrBase)}
          </p>
        )}
        {d.blendedReturnPct !== undefined && (
          <p className="text-gray-500 dark:text-gray-400">
            Blended return: {d.blendedReturnPct.toFixed(1)}%
          </p>
        )}
      </div>
    );
  };

  // Only show full loading skeleton on initial load, not during refetches
  if (settingsLoading || (fireLoading && result.projections.length === 0)) {
    return (
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800 p-4 h-32 animate-pulse" />
    );
  }

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800 p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
            FIRE Forecast
          </span>
          {isFetching && (
            <span className="w-3 h-3 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          )}
        </div>
        <button
          aria-label="Toggle FIRE forecast settings"
          onClick={() => setShowSettings((v) => !v)}
          className={cn(
            "flex items-center gap-1.5 px-2.5 py-1.5 text-sm rounded transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500",
            showSettings
              ? "bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300"
              : "text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
          )}
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
            />
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
            />
          </svg>
          Settings
        </button>
      </div>

      {/* Settings panel */}
      {showSettings && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
          <NumberInput
            label="Current age"
            value={settings.currentAge}
            onChange={(v) => updateSetting("currentAge", v)}
            min={0}
            max={120}
            step={1}
          />
          {!pensionActive && (
            <NumberInput
              label="Retirement age"
              value={settings.targetRetirementAge}
              onChange={(v) => updateSetting("targetRetirementAge", v)}
              min={settings.currentAge}
              max={120}
              step={1}
            />
          )}
          <NumberInput
            label="Inflation %"
            value={settings.inflationPct}
            onChange={(v) => updateSetting("inflationPct", v)}
            min={0}
            max={20}
            step={0.5}
          />
          <NumberInput
            label="SWR %"
            value={settings.safeWithdrawalRate}
            onChange={(v) => updateSetting("safeWithdrawalRate", v)}
            min={1}
            max={10}
            step={0.25}
          />
          <NumberInput
            label="Monthly savings"
            value={settings.monthlySavingsOverride ?? derived.monthlySavings}
            onChange={(v) => updateSetting("monthlySavingsOverride", v)}
            min={0}
            step={100}
            placeholder={derived.monthlySavings.toString()}
            onClear={
              settings.monthlySavingsOverride !== null
                ? () => updateSetting("monthlySavingsOverride", null)
                : undefined
            }
          />
          <NumberInput
            label="Annual expenses"
            value={settings.annualExpensesOverride ?? derived.annualExpenses}
            onChange={(v) => updateSetting("annualExpensesOverride", v)}
            min={0}
            step={1000}
            placeholder={derived.annualExpenses.toString()}
            onClear={
              settings.annualExpensesOverride !== null
                ? () => updateSetting("annualExpensesOverride", null)
                : undefined
            }
          />

          {/* Expected returns per asset group */}
          {Object.keys(latestByGroup).length > 0 && (
            <>
              <div className="col-span-full border-t border-gray-200 dark:border-gray-700 pt-3 mt-1">
                <div className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">
                  Expected return % by asset group (weighted: {derived.weightedReturnPct.toFixed(1)}%)
                </div>
              </div>
              {Object.entries(latestByGroup)
                .filter(([, amount]) => amount > 0)
                .sort(([, a], [, b]) => b - a)
                .map(([group]) => {
                  const excluded = settings.swrExcludedGroups.includes(group);
                  return (
                    <div key={group}>
                      <NumberInput
                        label={group}
                        value={
                          settings.groupReturnRates[group] ??
                          derived.groupReturnRates[group]
                        }
                        onChange={(v) => {
                          const updated = { ...settings.groupReturnRates, [group]: v };
                          updateSetting("groupReturnRates", updated);
                        }}
                        min={-10}
                        max={30}
                        step={0.5}
                      />
                      <label className="mt-1 flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-500">
                        <input
                          type="checkbox"
                          checked={excluded}
                          onChange={(e) =>
                            updateSetting(
                              "swrExcludedGroups",
                              e.target.checked
                                ? [...settings.swrExcludedGroups, group]
                                : settings.swrExcludedGroups.filter(
                                    (g) => g !== group
                                  )
                            )
                          }
                        />
                        Can&apos;t be withdrawn from
                      </label>
                    </div>
                  );
                })}
              <div className="col-span-full">
                <label className="block text-xs text-gray-600 dark:text-gray-400 mb-1">
                  Monthly savings go to
                </label>
                <select
                  className="w-full rounded border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-2 py-1 text-sm"
                  value={settings.contributionGroup ?? ""}
                  onChange={(e) =>
                    updateSetting("contributionGroup", e.target.value || null)
                  }
                >
                  <option value="">Spread across the mix</option>
                  {Object.entries(latestByGroup)
                    .filter(([, amount]) => amount > 0)
                    .sort(([, a], [, b]) => b - a)
                    .map(([group]) => (
                      <option key={group} value={group}>
                        {group}
                      </option>
                    ))}
                </select>
                <div className="mt-1 text-xs text-gray-500 dark:text-gray-500">
                  Spreading credits new money at the portfolio average. Naming a
                  group compounds it at that group&apos;s rate instead.
                </div>
              </div>
            </>
          )}

          {/* Loan terms, one loan at a time: two loans in a group rarely
              share a rate or a maturity. */}
          {Object.keys(derived.liabilitiesByCategory).length > 0 && (
            <>
              <div className="col-span-full border-t border-gray-200 dark:border-gray-700 pt-3 mt-1">
                <div className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">
                  Loan terms
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-500 mb-2">
                  Without terms a balance is held flat and only inflation erodes
                  it. The payment should match a budget expense, or savings will
                  be counted twice.
                </div>
              </div>
              {Object.entries(derived.liabilitiesByCategory).map(
                ([loan, { amount, group }]) => (
                  <LoanTerms
                    key={loan}
                    loan={loan}
                    group={group}
                    owed={amount}
                    terms={settings.liabilityTerms[loan]}
                    resolved={derived.liabilityTermsResolved[loan]}
                    onChange={(next) =>
                      updateSetting("liabilityTerms", (prev) => ({
                        ...prev,
                        [loan]: { ...prev[loan], ...next },
                      }))
                    }
                  />
                )
              )}
            </>
          )}

          {/* Pension (TyEL) section */}
          <div className="col-span-full border-t border-gray-200 dark:border-gray-700 pt-3 mt-1">
            <div className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">
              Pension (TyEL)
            </div>
          </div>
          <NumberInput
            label="Accrued monthly pension"
            value={settings.pensionAccruedMonthly ?? 0}
            onChange={(v) => updateSetting("pensionAccruedMonthly", v || null)}
            min={0}
            step={50}
            onClear={
              settings.pensionAccruedMonthly !== null
                ? () => updateSetting("pensionAccruedMonthly", null)
                : undefined
            }
          />
          <NumberInput
            label="TyEL monthly salary"
            value={settings.pensionMonthlySalaryOverride ?? derived.pensionMonthlySalary}
            onChange={(v) => updateSetting("pensionMonthlySalaryOverride", v)}
            min={0}
            step={100}
            placeholder={derived.pensionMonthlySalary.toString()}
            onClear={
              settings.pensionMonthlySalaryOverride !== null
                ? () => updateSetting("pensionMonthlySalaryOverride", null)
                : undefined
            }
          />
          <NumberInput
            label="Accrual rate %"
            value={settings.pensionAccrualRate}
            onChange={(v) => updateSetting("pensionAccrualRate", v)}
            min={0}
            max={10}
            step={0.1}
          />
          <NumberInput
            label="Full pension age"
            value={settings.pensionFullAge}
            onChange={(v) => updateSetting("pensionFullAge", v)}
            min={60}
            max={75}
            step={1}
          />
          {/* Guarantee pension (takuueläke) */}
          <div className="col-span-full flex items-center gap-2 mt-1">
            <input
              type="checkbox"
              id="pension-guarantee"
              checked={settings.pensionGuaranteeEnabled}
              onChange={(e) => updateSetting("pensionGuaranteeEnabled", e.target.checked)}
              className="rounded border-gray-300 dark:border-gray-600 text-emerald-600 focus:ring-emerald-500"
            />
            <label htmlFor="pension-guarantee" className="text-xs text-gray-600 dark:text-gray-400">
              Include takuueläke (guarantee pension)
            </label>
          </div>
          {settings.pensionGuaranteeEnabled && (
            <NumberInput
              label="Guarantee amount (€/mo)"
              value={settings.pensionGuaranteeAmount}
              onChange={(v) => updateSetting("pensionGuaranteeAmount", v)}
              min={0}
              max={5000}
              step={10}
            />
          )}
          <NumberInput
            label="Life expectancy"
            value={settings.lifeExpectancy}
            onChange={(v) => updateSetting("lifeExpectancy", v)}
            min={settings.pensionFullAge + 3}
            max={120}
            step={1}
          />
        </div>
      )}

      {/* FIRE metrics cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricCard
          label="FIRE Number"
          value={formatCurrencyRounded(result.fireNumberNow)}
          sublabel={
            settings.swrExcludedGroups.length > 0
              ? `vs ${formatCurrencyRounded(derived.swrBase)} drawable`
              : result.pension
                ? `If retiring now — ${settings.safeWithdrawalRate}% SWR + pension`
                : `${settings.safeWithdrawalRate}% SWR`
          }
        />
        <MetricCard
          label="Years to FIRE"
          value={result.yearsToFire !== null ? `${result.yearsToFire}` : "N/A"}
          sublabel={
            result.fireAge !== null
              ? result.onTrack
                ? `Age ${Math.round(result.fireAge)} — on track`
                : `Age ${Math.round(result.fireAge)} — target ${settings.targetRetirementAge}`
              : "Increase savings or return"
          }
          highlight={result.onTrack}
        />
        <MetricCard
          label="Coast FIRE"
          value={formatCurrencyRounded(result.coastFireNumber)}
          sublabel={
            result.coastFireReached
              ? "Reached — can stop saving!"
              : `${formatCurrencyRounded(result.coastFireNumber - derived.currentNetWorth)} to go`
          }
          highlight={result.coastFireReached}
        />
        <MetricCard
          label="Real return"
          value={`${derived.realReturnPct.toFixed(1)}%`}
          sublabel={`${derived.weightedReturnPct.toFixed(1)}% weighted, ${settings.inflationPct}% infl.`}
        />
      </div>

      {/* Pension scenarios */}
      {result.pension && (() => {
        const pension = result.pension;
        const labels: Record<string, string> = {
          early: "Early pension",
          normal: "Normal pension",
          late: "Delayed pension",
        };
        const colors: Record<string, string> = {
          early: "#E69F00",
          normal: "#009E73",
          late: "#56B4E9",
        };
        const normalScenario = pension.scenarios[1];
        const coveragePct = derived.annualExpenses > 0
          ? Math.round((normalScenario.annualPension / derived.annualExpenses) * 100)
          : 0;
        return (
          <div className="rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-3">
            <div className="text-sm text-gray-600 dark:text-gray-400 mb-2">
              Pension estimate: currently accrued {formatCurrencyRounded(settings.pensionAccruedMonthly ?? 0)}/mo will grow to {formatCurrencyRounded(pension.projectedMonthlyPension)}/mo if working until {settings.targetRetirementAge}, which would cover {coveragePct}% of expenses.
            </div>
            <div className="grid grid-cols-3 gap-3 text-sm">
              {pension.scenarios.map((s) => (
                <div key={s.label}>
                  <div className="font-bold" style={{ color: colors[s.label] }}>
                    {formatCurrencyRounded(s.monthlyPension)}/mo
                  </div>
                  <div className="text-sm text-gray-600 dark:text-gray-400">
                    {labels[s.label]} at {s.pensionStartAge}
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })()}

      {/* Loans whose payment does not cover their interest */}
      {result.warnings
        .filter((w) => w.code === "negative_amortization")
        .map((w) => (
          <div
            key={w.name}
            className="rounded-lg border border-red-300 dark:border-red-700 bg-red-50 dark:bg-red-900/20 p-3 text-sm"
          >
            <span className="text-red-600 dark:text-red-400">
              {w.name}: the monthly payment does not cover the interest, so the
              balance grows every month. The projection cannot show a payoff
              until the payment or rate changes.
            </span>
          </div>
        ))}

      {/* Guarantee pension (takuueläke) crossover milestone */}
      {result.pension?.guaranteeActive && (() => {
        const crossover = result.pension.crossoverAge;
        return (
          <div className="rounded-lg border border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-900/20 p-3 text-sm">
            <span className="text-blue-700 dark:text-blue-300">
              Takuueläke active: projected TyEL ({formatCurrencyRounded(result.pension.projectedMonthlyPension)}/mo)
              is below the guarantee ({formatCurrencyRounded(result.pension.guaranteeAmount)}/mo).
              {crossover !== null
                ? ` Your TyEL will exceed the guarantee at age ${crossover}, after which your pension is portable abroad.`
                : " Your TyEL may not reach the guarantee level before retirement."}
            </span>
          </div>
        );
      })()}

      {/* Portfolio depletion warning */}
      {result.portfolioDepletedAge !== null && result.pension && (() => {
        const normalPension = result.pension.scenarios[1];
        const monthlyExpenses = derived.annualExpenses / 12;
        const shortfall = monthlyExpenses - normalPension.monthlyPension;
        const pensionStarted = result.portfolioDepletedAge >= normalPension.pensionStartAge;
        return (
          <div className="rounded-lg border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/20 p-3 text-sm">
            {pensionStarted ? (
              <span className="text-amber-700 dark:text-amber-300">
                Portfolio runs out at age {result.portfolioDepletedAge}. Pension of {formatCurrencyRounded(normalPension.monthlyPension)}/mo
                {shortfall > 0
                  ? ` leaves a ${formatCurrencyRounded(shortfall)}/mo shortfall.`
                  : ` covers all expenses.`}
              </span>
            ) : (
              <span className="text-red-600 dark:text-red-400">
                Portfolio runs out at age {result.portfolioDepletedAge}, before pension starts at {normalPension.pensionStartAge}. No income until then.
              </span>
            )}
          </div>
        );
      })()}

      {/* Retirement age slider (pension mode only - in simple FIRE mode, retirement age doesn't affect the calculation) */}
      {pensionActive && (
        <div className="space-y-1">
          <div className="text-sm text-gray-500 dark:text-gray-400">
            Retire at age
          </div>
          <RetirementSlider
            value={settings.targetRetirementAge}
            min={settings.currentAge + 1}
            max={settings.pensionFullAge + 3}
            onChange={(v) => updateSetting("targetRetirementAge", v)}
          />
        </div>
      )}

      {/* Projection chart */}
      {chartData.length > 1 && (
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }} role="img" aria-label="FIRE projection chart">
              <defs>
                <linearGradient id="fireProjectionGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#009E73" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#009E73" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#e5e7eb"
                className="dark:stroke-gray-700"
                vertical={false}
              />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 14 }}
                tickLine={false}
                axisLine={false}
                interval={xInterval}
                className="text-gray-600 dark:text-gray-400"
              />
              <YAxis
                tickFormatter={formatYAxis}
                tick={{ fontSize: 14 }}
                tickLine={false}
                axisLine={false}
                width={60}
                domain={yDomain}
                className="text-gray-600 dark:text-gray-400"
              />
              <Tooltip content={<CustomTooltip />} />

              {/* FIRE number line - use Line for age-varying (pension mode) or ReferenceLine for constant */}
              {result.pension ? (
                <Line
                  type="monotone"
                  dataKey="fireNumber"
                  stroke="#D55E00"
                  strokeWidth={2}
                  strokeDasharray="8 4"
                  dot={false}
                />
              ) : (
                <ReferenceLine
                  y={result.fireNumber}
                  stroke="#D55E00"
                  strokeWidth={2}
                  strokeDasharray="8 4"
                />
              )}

              {/* Coast FIRE number line - use Line for age-varying (pension mode) or ReferenceLine for constant */}
              {result.pension ? (
                <Line
                  type="monotone"
                  dataKey="coastFireNumber"
                  stroke="#CC79A7"
                  strokeWidth={1.5}
                  strokeDasharray="4 4"
                  dot={false}
                />
              ) : (
                <ReferenceLine
                  y={result.coastFireNumber}
                  stroke="#56B4E9"
                  strokeWidth={1.5}
                  strokeDasharray="4 4"
                />
              )}

              {/* Retirement age line */}
              {settings.targetRetirementAge > settings.currentAge && (
                <ReferenceLine
                  x={`${settings.targetRetirementAge}`}
                  stroke="#9ca3af"
                  strokeWidth={1}
                  strokeDasharray="4 4"
                />
              )}

              {/* Zero line for pension drawdown */}
              {result.pension && (
                <ReferenceLine y={0} stroke="#9ca3af" strokeWidth={1} />
              )}

              {/* Net worth with savings */}
              <Area
                type="monotone"
                dataKey={result.pension ? "netWorthNormal" : "netWorth"}
                stroke="#009E73"
                strokeWidth={2}
                fill="url(#fireProjectionGrad)"
              />

              {/* Coast scenario (no more savings) — hide when pension active */}
              {!result.pension && (
                <Line
                  type="monotone"
                  dataKey="coastNetWorth"
                  stroke="#CC79A7"
                  strokeWidth={1.5}
                  strokeDasharray="5 5"
                  dot={false}
                />
              )}

              {/* Pension scenario lines */}
              {result.pension && (
                <>
                  <Line
                    type="monotone"
                    dataKey="netWorthEarly"
                    stroke="#E69F00"
                    strokeWidth={1.5}
                    strokeDasharray="5 5"
                    dot={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="netWorthLate"
                    stroke="#56B4E9"
                    strokeWidth={1.5}
                    strokeDasharray="5 5"
                    dot={false}
                  />
                </>
              )}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Legend */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-gray-600 dark:text-gray-400">
        {result.pension ? (
          <>
            <LegendItem color="#009E73" label="Normal pension" />
            <LegendItem color="#E69F00" label="Early pension" dashed />
            <LegendItem color="#56B4E9" label="Delayed pension" dashed />
            <LegendItem color="#D55E00" label="FIRE target" dashed />
            <LegendItem color="#CC79A7" label="Coast FIRE" dashed />
          </>
        ) : (
          <>
            <LegendItem color="#009E73" label="With savings" />
            <LegendItem color="#CC79A7" label="Coast (no savings)" dashed />
            <LegendItem color="#D55E00" label="FIRE target" dashed />
            <LegendItem color="#56B4E9" label="Coast FIRE" dashed />
          </>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function MetricCard({
  label,
  value,
  sublabel,
  highlight,
}: {
  label: string;
  value: string;
  sublabel?: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border p-3",
        highlight
          ? "border-emerald-300 dark:border-emerald-700 bg-emerald-50 dark:bg-emerald-900/20"
          : "border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900"
      )}
    >
      <div className="text-sm text-gray-600 dark:text-gray-400 mb-1">{label}</div>
      <div className="text-lg font-bold text-gray-900 dark:text-gray-100">{value}</div>
      {sublabel && (
        <div
          className={cn(
            "text-sm mt-0.5",
            highlight
              ? "text-emerald-600 dark:text-emerald-400"
              : "text-gray-500 dark:text-gray-400"
          )}
        >
          {sublabel}
        </div>
      )}
    </div>
  );
}

function NumberInput({
  label,
  value,
  onChange,
  min,
  max,
  step,
  placeholder,
  onClear,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  step?: number;
  placeholder?: string;
  onClear?: () => void;
}) {
  // While focused, keep the raw text so the field can be cleared and retyped
  // (no forced 0); otherwise mirror the numeric prop.
  const [focused, setFocused] = useState(false);
  const [text, setText] = useState("");
  const display = focused ? text : String(value);

  return (
    <div>
      <label className="block text-xs text-gray-600 dark:text-gray-400 mb-1">{label}</label>
      <div className="flex items-center gap-1">
        <input
          type="number"
          value={display}
          onFocus={() => {
            setText(String(value));
            setFocused(true);
          }}
          onBlur={() => setFocused(false)}
          onChange={(e) => {
            const raw = e.target.value;
            setText(raw);
            // Only propagate real numbers; an empty/partial field is left as-is
            // until the user types a value or blurs back to the current one.
            if (raw === "") return;
            const parsed = parseFloat(raw);
            if (!Number.isNaN(parsed)) onChange(parsed);
          }}
          min={min}
          max={max}
          step={step}
          placeholder={placeholder}
          className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-700 rounded bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
        />
        {onClear && (
          <button
            onClick={onClear}
            className="text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300 px-1"
            title="Reset to auto"
          >
            Auto
          </button>
        )}
      </div>
    </div>
  );
}

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

/** One loan's terms: a rate, plus either a payment or a payoff date. */
function LoanTerms({
  loan,
  group,
  owed,
  terms,
  resolved,
  onChange,
}: {
  loan: string;
  group: string;
  owed: number;
  terms?: LiabilityTerm;
  resolved?: ResolvedLiabilityTerm;
  onChange: (next: Partial<LiabilityTerm>) => void;
}) {
  const schedule = terms?.schedule ?? "fixed";
  const defaultEndYear = new Date().getFullYear() + 10;

  // A stated payoff date implies an instalment; a stated instalment implies a
  // payoff date. Whichever was not typed in is read back here.
  const payment = resolved?.monthly_payment ?? 0;
  const hint =
    schedule === "annuity"
      ? `${payment.toFixed(2)} €/mo to clear it by then`
      : payment <= 0
        ? "No payment set, so the balance is held flat"
        : resolved && resolved.payoff_year > 0
          ? `Paid off ${MONTHS[resolved.payoff_month - 1]} ${resolved.payoff_year}`
          : "This payment does not cover the interest";

  return (
    <div className="col-span-full rounded-lg border border-gray-200 dark:border-gray-800 p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2 mb-2">
        <div className="text-sm font-medium">
          {loan}{" "}
          <span className="text-xs font-normal text-gray-500 dark:text-gray-500">
            {group}
          </span>
        </div>
        <div className="text-xs text-gray-500 dark:text-gray-500">
          {formatCurrencyRounded(owed)} owed
        </div>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <NumberInput
          label="Rate %"
          value={terms?.rate_pct ?? 0}
          onChange={(v) => onChange({ rate_pct: v })}
          min={0}
          max={30}
          step={0.1}
        />
        <div className="col-span-full sm:col-span-2">
          <label className="block text-xs text-gray-600 dark:text-gray-400 mb-1">
            Schedule
          </label>
          <SegmentedControl
            ariaLabel={`${loan} schedule`}
            options={[
              { value: "annuity", label: "Paid off by" },
              { value: "fixed", label: "Fixed payment" },
            ]}
            value={schedule}
            onChange={(v) => {
              const next = v as "fixed" | "annuity";
              // An annuity is saved with its payoff date, or the API rejects
              // it as incomplete and the switch silently rolls back.
              onChange(
                next === "annuity"
                  ? {
                      schedule: next,
                      end_year: terms?.end_year ?? defaultEndYear,
                      end_month: terms?.end_month ?? 12,
                    }
                  : { schedule: next }
              );
            }}
          />
        </div>
        {schedule === "annuity" ? (
          <>
            <NumberInput
              label="Payoff year"
              value={terms?.end_year ?? defaultEndYear}
              onChange={(v) => onChange({ end_year: Math.round(v) })}
              min={new Date().getFullYear()}
              max={2200}
              step={1}
            />
            <NumberInput
              label="Payoff month"
              value={terms?.end_month ?? 12}
              onChange={(v) => onChange({ end_month: Math.round(v) })}
              min={1}
              max={12}
              step={1}
            />
          </>
        ) : (
          <NumberInput
            label="Payment /mo"
            value={terms?.monthly_payment ?? 0}
            onChange={(v) => onChange({ monthly_payment: v })}
            min={0}
            step={50}
          />
        )}
      </div>
      <div className="mt-2 text-xs text-gray-500 dark:text-gray-500">{hint}</div>
    </div>
  );
}

function LegendItem({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1">
      <svg width="16" height="4" className="inline-block">
        <line
          x1="0" y1="2" x2="16" y2="2"
          stroke={color}
          strokeWidth={2}
          strokeDasharray={dashed ? "4 2" : undefined}
        />
      </svg>
      {label}
    </span>
  );
}

function RetirementSlider({
  value,
  min,
  max,
  onChange,
}: {
  value: number;
  min: number;
  max: number;
  onChange: (v: number) => void;
}) {
  const [dragging, setDragging] = useState(false);
  const trackRef = useRef<HTMLDivElement>(null);

  const pct = max > min ? ((value - min) / (max - min)) * 100 : 0;
  const thumbSize = dragging ? 40 : 28;
  const halfThumb = thumbSize / 2;

  const getValueFromEvent = useCallback(
    (clientX: number) => {
      const track = trackRef.current;
      if (!track) return value;
      const rect = track.getBoundingClientRect();
      const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      return Math.round(min + ratio * (max - min));
    },
    [min, max, value]
  );

  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      setDragging(true);
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
      onChange(getValueFromEvent(e.clientX));
    },
    [onChange, getValueFromEvent]
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!dragging) return;
      onChange(getValueFromEvent(e.clientX));
    },
    [dragging, onChange, getValueFromEvent]
  );

  const handlePointerUp = useCallback(() => {
    setDragging(false);
  }, []);

  return (
    <div className="pt-2 pb-1">
      <div
        ref={trackRef}
        className="relative h-2 rounded-full bg-gray-200 dark:bg-gray-700 cursor-pointer select-none touch-none"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
      >
        {/* Filled portion */}
        <div
          className="absolute top-0 left-0 h-full rounded-full bg-emerald-500"
          style={{ width: `${pct}%` }}
        />
        {/* Thumb with number */}
        <div
          className={cn(
            "absolute top-1/2 flex items-center justify-center rounded-full",
            "bg-emerald-500 text-white font-bold shadow-md",
            "transition-all duration-150 ease-out",
            dragging ? "scale-110" : ""
          )}
          style={{
            width: thumbSize,
            height: thumbSize,
            left: `calc(${pct}% - ${halfThumb}px)`,
            transform: "translateY(-50%)",
            fontSize: dragging ? 14 : 12,
          }}
        >
          {value}
        </div>
      </div>
      <div className="flex justify-between text-sm text-gray-500 dark:text-gray-400 mt-2">
        <span>{min}</span>
        <span>{max}</span>
      </div>
    </div>
  );
}
