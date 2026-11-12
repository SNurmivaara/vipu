"use client";

import { ReactNode } from "react";
import { BudgetData, PeriodFlow } from "@/types";
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
 *
 * Each period is laid out as a sum: its pay, bills and card payments, then the
 * line they add up to. A figure that surprises the reader can be traced to the
 * movement behind it without leaving the card.
 */
export function BudgetSummary({ data }: BudgetSummaryProps) {
  const {
    cash_balance,
    card_debt,
    current_balance,
    cash_low_point: low,
    period_current: current,
    period_next: next,
  } = data.totals;

  // Cash on hand carried forward through each period. Card debt is not netted
  // off up front: it leaves the account on the card's due day, which is when it
  // actually stops being spendable.
  const atPayday = cash_balance + current.money_in - current.money_out;
  const endOfNextPeriod = atPayday + next.money_in - next.money_out;

  // Owing more on the cards than there is cash to cover them is worth saying
  // out loud: every projection below is being paid for out of a hole.
  const inTheHole = current_balance < 0;

  // Spare money is only genuinely spare if the period it belongs to ends with
  // the account in the black.
  const sweepable = endOfNextPeriod >= 0;

  // The balance can go under between two comfortable endpoints, because bills
  // land on their own days and pay lands on one. The low point only earns a
  // row when it is below every balance already shown.
  const dipsBetween = low.balance < Math.min(cash_balance, atPayday, endOfNextPeriod);

  const currentHasMovements = flowLines(current).length > 0;

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
      <div className="px-4 py-2.5 space-y-3">
        <p className="text-xs text-gray-500 dark:text-gray-400">
          {formatCurrency(cash_balance)} cash
          {card_debt !== 0 && <> · {formatCurrency(card_debt)} on cards</>}
        </p>

        {inTheHole && (
          <p className="text-xs text-red-600 dark:text-red-400">
            The cards owe {formatCurrency(-card_debt)} against{" "}
            {formatCurrency(cash_balance)} of cash, so this period starts{" "}
            {formatCurrency(-current_balance)} in the hole.
          </p>
        )}

        {low.balance < 0 && (
          <p className="text-xs text-red-600 dark:text-red-400">
            Cash runs out on {formatDateShort(low.date)}, short{" "}
            {formatCurrency(-low.balance)}. Bills land before the pay that
            covers them.
          </p>
        )}

        {dipsBetween && (
          <Line
            label={
              <>
                Lowest point
                <DateNote date={low.date} />
              </>
            }
            value={low.balance}
            valueClassName={low.balance < 0 ? getBalanceColor(low.balance) : undefined}
          />
        )}

        <PeriodBlock
          title="Until payday"
          dates={formatDateShort(current.end)}
          period={current}
          aside={currentHasMovements ? undefined : "nothing due"}
        >
          {currentHasMovements && (
            <Line
              label="At payday"
              value={atPayday}
              strong
              valueClassName={atPayday < 0 ? getBalanceColor(atPayday) : undefined}
            />
          )}
        </PeriodBlock>

        <PeriodBlock
          title="Next period"
          dates={`${formatDateShort(next.start)} – ${formatDateShort(next.end)}`}
          period={next}
        >
          {/* Colour carries the sweep verdict: green when the period ends in
              the black and the amount can move to savings on payday, gray when
              a shortfall at the end of the period already needs it, and the
              balance colour when the period does not cover itself. */}
          <Line
            label="Unallocated"
            value={next.net}
            strong
            valueClassName={
              next.net <= 0
                ? getBalanceColor(next.net)
                : sweepable
                  ? "text-emerald-700 dark:text-emerald-400"
                  : "text-gray-600 dark:text-gray-400"
            }
          />
          <Line
            label="Cash at the end"
            value={endOfNextPeriod}
            valueClassName={
              endOfNextPeriod < 0 ? getBalanceColor(endOfNextPeriod) : undefined
            }
          />
        </PeriodBlock>
      </div>
    </CollapsibleSection>
  );
}

/** A period's movements as signed lines, zero amounts omitted. */
function flowLines(period: PeriodFlow): [string, number][] {
  const lines: [string, number][] = [
    ["Pay", period.money_in],
    ["Bills", -(period.bills + period.savings)],
    ["Cards", -period.card_payments],
  ];
  return lines.filter(([, amount]) => amount !== 0);
}

interface PeriodBlockProps {
  title: string;
  dates: string;
  period: PeriodFlow;
  /** Shown beside the title when the period has nothing to list */
  aside?: string;
  /** The lines the movements add up to */
  children?: ReactNode;
}

function PeriodBlock({ title, dates, period, aside, children }: PeriodBlockProps) {
  const lines = flowLines(period);

  return (
    <section
      aria-label={title}
      className="pt-2 space-y-1 border-t border-gray-100 dark:border-gray-800"
    >
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-sm text-gray-900 dark:text-gray-100">
          {title}
          <span className="ml-1.5 text-xs text-gray-400 dark:text-gray-500">
            {dates}
          </span>
        </h3>
        {aside && (
          <span className="text-xs text-gray-400 dark:text-gray-500">{aside}</span>
        )}
      </div>

      {lines.map(([label, amount]) => (
        <Line key={label} label={label} value={amount} signed muted />
      ))}

      {children && (
        <div
          className={cn(
            "space-y-1",
            lines.length > 0 && "pt-1 border-t border-dashed border-gray-200 dark:border-gray-700"
          )}
        >
          {children}
        </div>
      )}
    </section>
  );
}

interface LineProps {
  label: ReactNode;
  value: number;
  /** Prefix positive amounts with "+", for movements in a sum */
  signed?: boolean;
  /** A total line, set in a heavier weight */
  strong?: boolean;
  /** A movement line, set smaller and lighter than the totals */
  muted?: boolean;
  /** Overrides the value's text colour */
  valueClassName?: string;
}

function Line({ label, value, signed, strong, muted, valueClassName }: LineProps) {
  return (
    <div
      className={cn(
        "flex items-baseline justify-between gap-3",
        muted ? "text-xs" : "text-sm"
      )}
    >
      <span className="text-gray-600 dark:text-gray-400">{label}</span>
      <span
        className={cn(
          "whitespace-nowrap tabular-nums",
          strong ? "font-semibold" : "font-medium",
          valueClassName ??
            (muted
              ? "text-gray-500 dark:text-gray-400"
              : "text-gray-900 dark:text-gray-100")
        )}
      >
        {signed && value > 0 ? "+" : ""}
        {formatCurrency(value)}
      </span>
    </div>
  );
}

function DateNote({ date }: { date: string }) {
  return (
    <span className="ml-1.5 text-xs text-gray-400 dark:text-gray-500">
      {formatDateShort(date)}
    </span>
  );
}
