"use client";

import { useMemo } from "react";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from "recharts";
import type { Props as LegendProps } from "recharts/types/component/DefaultLegendContent";
import { NetWorthSnapshot } from "@/types";
import { formatCurrency } from "@/lib/utils";
import { useNetWorthGroups } from "@/hooks/useNetWorth";

interface AllocationChartProps {
  snapshot: NetWorthSnapshot | null;
}

// Fallback colors for groups without a color defined
const DEFAULT_COLORS = [
  "#3b82f6", // blue
  "#10b981", // emerald
  "#f59e0b", // amber
  "#8b5cf6", // violet
  "#ef4444", // red
  "#f97316", // orange
  "#06b6d4", // cyan
  "#ec4899", // pink
];

export function AllocationChart({ snapshot }: AllocationChartProps) {
  const { data: groups = [] } = useNetWorthGroups();

  // Build a map of group name -> color
  const groupColors = useMemo(() => {
    const colors: Record<string, string> = {};
    groups.forEach((group, index) => {
      colors[group.name] = group.color || DEFAULT_COLORS[index % DEFAULT_COLORS.length];
    });
    return colors;
  }, [groups]);

  const chartData = useMemo(() => {
    if (!snapshot?.by_group) return [];

    return Object.entries(snapshot.by_group)
      .filter(([, value]) => value > 0)
      .map(([groupName, value]) => ({
        name: groupName,
        value: value,
        color: groupColors[groupName] || DEFAULT_COLORS[0],
      }))
      .sort((a, b) => b.value - a.value);
  }, [snapshot, groupColors]);

  if (!snapshot || chartData.length === 0) {
    return (
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800 p-4">
        <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-4">
          Asset Allocation
        </div>
        <div className="h-64 flex items-center justify-center text-gray-500 dark:text-gray-400">
          No data to display
        </div>
      </div>
    );
  }

  const CustomTooltip = ({
    active,
    payload,
  }: {
    active?: boolean;
    payload?: Array<{ payload: { name: string; value: number; color: string } }>;
  }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      // Percentages use groupName_pct format
      const percentage = snapshot.percentages[`${data.name}_pct`] || 0;

      return (
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg p-3">
          <p className="font-medium text-gray-900 dark:text-gray-100">{data.name}</p>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            {formatCurrency(data.value)}
          </p>
          <p className="text-sm text-gray-500 dark:text-gray-500">
            {percentage.toFixed(1).replace(".", ",")} % of total
          </p>
        </div>
      );
    }
    return null;
  };

  const renderLegend = (props: LegendProps) => {
    const { payload } = props;
    if (!payload) return null;

    return (
      <div className="flex flex-wrap justify-center gap-x-4 gap-y-1 mt-2">
        {payload.map((entry, index) => (
          <div key={index} className="flex items-center gap-1.5 text-xs">
            <div
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: entry.color }}
            />
            <span className="text-gray-600 dark:text-gray-400">{String(entry.value)}</span>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800 p-4">
      <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-4">
        Asset Allocation
      </div>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              innerRadius={50}
              outerRadius={80}
              paddingAngle={2}
              dataKey="value"
            >
              {chartData.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={entry.color}
                  stroke="transparent"
                />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
            <Legend content={renderLegend} />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
