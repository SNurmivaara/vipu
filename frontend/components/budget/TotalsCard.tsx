"use client";

import { BudgetTotals } from "@/types";
import { formatCurrency, getBalanceColor, cn } from "@/lib/utils";

interface TotalsCardProps {
  totals: BudgetTotals;
}

export function TotalsCard({ totals }: TotalsCardProps) {
  return (
    <section className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800">
      <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-800">
        <h2 className="font-semibold text-gray-900 dark:text-gray-100">
          Summary
        </h2>
      </div>
      <div className="p-4 space-y-3">
        <div className="flex justify-between items-center">
          <span className="text-gray-600 dark:text-gray-400">Gross Income</span>
          <span className="font-medium text-gray-900 dark:text-gray-100">
            {formatCurrency(totals.gross_income)}
          </span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-gray-600 dark:text-gray-400">Net Income</span>
          <span className="font-medium text-gray-900 dark:text-gray-100">
            {formatCurrency(totals.net_income)}
          </span>
        </div>
        <div className="border-t border-gray-100 dark:border-gray-800 pt-3">
          <div className="flex justify-between items-center">
            <span className="text-gray-600 dark:text-gray-400">
              Current Balance
            </span>
            <span
              className={cn(
                "font-medium",
                getBalanceColor(totals.current_balance)
              )}
            >
              {formatCurrency(totals.current_balance)}
            </span>
          </div>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-gray-600 dark:text-gray-400">
            Monthly Expenses
          </span>
          <span className="font-medium text-gray-900 dark:text-gray-100">
            {formatCurrency(totals.total_expenses)}
          </span>
        </div>
        <div className="border-t border-gray-200 dark:border-gray-700 pt-3">
          <div className="flex justify-between items-center">
            <span className="font-semibold text-gray-900 dark:text-gray-100">
              Net Position
            </span>
            <span
              className={cn(
                "text-lg font-bold",
                getBalanceColor(totals.net_position)
              )}
            >
              {formatCurrency(totals.net_position)}
            </span>
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Balance after covering monthly expenses
          </p>
        </div>
      </div>
    </section>
  );
}
