"use client";

import { useMemo, useState, useEffect, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Line,
  ComposedChart,
} from "recharts";
import { NetWorthSnapshot, GoalProgress, ForecastPeriod } from "@/types";
import { formatCurrency } from "@/lib/utils";
import { fetchForecast } from "@/lib/api";

interface NetWorthChartProps {
  snapshots: NetWorthSnapshot[];
  netWorthGoals?: GoalProgress[];
}

const MONTH_NAMES = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
];

const PERIOD_LABELS: Record<ForecastPeriod, string> = {
  month: "1M",
  quarter: "3M",
  half_year: "6M",
  year: "1Y",
};

const STORAGE_KEY = "vipu-chart-settings";

interface ChartSettings {
  showForecast: boolean;
  forecastPeriod: ForecastPeriod;
}

function loadChartSettings(): ChartSettings {
  if (typeof window === "undefined") {
    return { showForecast: false, forecastPeriod: "quarter" };
  }
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      return {
        showForecast: parsed.showForecast ?? false,
        forecastPeriod: parsed.forecastPeriod ?? "quarter",
      };
    }
  } catch {
    // Ignore parse errors
  }
  return { showForecast: false, forecastPeriod: "quarter" };
}

function saveChartSettings(settings: ChartSettings) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  } catch {
    // Ignore storage errors
  }
}

