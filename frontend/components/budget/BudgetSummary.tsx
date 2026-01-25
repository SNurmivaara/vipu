"use client";

import { BudgetData } from "@/types";
import { formatCurrency, getBalanceColor, cn } from "@/lib/utils";

interface BudgetSummaryProps {
  data: BudgetData;
}

export function BudgetSummary({ data }: BudgetSummaryProps) {
  // Calculate separated totals
  const monthlyExpenses = data.expenses
    .filter((e) => !e.is_savings_goal)
    .reduce((sum, e) => sum + e.amount, 0);

  const savingsGoals = data.expenses
    .filter((e) => e.is_savings_goal)
    .reduce((sum, e) => sum + e.amount, 0);

  const currentBalance = data.totals.current_balance;
  const netIncome = data.totals.net_income;

  // Three financial states:
  // 1. Current Reality: Balance - Monthly Expenses (ignoring goals)
  const currentReality = currentBalance - monthlyExpenses;

  // 2. End of Month: Current + Net Income - Monthly Expenses
  const endOfMonth = currentBalance + netIncome - monthlyExpenses;

  // 3. Goal Distance: How much more needed to cover everything including goals
  const goalDistance = currentBalance + netIncome - monthlyExpenses - savingsGoals;

  return (
    <div className="grid gap-4 sm:grid-cols-3">
      {/* Current Reality */}
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800 p-4">
        <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">
          Current Position
        </div>
        <div
          className={cn("text-2xl font-bold", getBalanceColor(currentReality))}
        >
          {formatCurrency(currentReality)}
        </div>
        <div className="text-xs text-gray-500 dark:text-gray-400 mt-2">
          Balance minus monthly expenses
        </div>
      </div>

      {/* End of Month */}
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800 p-4">
        <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">
          After This Month
        </div>
        <div
          className={cn("text-2xl font-bold", getBalanceColor(endOfMonth))}
        >
          {formatCurrency(endOfMonth)}
        </div>
        <div className="text-xs text-gray-500 dark:text-gray-400 mt-2">
          Plus net income ({formatCurrency(netIncome)})
        </div>
      </div>

      {/* Goal Distance */}
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800 p-4">
        <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">
          With Savings Goals
        </div>
        <div
          className={cn("text-2xl font-bold", getBalanceColor(goalDistance))}
        >
          {formatCurrency(goalDistance)}
        </div>
        <div className="text-xs text-gray-500 dark:text-gray-400 mt-2">
          {savingsGoals > 0
            ? `Including ${formatCurrency(savingsGoals)} in goals`
            : "No savings goals set"}
        </div>
      </div>
    </div>
  );
}
