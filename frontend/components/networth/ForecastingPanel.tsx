"use client";

import { useMemo, useState, useEffect, useCallback } from "react";
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
import { NetWorthSnapshot, BudgetTotals, ForecastingSettings } from "@/types";
import { formatCurrencyRounded, cn } from "@/lib/utils";
import { calculateFire, FireInputs, FireResult, ProjectionPoint } from "@/lib/fire";

// ---------------------------------------------------------------------------
// localStorage persistence
// ---------------------------------------------------------------------------

const STORAGE_KEY = "vipu-forecasting-settings";

const DEFAULT_SETTINGS: ForecastingSettings = {
  annualReturnPct: 7,
  inflationPct: 2,
  safeWithdrawalRate: 4,
  currentAge: 30,
  targetRetirementAge: 65,
  monthlySavingsOverride: null,
  annualExpensesOverride: null,
};

function loadSettings(): ForecastingSettings {
  if (typeof window === "undefined") return DEFAULT_SETTINGS;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
  } catch {
    /* ignore */
  }
  return DEFAULT_SETTINGS;
}

function saveSettings(s: ForecastingSettings) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
  } catch {
    /* ignore */
  }
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ForecastingPanelProps {
  snapshots: NetWorthSnapshot[];
  budgetTotals?: BudgetTotals | null;
  monthlyExpenses?: number;
  monthlySavings?: number;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ForecastingPanel({
  snapshots,
  budgetTotals,
  monthlyExpenses,
  monthlySavings,
}: ForecastingPanelProps) {
  const [settings, setSettings] = useState<ForecastingSettings>(DEFAULT_SETTINGS);
  const [isHydrated, setIsHydrated] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  // Hydrate from localStorage
  useEffect(() => {
    setSettings(loadSettings());
    setIsHydrated(true);
  }, []);

  // Persist changes
  useEffect(() => {
    if (isHydrated) saveSettings(settings);
  }, [settings, isHydrated]);

  const updateSetting = useCallback(
    <K extends keyof ForecastingSettings>(key: K, value: ForecastingSettings[K]) => {
      setSettings((prev) => ({ ...prev, [key]: value }));
    },
    []
  );

  // Derive values from budget data where possible
  const derivedMonthlySavings =
    settings.monthlySavingsOverride ??
    monthlySavings ??
    (budgetTotals ? budgetTotals.net_income - budgetTotals.total_expenses : 0);

  const derivedAnnualExpenses =
    settings.annualExpensesOverride ??
    (monthlyExpenses ?? budgetTotals?.total_expenses ?? 0) * 12;

  const currentNetWorth = snapshots.length > 0 ? snapshots[0].net_worth : 0;

  const fireInputs: FireInputs = useMemo(
    () => ({
      currentNetWorth,
      monthlyContribution: derivedMonthlySavings,
      annualExpenses: derivedAnnualExpenses,
      annualReturnPct: settings.annualReturnPct,
      inflationPct: settings.inflationPct,
      currentAge: settings.currentAge,
      targetRetirementAge: settings.targetRetirementAge,
      safeWithdrawalRate: settings.safeWithdrawalRate,
    }),
    [
      currentNetWorth,
      derivedMonthlySavings,
      derivedAnnualExpenses,
      settings.annualReturnPct,
      settings.inflationPct,
      settings.currentAge,
      settings.targetRetirementAge,
      settings.safeWithdrawalRate,
    ]
  );

  const result: FireResult = useMemo(() => calculateFire(fireInputs), [fireInputs]);

  // Build chart data
  const chartData = useMemo(() => {
    return result.projections.map((p) => ({
      label: `${p.age}`,
      age: p.age,
      netWorth: p.netWorth,
      coastNetWorth: p.coastNetWorth,
      fireNumber: result.fireNumber,
      coastFireNumber: result.coastFireNumber,
    }));
  }, [result]);

  // Y-axis domain
  const yDomain = useMemo(() => {
    const vals = chartData.flatMap((d) => [d.netWorth, d.coastNetWorth, d.fireNumber]);
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
    payload?: Array<{
      payload: {
        age: number;
        netWorth: number;
        coastNetWorth: number;
        fireNumber: number;
        coastFireNumber: number;
      };
    }>;
  }) => {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    return (
      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg p-3 text-sm">
        <p className="font-medium text-gray-900 dark:text-gray-100 mb-1">
          Age {d.age}
        </p>
        <p className="text-emerald-600 dark:text-emerald-400">
          With savings: {formatCurrencyRounded(d.netWorth)}
        </p>
        <p className="text-blue-500 dark:text-blue-400">
          Coast (no savings): {formatCurrencyRounded(d.coastNetWorth)}
        </p>
        <p className="text-amber-600 dark:text-amber-400">
          FIRE target: {formatCurrencyRounded(d.fireNumber)}
        </p>
      </div>
    );
  };

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800 p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium text-gray-700 dark:text-gray-300">
          FIRE Forecast
        </div>
        <button
          onClick={() => setShowSettings((v) => !v)}
          className={cn(
            "flex items-center gap-1.5 px-2 py-1 text-sm rounded transition-colors",
            showSettings
              ? "bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300"
              : "text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
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
          <NumberInput
            label="Retirement age"
            value={settings.targetRetirementAge}
            onChange={(v) => updateSetting("targetRetirementAge", v)}
            min={settings.currentAge}
            max={120}
            step={1}
          />
          <NumberInput
            label="Expected return %"
            value={settings.annualReturnPct}
            onChange={(v) => updateSetting("annualReturnPct", v)}
            min={0}
            max={30}
            step={0.5}
          />
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
            value={settings.monthlySavingsOverride ?? derivedMonthlySavings}
            onChange={(v) => updateSetting("monthlySavingsOverride", v)}
            min={0}
            step={100}
            placeholder={derivedMonthlySavings.toString()}
            onClear={
              settings.monthlySavingsOverride !== null
                ? () => updateSetting("monthlySavingsOverride", null)
                : undefined
            }
          />
          <NumberInput
            label="Annual expenses"
            value={settings.annualExpensesOverride ?? derivedAnnualExpenses}
            onChange={(v) => updateSetting("annualExpensesOverride", v)}
            min={0}
            step={1000}
            placeholder={derivedAnnualExpenses.toString()}
            onClear={
              settings.annualExpensesOverride !== null
                ? () => updateSetting("annualExpensesOverride", null)
                : undefined
            }
          />
        </div>
      )}

      {/* FIRE metrics cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricCard
          label="FIRE Number"
          value={formatCurrencyRounded(result.fireNumber)}
          sublabel={`${settings.safeWithdrawalRate}% SWR`}
        />
        <MetricCard
          label="Years to FIRE"
          value={result.yearsToFire !== null ? `${result.yearsToFire}` : "N/A"}
          sublabel={
            result.fireAge !== null
              ? `Age ${Math.round(result.fireAge)}`
              : "Increase savings or return"
          }
          highlight={result.yearsToFire !== null && result.yearsToFire <= 0}
        />
        <MetricCard
          label="Coast FIRE"
          value={formatCurrencyRounded(result.coastFireNumber)}
          sublabel={
            result.coastFireReached
              ? "Reached!"
              : result.coastFireAge !== null
                ? `At age ${Math.round(result.coastFireAge)}`
                : "Not yet reachable"
          }
          highlight={result.coastFireReached}
        />
        <MetricCard
          label="Real return"
          value={`${(settings.annualReturnPct - settings.inflationPct).toFixed(1)}%`}
          sublabel={`${settings.annualReturnPct}% - ${settings.inflationPct}% infl.`}
        />
      </div>

      {/* Projection chart */}
      {chartData.length > 1 && (
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="fireProjectionGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
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

              {/* FIRE number line */}
              <ReferenceLine
                y={result.fireNumber}
                stroke="#f59e0b"
                strokeWidth={2}
                strokeDasharray="8 4"
              />

              {/* Coast FIRE number line */}
              <ReferenceLine
                y={result.coastFireNumber}
                stroke="#6366f1"
                strokeWidth={1.5}
                strokeDasharray="4 4"
              />

              {/* Retirement age line */}
              {settings.targetRetirementAge > settings.currentAge && (
                <ReferenceLine
                  x={`${settings.targetRetirementAge}`}
                  stroke="#9ca3af"
                  strokeWidth={1}
                  strokeDasharray="4 4"
                />
              )}

              {/* Net worth with savings */}
              <Area
                type="monotone"
                dataKey="netWorth"
                stroke="#10b981"
                strokeWidth={2}
                fill="url(#fireProjectionGrad)"
              />

              {/* Coast scenario (no more savings) */}
              <Line
                type="monotone"
                dataKey="coastNetWorth"
                stroke="#6366f1"
                strokeWidth={1.5}
                strokeDasharray="5 5"
                dot={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Legend */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500 dark:text-gray-400">
        <span className="inline-flex items-center gap-1">
          <span className="w-3 h-0.5 bg-emerald-500 inline-block" /> With savings
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="w-3 h-0.5 bg-indigo-500 inline-block" style={{ borderTop: "2px dashed" }} /> Coast (no savings)
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="w-3 h-0.5 bg-amber-500 inline-block" style={{ borderTop: "2px dashed" }} /> FIRE target
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="w-3 h-0.5 bg-indigo-500 inline-block" style={{ borderTop: "1.5px dashed" }} /> Coast FIRE
        </span>
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
      <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">{label}</div>
      <div className="text-lg font-bold text-gray-900 dark:text-gray-100">{value}</div>
      {sublabel && (
        <div
          className={cn(
            "text-xs mt-0.5",
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
  return (
    <div>
      <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">{label}</label>
      <div className="flex items-center gap-1">
        <input
          type="number"
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          min={min}
          max={max}
          step={step}
          placeholder={placeholder}
          className="w-full px-2 py-1 text-sm border border-gray-300 dark:border-gray-700 rounded bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
        />
        {onClear && (
          <button
            onClick={onClear}
            className="text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 px-1"
            title="Reset to auto"
          >
            Auto
          </button>
        )}
      </div>
    </div>
  );
}