export function NetWorthChart({ snapshots, netWorthGoals = [] }: NetWorthChartProps) {
  const [showForecast, setShowForecast] = useState(false);
  const [forecastPeriod, setForecastPeriod] = useState<ForecastPeriod>("quarter");
  const [isHydrated, setIsHydrated] = useState(false);

  // Load settings from localStorage after hydration
  useEffect(() => {
    const settings = loadChartSettings();
    setShowForecast(settings.showForecast);
    setForecastPeriod(settings.forecastPeriod);
    setIsHydrated(true);
  }, []);

  // Save settings when they change (after initial hydration)
  useEffect(() => {
    if (isHydrated) {
      saveChartSettings({ showForecast, forecastPeriod });
    }
  }, [showForecast, forecastPeriod, isHydrated]);

  const handleToggleForecast = useCallback(() => {
    setShowForecast((prev) => !prev);
  }, []);

  const handlePeriodChange = useCallback((period: ForecastPeriod) => {
    setForecastPeriod(period);
  }, []);

  const { data: forecast, isLoading: forecastLoading, isError: forecastError } = useQuery({
    queryKey: ["forecast", forecastPeriod],
    queryFn: () => fetchForecast({ period: forecastPeriod, months_ahead: 12 }),
    enabled: showForecast && snapshots.length > 0,
  });

  const chartData = useMemo(() => {
    const historicalData = [...snapshots]
      .reverse()
      .map((snapshot) => ({
        name: `${MONTH_NAMES[snapshot.month - 1]} ${snapshot.year}`,
        netWorth: snapshot.net_worth,
        assets: snapshot.total_assets,
        liabilities: Math.abs(snapshot.total_liabilities),
        forecast: null as number | null,
      }));

    // Add forecast data if enabled
    if (showForecast && forecast?.projections) {
      // Connect the forecast line to the last historical point
      if (historicalData.length > 0 && forecast.projections.length > 0) {
        const lastHistorical = historicalData[historicalData.length - 1];
        lastHistorical.forecast = lastHistorical.netWorth;
      }

      // Add forecast points
      const forecastData = forecast.projections.map((p) => ({
        name: `${MONTH_NAMES[p.month - 1]} ${p.year}`,
        netWorth: null as number | null,
        assets: null as number | null,
        liabilities: null as number | null,
        forecast: p.projected_net_worth,
      }));

      return [...historicalData, ...forecastData];
    }

    return historicalData;
  }, [snapshots, showForecast, forecast]);

  // Filter for net worth goals only, include required monthly rate
  const netWorthGoalLines = useMemo(() => {
    return netWorthGoals
      .filter((g) => g.goal.goal_type === "net_worth_target" && g.goal.is_active)
      .map((g) => ({
        name: g.goal.name,
        value: g.target_value,
        achieved: g.is_achieved,
        requiredMonthly: g.forecast?.required_monthly_change ?? null,
      }));
  }, [netWorthGoals]);

  if (snapshots.length === 0) {
    return (
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800 p-4">
        <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-4">
          Net Worth Over Time
        </div>
        <div className="h-64 flex items-center justify-center text-gray-500 dark:text-gray-400">
          No data to display
        </div>
      </div>
    );
  }

  const formatYAxis = (value: number) => {
    if (value >= 1000000) {
      return `${(value / 1000000).toFixed(1)}M €`;
    } else if (value >= 1000) {
      return `${(value / 1000).toFixed(0)}k €`;
    }
    return `${value} €`;
  };

  const CustomTooltip = ({
    active,
    payload,
    label,
  }: {
    active?: boolean;
    payload?: Array<{ value: number | null; dataKey: string }>;
    label?: string;
  }) => {
    if (active && payload && payload.length) {
      const netWorth = payload.find(p => p.dataKey === "netWorth")?.value;
      const forecast = payload.find(p => p.dataKey === "forecast")?.value;
      const assets = payload.find(p => p.dataKey === "assets")?.value;
      const liabilities = payload.find(p => p.dataKey === "liabilities")?.value;
      const isForecast = forecast !== null && netWorth === null;

      return (
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg p-3">
          <p className="font-medium text-gray-900 dark:text-gray-100 mb-2">
            {label}
            {isForecast && (
              <span className="ml-2 text-xs text-amber-600 dark:text-amber-400">
                (Projected)
              </span>
            )}
          </p>
          {isForecast ? (
            <p className="text-sm text-amber-600 dark:text-amber-400">
              Projected: {formatCurrency(forecast ?? 0)}
            </p>
          ) : (
            <>
              <p className="text-sm text-emerald-600 dark:text-emerald-400">
                Net Worth: {formatCurrency(netWorth ?? 0)}
              </p>
              <p className="text-sm text-blue-600 dark:text-blue-400">
                Assets: {formatCurrency(assets ?? 0)}
              </p>
              <p className="text-sm text-red-600 dark:text-red-400">
                Liabilities: {formatCurrency(liabilities ?? 0)}
              </p>
            </>
          )}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800 p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="text-sm font-medium text-gray-700 dark:text-gray-300">
          Net Worth Over Time
        </div>
        <div className="flex items-center gap-3">
          {showForecast && (
            <div className="flex items-center gap-1">
              {(Object.keys(PERIOD_LABELS) as ForecastPeriod[]).map((period) => (
                <button
                  key={period}
                  onClick={() => handlePeriodChange(period)}
                  className={`px-2 py-1 text-xs rounded ${
                    forecastPeriod === period
                      ? "bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300"
                      : "text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
                  }`}
                >
                  {PERIOD_LABELS[period]}
                </button>
              ))}
            </div>
          )}
          <button
            onClick={handleToggleForecast}
            className={`flex items-center gap-1.5 px-2 py-1 text-xs rounded transition-colors ${
              showForecast
                ? "bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300"
                : "text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
            }`}
          >
            <svg
              className="w-3.5 h-3.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"
              />
            </svg>
            Forecast
          </button>
        </div>
      </div>

      {showForecast && (
        <div className="mb-3 text-xs text-gray-500 dark:text-gray-400 flex flex-wrap items-center gap-x-4 gap-y-1">
          {forecastLoading && (
            <span className="text-amber-500">Loading forecast...</span>
          )}
          {forecastError && (
            <span className="text-red-500 dark:text-red-400">Failed to load forecast</span>
          )}
          {forecast && (
            <>
              <span className="inline-flex items-center gap-1">
                <span className="w-3 h-0.5 bg-amber-500" style={{ borderStyle: "dashed" }}></span>
                Current pace: {formatCurrency(forecast.monthly_change_rate)}/mo
              </span>
              {/* Show required pace only for the most behind-schedule goal */}
              {(() => {
                const behindGoals = netWorthGoalLines
                  .filter(g => !g.achieved && g.requiredMonthly && g.requiredMonthly > 0)
                  .sort((a, b) => (b.requiredMonthly ?? 0) - (a.requiredMonthly ?? 0));
                const mostUrgent = behindGoals[0];
                if (!mostUrgent) return null;
                const isOnTrack = forecast.monthly_change_rate >= mostUrgent.requiredMonthly!;
                return (
                  <span
                    className={`inline-flex items-center gap-1 ${
                      isOnTrack
                        ? "text-emerald-600 dark:text-emerald-400"
                        : "text-amber-600 dark:text-amber-400"
                    }`}
                  >
                    {mostUrgent.name}: {formatCurrency(mostUrgent.requiredMonthly!)}/mo needed
                  </span>
                );
              })()}
            </>
          )}
        </div>
      )}

      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={chartData}
            margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
          >
            <defs>
              <linearGradient id="netWorthGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#e5e7eb"
              className="dark:stroke-gray-700"
            />
            <XAxis
              dataKey="name"
              tick={{ fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              className="text-gray-600 dark:text-gray-400"
            />
            <YAxis
              tickFormatter={formatYAxis}
              tick={{ fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              width={60}
              className="text-gray-600 dark:text-gray-400"
            />
            <Tooltip content={<CustomTooltip />} />
            <Area
              type="monotone"
              dataKey="netWorth"
              stroke="#10b981"
              strokeWidth={2}
              fill="url(#netWorthGradient)"
              connectNulls={false}
            />
            {showForecast && (
              <Line
                type="monotone"
                dataKey="forecast"
                stroke="#f59e0b"
                strokeWidth={2}
                strokeDasharray="5 5"
                dot={false}
                connectNulls={true}
              />
            )}
            {netWorthGoalLines.map((goal, index) => (
              <ReferenceLine
                key={`goal-${index}`}
                y={goal.value}
                stroke={goal.achieved ? "#10b981" : "#f59e0b"}
                strokeDasharray="5 5"
                strokeWidth={2}
                label={{
                  value: goal.name,
                  position: "right",
                  fill: goal.achieved ? "#10b981" : "#f59e0b",
                  fontSize: 11,
                }}
              />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
