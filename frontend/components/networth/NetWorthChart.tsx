"use client";

import { useMemo } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { NetWorthSnapshot, GoalProgress } from "@/types";
import { formatCurrency } from "@/lib/utils";

interface NetWorthChartProps {
  snapshots: NetWorthSnapshot[];
  netWorthGoals?: GoalProgress[];
}

const MONTH_NAMES = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
];

export function NetWorthChart({ snapshots, netWorthGoals = [] }: NetWorthChartProps) {
  const chartData = useMemo(() => {
    return [...snapshots]
      .reverse()
      .map((snapshot) => ({
        name: `${MONTH_NAMES[snapshot.month - 1]} ${snapshot.year}`,
        netWorth: snapshot.net_worth,
        assets: snapshot.total_assets,
        liabilities: Math.abs(snapshot.total_liabilities),
      }));
  }, [snapshots]);

  // Filter for net worth goals only
  const netWorthGoalLines = useMemo(() => {
    return netWorthGoals
      .filter((g) => g.goal.goal_type === "net_worth" && g.goal.is_active)
      .map((g) => ({
        name: g.goal.name,
        value: g.target_value,
        achieved: g.is_achieved,
      }));
  }, [netWorthGoals]);

  if (chartData.length === 0) {
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
    payload?: Array<{ value: number; dataKey: string }>;
    label?: string;
  }) => {
    if (active && payload && payload.length) {
      const netWorth = payload.find(p => p.dataKey === "netWorth")?.value ?? 0;
      const assets = payload.find(p => p.dataKey === "assets")?.value ?? 0;
      const liabilities = payload.find(p => p.dataKey === "liabilities")?.value ?? 0;

      return (
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg p-3">
          <p className="font-medium text-gray-900 dark:text-gray-100 mb-2">{label}</p>
          <p className="text-sm text-emerald-600 dark:text-emerald-400">
            Net Worth: {formatCurrency(netWorth)}
          </p>
          <p className="text-sm text-blue-600 dark:text-blue-400">
            Assets: {formatCurrency(assets)}
          </p>
          <p className="text-sm text-red-600 dark:text-red-400">
            Liabilities: {formatCurrency(liabilities)}
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800 p-4">
      <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-4">
        Net Worth Over Time
      </div>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
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
            />
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
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
