import { describe, expect, it } from "vitest";

import {
  getModeFromItem,
  getSchedulingDefaultValues,
  getSchedulingInitialValues,
  parseSchedulingFormValues,
} from "./schedulingMode";

const monthlyItem = {
  is_ephemeral: false,
  frequency_value: 1,
  frequency_unit: "months" as const,
  start_date: null,
  end_date: null,
  due_day: 15,
};

describe("parseSchedulingFormValues", () => {
  it("monthly mode keeps the due day and a monthly frequency", () => {
    expect(
      parseSchedulingFormValues({ mode: "monthly", due_day: 15 }, "mode")
    ).toEqual({
      due_day: 15,
      frequency_value: 1,
      frequency_unit: "months",
      start_date: null,
      end_date: null,
      is_ephemeral: false,
    });
  });

  it("one-time mode is ephemeral and takes its day from the date", () => {
    expect(
      parseSchedulingFormValues(
        { mode: "one_time", one_time_date: "2026-03-20" },
        "mode"
      )
    ).toMatchObject({
      due_day: 20,
      start_date: "2026-03-20",
      is_ephemeral: true,
    });
  });

  it("custom mode reads its own fields and turns blanks into null", () => {
    expect(
      parseSchedulingFormValues(
        {
          mode: "custom",
          custom_due_day: 5,
          frequency_value: 2,
          frequency_unit: "weeks",
          start_date: "2026-01-05",
          end_date: "",
        },
        "mode"
      )
    ).toEqual({
      due_day: 5,
      frequency_value: 2,
      frequency_unit: "weeks",
      start_date: "2026-01-05",
      end_date: null,
      is_ephemeral: false,
    });
  });

  it("defaults to monthly on day 1 when the form is empty", () => {
    expect(parseSchedulingFormValues({}, "mode")).toMatchObject({
      due_day: 1,
      is_ephemeral: false,
    });
  });
});

describe("getModeFromItem", () => {
  it("classifies items by ephemerality, frequency and date range", () => {
    expect(getModeFromItem(monthlyItem)).toBe("monthly");
    expect(getModeFromItem({ ...monthlyItem, is_ephemeral: true })).toBe(
      "one_time"
    );
    expect(getModeFromItem({ ...monthlyItem, frequency_value: 3 })).toBe(
      "custom"
    );
    expect(getModeFromItem({ ...monthlyItem, end_date: "2026-12-31" })).toBe(
      "custom"
    );
  });
});

describe("form values", () => {
  it("round-trips an existing monthly item through the form", () => {
    const values = getSchedulingInitialValues(monthlyItem, "mode");
    expect(values.mode).toBe("monthly");
    expect(parseSchedulingFormValues(values, "mode").due_day).toBe(15);
  });

  it("starts a new item as monthly on day 1", () => {
    expect(getSchedulingDefaultValues("mode")).toMatchObject({
      mode: "monthly",
      due_day: 1,
    });
  });
});
