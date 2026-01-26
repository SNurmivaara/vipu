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

// Format month/year as compact "M/YY" (e.g., "1/25" for January 2025)
function formatMonthLabel(month: number, year: number): string {
  return `${month}/${String(year).slice(-2)}`;
}

// Aggregate data points for longer time scales
// Returns the sampling interval (1 = every point, 3 = quarterly, 12 = yearly)
function getAggregationInterval(dataLength: number, timeScale: TimeScale): number {
  // For very short scales, always show every point
  if (timeScale === "1m" || timeScale === "3m") {
    return 1;
  }

  // For 6M and 1Y, show every point unless we have too many
  if (timeScale === "6m" || timeScale === "1y") {
    if (dataLength > 24) {
      return 2; // Every other month if > 2 years of data
    }
    return 1;
  }

  // For 5Y scale, show quarterly (every 3 months)
  if (timeScale === "5y") {
    return 3;
  }

  // For Max scale, adapt based on data length
  if (dataLength > 60) {
    return 12; // Yearly for > 5 years of data
  } else if (dataLength > 24) {
    return 3; // Quarterly for > 2 years
  }
  return 1; // Monthly otherwise
}

// Time scales for filtering historical data
type TimeScale = "max" | "5y" | "1y" | "6m" | "3m" | "1m";

const TIME_SCALE_LABELS: Record<TimeScale, string> = {
  max: "Max",
  "5y": "5Y",
  "1y": "1Y",
  "6m": "6M",
  "3m": "3M",
  "1m": "1M",
};

// Historical months to show for each time scale
const TIME_SCALE_HISTORY_MONTHS: Record<TimeScale, number | null> = {
  max: null, // Show all history
  "5y": 60,
  "1y": 12,
  "6m": 6,
  "3m": 3,
  "1m": 1,
};

// Forecast period type for API calls
const TIME_SCALE_FORECAST_PERIOD: Record<TimeScale, ForecastPeriod> = {
  max: "year",
  "5y": "year",
  "1y": "year",
  "6m": "half_year",
  "3m": "quarter",
  "1m": "month",
};

const STORAGE_KEY = "vipu-chart-settings";

interface ChartSettings {
  showForecast: boolean;
  timeScale: TimeScale;
}

