"use client";

import { BudgetData } from "@/types";
import { cn, formatCurrency, formatDateShort, getBalanceColor } from "@/lib/utils";
import { CollapsibleSection } from "./CollapsibleSection";

interface BudgetSummaryProps {
  data: BudgetData;
}

/**
 * The front page projects the actual periods ahead rather than a smoothed
 * monthly rate: real cash, the real bills falling due, and each card's balance
 * leaving on its own due day. A rate would answer "what does a typical month
 * look like", which is an analytics question; this answers "what happens next".
 */
export function BudgetSummary({ data }: BudgetSummaryProps) {
  const {
    cash_balance,
    card_debt,
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
    unallocated_next_period,
  } = data.totals;

  // Cash on hand carried forward through each period. Card debt is not netted
  // off up front: it leaves the account on the card's due day, which is when it
  // actually stops being spendable.
  const billsBeforePayday = expenses_before_payday + savings_before_payday;
  const atPayday =
    cash_balance +
    income_before_payday -
    billsBeforePayday -
    cc_payments_before_payday;

  const billsNextPeriod = expenses_next_period + savings_next_period;
  const endOfNextPeriod =
    atPayday + income_next_period - billsNextPeriod - cc_payments_next_period;

  // Owing more on the cards than there is cash to cover them is worth saying
  // out loud: every projection below is being paid for out of a hole.
  const inTheHole = current_balance < 0;

  // Spare money is only genuinely spare if the period it belongs to ends with
  // the account in the black.
  const sweepable = endOfNextPeriod >= 0;

  return (
    <CollapsibleSection
      title="You have now"
      total={formatCurrency(current_balance)}
      totalClassName={cn(
        "font-semibold",
        inTheHole
          ? getBalanceColor(current_balance)
          : "text-gray-900 dark:text-gray-100"
      )}
      defaultOpen
    >
      <div className="px-4 py-2.5 space-y-2">
        <div className="flex items-baseline justify-between gap-3 text-sm">
          <span className="text-gray-600 dark:text-gray-400">Cash</span>
          <span className="text-gray-900 dark:text-gray-100">
            {formatCurrency(cash_balance)}
          </span>
        </div>
        <div className="flex items-baseline justify-between gap-3 text-sm">
          <span className="text-gray-600 dark:text-gray-400">
            Owed on cards
            <span className="ml-1.5 text-xs text-gray-400 dark:text-gray-500">
              leaves on each card&apos;s due day
            </span>
          </span>
          <span className="text-gray-900 dark:text-gray-100">
            {formatCurrency(card_debt)}
          </span>
        </div>

        {inTheHole && (
          <p className="text-xs text-red-600 dark:text-red-400">
            The cards owe {formatCurrency(-card_debt)} against{" "}
            {formatCurrency(cash_balance)} of cash, so this period starts{" "}
            {formatCurrency(-current_balance)} in the hole.
          </p>
        )}

        <div className="pt-1 space-y-2 border-t border-gray-100 dark:border-gray-800">
          <PositionRow
            label="At payday"
            date={next_payday}
            value={atPayday}
            detail={flowDetail([
              [income_before_payday, "pay"],
              [-billsBeforePayday, "bills"],
              [-cc_payments_before_payday, "cards"],
            ])}
          />
          <PositionRow
            label="End of next period"
            date={next_period_end}
            value={endOfNextPeriod}
            valueClassName={
              endOfNextPeriod < 0 ? getBalanceColor(endOfNextPeriod) : undefined
            }
            detail={flowDetail([
              [income_next_period, "pay"],
              [-billsNextPeriod, "bills"],
              [-cc_payments_next_period, "cards"],
            ])}
          />
        </div>

        {/* The point of the whole card: what next period doesn't need, and can
            therefore be swept somewhere it earns. Money is only free to move
            once the period it belongs to ends in the black — otherwise it is
            already spoken for by the shortfall. */}
        <div className="pt-2 flex items-baseline justify-between gap-3 border-t border-gray-100 dark:border-gray-800">
          <div className="min-w-0">
            <div className="text-sm text-gray-600 dark:text-gray-400">
              Unallocated next period
            </div>
            <div className="text-xs text-gray-400 dark:text-gray-500">
              {unallocated_next_period <= 0
                ? "next period doesn't cover itself"
                : sweepable
                  ? "free to move to savings on payday"
                  : "needed to cover the shortfall first"}
            </div>
          </div>
          <span
            className={cn(
              "text-sm font-semibold whitespace-nowrap",
              unallocated_next_period <= 0
                ? getBalanceColor(unallocated_next_period)
                : sweepable
                  ? "text-emerald-700 dark:text-emerald-400"
                  : "text-gray-600 dark:text-gray-400"
            )}
          >
            {formatCurrency(unallocated_next_period)}
          </span>
        </div>
      </div>
    </CollapsibleSection>
  );
}

/** "+4 575,00 € pay · −1 900,00 € bills · −200,00 € cards", zeroes omitted */
function flowDetail(parts: [number, string][]): string {
  const shown = parts
    .filter(([amount]) => amount !== 0)
    .map(
      ([amount, label]) =>
        `${amount > 0 ? "+" : "−"}${formatCurrency(Math.abs(amount))} ${label}`
    );
  return shown.length > 0 ? shown.join(" · ") : "nothing due";
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
          valueClassName ?? "text-gray-600 dark:text-gray-400"
        )}
      >
        {formatCurrency(value)}
      </span>
    </div>
  );
}
