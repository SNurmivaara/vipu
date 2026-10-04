import { afterEach, describe, expect, it, vi } from "vitest";

import {
  formatCurrency,
  formatCurrencyRounded,
  formatOccurrenceDate,
  formatPercentage,
  getBalanceColor,
  parseEuropeanNumber,
} from "./utils";

// fi-FI groups thousands with a no-break space and writes minus as U+2212.
const normalize = (s: string) => s.replace(/\s/g, " ").replace("−", "-");

describe("formatCurrency", () => {
  it("uses Finnish grouping, a decimal comma and a trailing euro sign", () => {
    expect(normalize(formatCurrency(1234.5))).toBe("1 234,50 €");
  });

  it("keeps the sign of debt", () => {
    expect(normalize(formatCurrency(-42))).toBe("-42,00 €");
  });
});

describe("formatCurrencyRounded", () => {
  it("rounds to whole euros", () => {
    expect(normalize(formatCurrencyRounded(1234.5))).toBe("1 235 €");
  });
});

describe("formatPercentage", () => {
  it("shows one decimal", () => {
    expect(normalize(formatPercentage(26.54))).toBe("26,5 %");
  });
});

describe("getBalanceColor", () => {
  it("is green above zero, orange down to -500 and red below", () => {
    expect(getBalanceColor(0.01)).toContain("emerald");
    expect(getBalanceColor(0)).toContain("orange");
    expect(getBalanceColor(-500)).toContain("orange");
    expect(getBalanceColor(-500.01)).toContain("red");
  });
});

describe("parseEuropeanNumber", () => {
  it("accepts a decimal comma and spaces", () => {
    expect(parseEuropeanNumber("1 234,56")).toBe(1234.56);
  });

  it("falls back to zero for text that is not a number", () => {
    expect(parseEuropeanNumber("abc")).toBe(0);
  });
});

describe("formatOccurrenceDate", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("omits the year inside the current year and shows it outside", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-01T12:00:00Z"));
    expect(formatOccurrenceDate("2026-08-25")).toBe("25.8.");
    expect(formatOccurrenceDate("2027-08-25")).toBe("25.8.2027");
  });
});
