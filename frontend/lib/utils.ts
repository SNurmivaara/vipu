import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format a number as European currency (1 234,56 €)
 */
export function formatCurrency(value: number): string {
  const formatted = new Intl.NumberFormat("fi-FI", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
  return `${formatted} €`;
}

/**
 * Format a percentage (26,5 %)
 */
export function formatPercentage(value: number): string {
  const formatted = new Intl.NumberFormat("fi-FI", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(value);
  return `${formatted} %`;
}

/**
 * Get color class for account balance
 * Green: > 0
 * Yellow: -500 to 0
 * Red: < -500
 */
export function getBalanceColor(balance: number): string {
  if (balance > 0) {
    return "text-emerald-700 dark:text-emerald-400";
  } else if (balance >= -500) {
    return "text-orange-600 dark:text-orange-400";
  } else {
    return "text-red-600 dark:text-red-400";
  }
}

/**
 * Parse European format number input (allows comma as decimal separator)
 */
export function parseEuropeanNumber(value: string): number {
  const normalized = value.replace(/\s/g, "").replace(",", ".");
  return parseFloat(normalized) || 0;
}
