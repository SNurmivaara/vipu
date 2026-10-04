import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SegmentedControl } from "./SegmentedControl";

const options = [
  { value: "month", label: "Month" },
  { value: "year", label: "Year" },
];

describe("SegmentedControl", () => {
  it("marks the selected option and reports clicks on the others", () => {
    const onChange = vi.fn();
    render(
      <SegmentedControl
        options={options}
        value="month"
        onChange={onChange}
        ariaLabel="Period"
      />
    );

    expect(screen.getByRole("radiogroup", { name: "Period" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Month" })).toHaveAttribute(
      "aria-checked",
      "true"
    );

    fireEvent.click(screen.getByRole("radio", { name: "Year" }));
    expect(onChange).toHaveBeenCalledWith("year");
  });
});
