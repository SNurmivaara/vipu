import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BudgetData, PeriodFlow } from "@/types";
import { formatCurrency } from "@/lib/utils";

import { BudgetSummary } from "./BudgetSummary";

// Example figures only.
function period(
  start: string,
  end: string,
  flows: Partial<Pick<PeriodFlow, "money_in" | "bills" | "savings" | "card_payments">>
): PeriodFlow {
  const money_in = flows.money_in ?? 0;
  const bills = flows.bills ?? 0;
  const savings = flows.savings ?? 0;
  const card_payments = flows.card_payments ?? 0;
  const money_out = bills + savings + card_payments;
  return {
    start,
    end,
    income: money_in,
    deductions: 0,
    bills,
    savings,
    card_payments,
    money_in,
    money_out,
    net: money_in - money_out,
  };
}

function budget(totals: {
  cash: number;
  cards: number;
  current: PeriodFlow;
  next: PeriodFlow;
  low: { date: string; balance: number };
}): BudgetData {
  return {
    totals: {
      cash_balance: totals.cash,
      card_debt: totals.cards,
      current_balance: totals.cash + totals.cards,
      cash_low_point: totals.low,
      period_current: totals.current,
      period_next: totals.next,
    },
  } as unknown as BudgetData;
}

/**
 * The amount printed beside a line's label. Compared as raw text: the fi-FI
 * currency format separates thousands with a non-breaking space, which
 * toHaveTextContent normalises on one side of the comparison only.
 */
function amountOf(scope: ReturnType<typeof within>, label: string): string {
  return scope.getByText(label).nextSibling?.textContent ?? "";
}

const quietCurrentPeriod = period("2026-11-12", "2026-11-15", {});
const nextPeriod = period("2026-11-15", "2026-12-15", {
  money_in: 3000,
  bills: 2000,
  card_payments: 500,
});

describe("BudgetSummary", () => {
  it("lays the next period out as a sum ending in its unallocated amount", () => {
    render(
      <BudgetSummary
        data={budget({
          cash: 1000,
          cards: -500,
          current: quietCurrentPeriod,
          next: nextPeriod,
          low: { date: "2026-11-12", balance: 1000 },
        })}
      />
    );

    const next = within(screen.getByRole("region", { name: "Next period" }));
    expect(amountOf(next, "Pay")).toBe(`+${formatCurrency(3000)}`);
    expect(amountOf(next, "Bills")).toBe(formatCurrency(-2000));
    expect(amountOf(next, "Cards")).toBe(formatCurrency(-500));
    expect(amountOf(next, "Unallocated")).toBe(formatCurrency(500));
    expect(amountOf(next, "Cash at the end")).toBe(formatCurrency(1500));
    expect(screen.queryByText(/free to move/)).not.toBeInTheDocument();
  });

  it("says nothing is due before payday instead of repeating the balance", () => {
    render(
      <BudgetSummary
        data={budget({
          cash: 1000,
          cards: -500,
          current: quietCurrentPeriod,
          next: nextPeriod,
          low: { date: "2026-11-12", balance: 1000 },
        })}
      />
    );

    const untilPayday = within(screen.getByRole("region", { name: "Until payday" }));
    expect(untilPayday.getByText("nothing due")).toBeInTheDocument();
    expect(untilPayday.queryByText("At payday")).not.toBeInTheDocument();
    expect(screen.queryByText("Lowest point")).not.toBeInTheDocument();
  });

  it("lists the bills before payday and the balance they leave", () => {
    render(
      <BudgetSummary
        data={budget({
          cash: 1000,
          cards: 0,
          current: period("2026-11-12", "2026-11-15", { bills: 300 }),
          next: nextPeriod,
          low: { date: "2026-11-13", balance: 700 },
        })}
      />
    );

    const untilPayday = within(screen.getByRole("region", { name: "Until payday" }));
    expect(amountOf(untilPayday, "Bills")).toBe(formatCurrency(-300));
    expect(amountOf(untilPayday, "At payday")).toBe(formatCurrency(700));
    expect(untilPayday.queryByText("nothing due")).not.toBeInTheDocument();
  });

  it("shows the low point only when it dips below every balance shown", () => {
    render(
      <BudgetSummary
        data={budget({
          cash: 1000,
          cards: 0,
          current: quietCurrentPeriod,
          next: nextPeriod,
          low: { date: "2026-11-20", balance: -200 },
        })}
      />
    );

    expect(screen.getByText("Lowest point")).toBeInTheDocument();
    expect(screen.getByText(/Cash runs out on/)).toBeInTheDocument();
  });
});
