"use client";

import { useMemo } from "react";
import {
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ComposedChart,
} from "recharts";
import { BudgetSnapshot } from "@/types";
import { formatCurrency } from "@/lib/utils";

interface BudgetChartProps {
  snapshots: BudgetSnapshot[];
}

function formatDateLabel(dateStr: string): string {
  const d = new Date(dateStr);
  return `${d.getDate()}/${d.getMonth() + 1}`;
}

export function BudgetChart({ snapshots }: BudgetChartProps) {
  const chartData = useMemo(() => {
    return [...snapshots].reverse().map((s) => ({
      name: formatDateLabel(s.date),
      balance: s.current_balance,
      change: s.change_from_previous,
    }));
  }, [snapshots]);

  const xAxisInterval = useMemo(() => {
    const len = chartData.length;
    if (len <= 8) return 0;
    if (len <= 16) return 1;
    return Math.floor(len / 8) - 1;
  }, [chartData.length]);

  if (snapshots.length === 0) {
    return null;
  }

  const formatYAxis = (value: number) => {
    if (Math.abs(value) >= 1000000) {
      return `${(value / 1000000).toFixed(1)}M €`;
    } else if (Math.abs(value) >= 1000) {
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
    payload?: Array<{
      value: number;
      dataKey: string;
      payload: { balance: number; change: number };
    }>;
    label?: string;
  }) => {
    if (active && payload && payload.length) {
      const dataPoint = payload[0]?.payload;
      if (!dataPoint) return null;
      const changePrefix = dataPoint.change > 0 ? "+" : "";

      return (
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg p-3">
          <p className="font-medium text-gray-900 dark:text-gray-100 mb-2">
            {label}
          </p>
          <p className="text-sm text-blue-600 dark:text-blue-400">
            Balance: {formatCurrency(dataPoint.balance)}
          </p>
          {dataPoint.change !== 0 && (
            <p className={`text-sm ${dataPoint.change >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"}`}>
              Change: {changePrefix}{formatCurrency(dataPoint.change)}
            </p>
          )}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800 p-4">
      <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-4">
        Budget Trend
      </div>
      <div className="h-48" role="img" aria-label="Budget trend chart">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={chartData}
            margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
          >
            <defs>
              <linearGradient id="balanceGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
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
              tick={{ fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              interval={xAxisInterval}
              className="text-gray-600 dark:text-gray-400"
            />
            <YAxis
              tickFormatter={formatYAxis}
              tick={{ fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              width={65}
              domain={["dataMin", "auto"]}
              className="text-gray-600 dark:text-gray-400"
            />
            <Tooltip content={<CustomTooltip />} />
            <Area
              type="monotone"
              dataKey="balance"
              stroke="#3b82f6"
              strokeWidth={2}
              fill="url(#balanceGradient)"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