function loadChartSettings(): ChartSettings {
  if (typeof window === "undefined") {
    return { showForecast: false, timeScale: "1y" };
  }
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      return {
        showForecast: parsed.showForecast ?? false,
        timeScale: parsed.timeScale ?? "1y",
      };
    }
  } catch {
    // Ignore parse errors
  }
  return { showForecast: false, timeScale: "1y" };
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
  const [timeScale, setTimeScale] = useState<TimeScale>("1y");
  const [isHydrated, setIsHydrated] = useState(false);

  // Derive forecast period from time scale
  const forecastPeriod = TIME_SCALE_FORECAST_PERIOD[timeScale];

  // Load settings from localStorage after hydration
  useEffect(() => {
    const settings = loadChartSettings();
    setShowForecast(settings.showForecast);
    setTimeScale(settings.timeScale);
    setIsHydrated(true);
  }, []);

  // Save settings when they change (after initial hydration)
  useEffect(() => {
    if (isHydrated) {
      saveChartSettings({ showForecast, timeScale });
    }
  }, [showForecast, timeScale, isHydrated]);

  const handleToggleForecast = useCallback(() => {
    setShowForecast((prev) => !prev);
  }, []);

  const handleTimeScaleChange = useCallback((scale: TimeScale) => {
    setTimeScale(scale);
  }, []);

  // Determine which time scales are available based on data
  const availableScales = useMemo(() => {
    if (snapshots.length === 0) return [];
    const totalMonths = snapshots.length;
    const scales: TimeScale[] = [];

    // Always show Max if we have data
    scales.push("max");

    // Add scales that have enough data (or close to it)
    if (totalMonths >= 24) scales.push("5y"); // Show 5Y if at least 2 years
    if (totalMonths >= 6) scales.push("1y");  // Show 1Y if at least 6 months
    if (totalMonths >= 3) scales.push("6m");  // Show 6M if at least 3 months
    if (totalMonths >= 2) scales.push("3m");  // Show 3M if at least 2 months
    scales.push("1m"); // Always show 1M

    return scales;
  }, [snapshots.length]);

  // Calculate months ahead for forecast - match the history length
  const forecastMonthsAhead = useMemo(() => {
    const historyMonths = TIME_SCALE_HISTORY_MONTHS[timeScale];
    if (historyMonths === null) return 12; // Default for "max"
    return historyMonths;
  }, [timeScale]);

  const { data: forecast, isLoading: forecastLoading, isError: forecastError } = useQuery({
    queryKey: ["forecast", forecastPeriod, forecastMonthsAhead],
    queryFn: () => fetchForecast({
      period: forecastPeriod,
      months_ahead: forecastMonthsAhead
    }),
    enabled: showForecast && snapshots.length > 0,
  });

  const chartData = useMemo(() => {
    const historyMonthsLimit = TIME_SCALE_HISTORY_MONTHS[timeScale];

    // Slice snapshots based on time scale (they come newest-first)
    const filteredSnapshots = historyMonthsLimit === null
      ? snapshots
      : snapshots.slice(0, Math.min(historyMonthsLimit, snapshots.length));

    // Reverse to get oldest-first order
    const chronologicalSnapshots = [...filteredSnapshots].reverse();

    // Calculate total data points (history + forecast if enabled)
    const forecastLength = (showForecast && forecast?.projections) ? forecast.projections.length : 0;
    const totalDataPoints = chronologicalSnapshots.length + forecastLength;

    // Determine aggregation interval based on total data points
    const interval = getAggregationInterval(totalDataPoints, timeScale);

    // Sample data points at the interval, always including the last point
    const sampledSnapshots = chronologicalSnapshots.filter((_, index, arr) => {
      // Always include first point
      if (index === 0) return true;
      // Always include last point (most recent)
      if (index === arr.length - 1) return true;
      // Include points at the interval
      return index % interval === 0;
    });

    const historicalData = sampledSnapshots.map((snapshot) => ({
      name: formatMonthLabel(snapshot.month, snapshot.year),
      netWorth: snapshot.net_worth,
      assets: snapshot.total_assets,
      liabilities: Math.abs(snapshot.total_liabilities),
      forecast: null as number | null,
    }));

    // Add forecast data if enabled - append all forecast months after history
    if (showForecast && forecast?.projections) {
      // Connect the forecast line to the last historical point
      if (historicalData.length > 0 && forecast.projections.length > 0) {
        const lastHistorical = historicalData[historicalData.length - 1];
        lastHistorical.forecast = lastHistorical.netWorth;
      }

      // Sample forecast at same interval for consistency
      const sampledForecast = forecast.projections.filter((_, index, arr) => {
        if (index === 0) return true;
        if (index === arr.length - 1) return true;
        return index % interval === 0;
      });

      const forecastData = sampledForecast.map((p) => ({
        name: formatMonthLabel(p.month, p.year),
        netWorth: null as number | null,
        assets: null as number | null,
        liabilities: null as number | null,
        forecast: p.projected_net_worth,
      }));

      return [...historicalData, ...forecastData];
    }

    return historicalData;
  }, [snapshots, showForecast, forecast, timeScale]);

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
          {/* Time scale selector */}
          <div className="flex items-center gap-1">
            {availableScales.map((scale) => (
              <button
                key={scale}
                onClick={() => handleTimeScaleChange(scale)}
                className={`px-2 py-1 text-xs rounded ${
                  timeScale === scale
                    ? "bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300"
                    : "text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
                }`}
              >
                {TIME_SCALE_LABELS[scale]}
              </button>
            ))}
          </div>
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
              vertical={false}
            />
            <XAxis
              dataKey="name"
              tick={{ fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              interval={0}
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
