"use client";

import { BudgetData } from "@/types";
import {
  formatCurrency,
  formatDateShort,
  getBalanceColor,
  cn,
} from "@/lib/utils";

interface BudgetSummaryProps {
  data: BudgetData;
}

export function BudgetSummary({ data }: BudgetSummaryProps) {
  const {
    current_balance,
    expenses_before_payday,
    income_before_payday,
    savings_before_payday,
    cc_payments_before_payday,
    next_payday,
    next_period_end,
    expenses_next_period,
    savings_next_period,
    cc_payments_next_period,
    income_next_period,
  } = data.totals;

  // Total obligations before next payday (expenses + savings + CC payments)
  const obligationsBeforePayday =
    expenses_before_payday + savings_before_payday + cc_payments_before_payday;

  // Three financial states (deadline-aware):
  // 1. Current Position: Balance minus ALL obligations due before next payday
  const currentPosition = current_balance - obligationsBeforePayday;

  // 2. After Next Payday: Current position plus income arriving before payday
  const afterPayday = currentPosition + income_before_payday;

  // 3. Next Month Preview: After payday plus next period income minus next period obligations
  const nextPeriodObligations =
    expenses_next_period + savings_next_period + cc_payments_next_period;
  const nextMonthPreview = afterPayday + income_next_period - nextPeriodObligations;

  return (
    <div className="grid gap-4 sm:grid-cols-3">
      {/* Current Position */}
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800 p-4">
        <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">
          Current Position
        </div>
        <div
          className={cn("text-2xl font-bold", getBalanceColor(currentPosition))}
        >
          {formatCurrency(currentPosition)}
        </div>
        <div className="text-sm text-gray-500 dark:text-gray-400 mt-2">
          After {formatCurrency(obligationsBeforePayday)} due by{" "}
          {formatDateShort(next_payday)}
        </div>
      </div>

      {/* After Next Payday */}
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800 p-4">
        <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">
          After Next Payday
        </div>
        <div
          className={cn("text-2xl font-bold", getBalanceColor(afterPayday))}
        >
          {formatCurrency(afterPayday)}
        </div>
        <div className="text-sm text-gray-500 dark:text-gray-400 mt-2">
          Plus {formatCurrency(income_before_payday)} income
        </div>
      </div>

      {/* Next Month Preview */}
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800 p-4">
        <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">
          Next Month Preview
        </div>
        <div
          className={cn("text-2xl font-bold", getBalanceColor(nextMonthPreview))}
        >
          {formatCurrency(nextMonthPreview)}
        </div>
        <div className="text-sm text-gray-500 dark:text-gray-400 mt-2">
          {nextPeriodObligations > 0
            ? `Minus ${formatCurrency(nextPeriodObligations)} due by ${formatDateShort(next_period_end)}`
            : "No obligations next period"}
        </div>
      </div>
    </div>
  );
}
