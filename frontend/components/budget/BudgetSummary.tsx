"use client";

import { BudgetData } from "@/types";
import { cn, formatCurrency, formatDateShort, getBalanceColor } from "@/lib/utils";
import { CollapsibleSection } from "./CollapsibleSection";

interface BudgetSummaryProps {
  data: BudgetData;
}

export function BudgetSummary({ data }: BudgetSummaryProps) {
  const {
    current_balance,
    expenses_before_payday,
    income_before_payday,
    savings_before_payday,
    next_payday,
    next_period_end,
    expenses_next_period,
    savings_next_period,
  } = data.totals;

  // Total obligations before next payday (expenses + savings).
  // CC payments excluded: they are internal transfers already reflected in current_balance.
  // Bills due today (or earlier) are excluded by the backend — they're assumed paid —
  // so this is genuinely "what's still due before payday".
  const obligationsBeforePayday = expenses_before_payday + savings_before_payday;

  // Three projected balances, anchored to the actual current balance:
  // 1. Before payday: balance minus the obligations still due before next payday
  const currentPosition = current_balance - obligationsBeforePayday;

  // 2. After payday: plus the income arriving up to and including payday.
  //    This is the money that has to carry you through the WHOLE next period.
  const afterPayday = currentPosition + income_before_payday;

  // 3. End of next period: next period's bills come due BEFORE the paycheck that
  //    lands at the period end (income_next_period), so they have to be paid out of
  //    the after-payday balance. We deliberately do NOT add that period-end paycheck
  //    here — counting it would hide whether you can actually afford the period.
  //    A negative result means after-payday money can't cover next period's bills.
  const nextPeriodObligations = expenses_next_period + savings_next_period;
  const endOfNextPeriod = afterPayday - nextPeriodObligations;

  return (
    <CollapsibleSection
      title="You have now"
      total={formatCurrency(current_balance)}
      totalClassName="font-semibold text-gray-900 dark:text-gray-100"
      defaultOpen
    >
      {/* Projected balance at each upcoming moment — smaller, muted extra info. */}
      <div className="px-4 py-2.5 space-y-2">
        <PositionRow
          label="Before payday"
          date={next_payday}
          value={currentPosition}
          detail={
            obligationsBeforePayday > 0
              ? `−${formatCurrency(obligationsBeforePayday)} bills still due`
              : "Nothing left to pay before payday"
          }
        />
        <PositionRow
          label="After payday"
          date={next_payday}
          value={afterPayday}
          detail={`+${formatCurrency(income_before_payday)} pay`}
        />
        <PositionRow
          label="End of next period"
          date={next_period_end}
          value={endOfNextPeriod}
          // Flag a shortfall: if next period's bills can't be covered by the
          // after-payday balance, show the gap in a warning colour.
          valueClassName={
            endOfNextPeriod < 0 ? getBalanceColor(endOfNextPeriod) : undefined
          }
          detail={
            nextPeriodObligations > 0
              ? endOfNextPeriod < 0
                ? `−${formatCurrency(nextPeriodObligations)} bills · ${formatCurrency(-endOfNextPeriod)} short`
                : `−${formatCurrency(nextPeriodObligations)} bills`
              : "No bills next period"
          }
        />
      </div>
    </CollapsibleSection>
  );
}

interface PositionRowProps {
  label: string;
  /** ISO date string for the moment this balance is projected to */
  date: string;
  value: number;
  /** Sub-line explaining the change from the line above */
  detail: string;
  /** Optional override for the value's text colour (defaults to muted gray) */
  valueClassName?: string;
}

function PositionRow({
  label,
  date,
  value,
  detail,
  valueClassName,
}: PositionRowProps) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <div className="min-w-0">
        <div className="text-sm text-gray-600 dark:text-gray-400">
          {label}
          <span className="ml-1.5 text-xs text-gray-400 dark:text-gray-500">
            {formatDateShort(date)}
          </span>
        </div>
        <div className="text-xs text-gray-400 dark:text-gray-500">{detail}</div>
      </div>
      <span
        className={cn(
          "text-sm font-medium whitespace-nowrap",
          valueClassName ?? "text-gray-600 dark:text-gray-400",
        )}
      >
        {formatCurrency(value)}
      </span>
    </div>
  );
}
