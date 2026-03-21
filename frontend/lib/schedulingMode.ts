import { FrequencyUnit, IncomeItem, ExpenseItem } from "@/types";

/** The three scheduling modes for budget items */
export type SchedulingMode = "monthly" | "one_time" | "custom";

export const DEFAULT_MODE: SchedulingMode = "monthly";

/** Values extracted from form for scheduling fields */
export interface SchedulingFormValues {
  mode: SchedulingMode;
  due_day?: number;
  custom_due_day?: number;
  one_time_date?: string;
  frequency_value?: number;
  frequency_unit?: FrequencyUnit;
  start_date?: string;
  end_date?: string;
}

/** Parsed scheduling data ready for API submission */
export interface SchedulingData {
  due_day: number;
  frequency_value: number;
  frequency_unit: FrequencyUnit;
  start_date: string | null;
  end_date: string | null;
  is_ephemeral: boolean;
}

/**
 * Parse form values into scheduling data for API submission.
 * Handles the three modes: monthly, one_time, and custom.
 */
export function parseSchedulingFormValues(
  values: Record<string, string | number | boolean>,
  modeFieldName: string
): SchedulingData {
  const mode = (values[modeFieldName] as SchedulingMode) || DEFAULT_MODE;
  const oneTimeDate = values.one_time_date as string;

  let dueDay: number;
  let startDate: string | null = null;
  let endDate: string | null = null;
  let frequencyValue = 1;
  let frequencyUnit: FrequencyUnit = "months";
  let isEphemeral = false;

  if (mode === "monthly") {
    dueDay = (values.due_day as number) || 1;
  } else if (mode === "one_time") {
    isEphemeral = true;
    if (oneTimeDate) {
      const date = new Date(oneTimeDate);
      dueDay = date.getDate();
      startDate = oneTimeDate;
    } else {
      dueDay = 1;
    }
  } else {
    // custom mode
    dueDay = (values.custom_due_day as number) || 1;
    frequencyValue = (values.frequency_value as number) || 1;
    frequencyUnit = (values.frequency_unit as FrequencyUnit) || "months";
    startDate = (values.start_date as string) || null;
    endDate = (values.end_date as string) || null;
  }

  return {
    due_day: dueDay,
    frequency_value: frequencyValue,
    frequency_unit: frequencyUnit,
    start_date: startDate,
    end_date: endDate,
    is_ephemeral: isEphemeral,
  };
}

/** Common interface for items with scheduling fields */
interface SchedulableItem {
  is_ephemeral: boolean;
  frequency_value: number;
  frequency_unit: FrequencyUnit;
  start_date: string | null;
  end_date: string | null;
}

/**
 * Determine the scheduling mode from an existing item's data.
 * - If is_ephemeral: "one_time"
 * - If non-monthly frequency or has date range: "custom"
 * - Otherwise: "monthly"
 */
export function getModeFromItem(item: SchedulableItem): SchedulingMode {
  if (item.is_ephemeral) return "one_time";
  if (
    item.frequency_value !== 1 ||
    item.frequency_unit !== "months" ||
    item.start_date ||
    item.end_date
  ) {
    return "custom";
  }
  return "monthly";
}

/**
 * Get initial form values for scheduling fields from an existing item.
 */
export function getSchedulingInitialValues(
  item: SchedulableItem & { due_day: number; start_date: string | null },
  modeFieldName: string
): Record<string, string | number | boolean> {
  const mode = getModeFromItem(item);
  return {
    [modeFieldName]: mode,
    due_day: item.due_day,
    custom_due_day: item.due_day,
    frequency_value: item.frequency_value,
    frequency_unit: item.frequency_unit,
    one_time_date: item.is_ephemeral ? (item.start_date || "") : "",
    start_date: item.start_date || "",
    end_date: item.end_date || "",
  };
}

/**
 * Get default form values for scheduling fields (new item).
 */
export function getSchedulingDefaultValues(
  modeFieldName: string
): Record<string, string | number | boolean> {
  return {
    [modeFieldName]: DEFAULT_MODE,
    due_day: 1,
    custom_due_day: 1,
    frequency_value: 1,
    frequency_unit: "months",
    one_time_date: "",
    start_date: "",
    end_date: "",
  };
}

// Re-export types for use in components
export type { IncomeItem, ExpenseItem };
