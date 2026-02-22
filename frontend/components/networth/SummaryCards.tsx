"use client";

import { NetWorthSnapshot } from "@/types";
import { formatCurrencyRounded, cn, getBalanceColor } from "@/lib/utils";

interface SummaryCardsProps {
  snapshots: NetWorthSnapshot[];
}

export function SummaryCards({ snapshots }: SummaryCardsProps) {
  const latest = snapshots[0];

  if (!latest) {
    return (
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800 p-4">
          <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">
            Net Worth
          </div>
          <div className="text-2xl font-bold text-gray-400 dark:text-gray-500">
            No data
          </div>
        </div>
        <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800 p-4">
          <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">
            Monthly Change
          </div>
          <div className="text-2xl font-bold text-gray-400 dark:text-gray-500">
            No data
          </div>
        </div>
        <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800 p-4">
          <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">
            Personal / Company
          </div>
          <div className="text-2xl font-bold text-gray-400 dark:text-gray-500">
            No data
          </div>
        </div>
      </div>
    );
  }

  const changePercent =
    latest.net_worth !== 0 && latest.change_from_previous !== 0
      ? ((latest.change_from_previous / (latest.net_worth - latest.change_from_previous)) * 100)
      : 0;

  const changeColor =
    latest.change_from_previous > 0
      ? "text-emerald-700 dark:text-emerald-400"
      : latest.change_from_previous < 0
        ? "text-red-600 dark:text-red-400"
        : "text-gray-600 dark:text-gray-400";

  const changePrefix = latest.change_from_previous > 0 ? "+" : "";

  return (
    <div className="grid gap-4 sm:grid-cols-3">
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800 p-4">
        <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">
          Net Worth
        </div>
        <div
          className={cn("text-2xl font-bold", getBalanceColor(latest.net_worth))}
        >
          {formatCurrencyRounded(latest.net_worth)}
        </div>
        <div className="text-sm mt-2 space-y-0.5">
          <div className="text-emerald-600 dark:text-emerald-400">
            {formatCurrencyRounded(latest.total_assets)} assets
          </div>
          <div className="text-red-600 dark:text-red-400">
            {formatCurrencyRounded(Math.abs(latest.total_liabilities))} liabilities
          </div>
        </div>
      </div>

      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800 p-4">
        <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">
          Monthly Change
        </div>
        <div className={cn("text-2xl font-bold", changeColor)}>
          {changePrefix}
          {formatCurrencyRounded(latest.change_from_previous)}
        </div>
        <div className="text-sm text-gray-500 dark:text-gray-400 mt-2">
          {changePrefix}
          {changePercent.toFixed(1).replace(".", ",")} % from previous
        </div>
      </div>

      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800 p-4">
        <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">
          Personal / Company
        </div>
        <div className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          {formatCurrencyRounded(latest.personal_wealth)}
        </div>
        <div className="text-sm text-gray-500 dark:text-gray-400 mt-2">
          Company: {formatCurrencyRounded(latest.company_wealth)}
        </div>
      </div>
    </div>
  );
}
