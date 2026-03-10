"use client";

import { FrequencyUnit } from "@/types";
import { cn } from "@/lib/utils";

interface FrequencyPickerProps {
  value: number;
  unit: FrequencyUnit;
  onValueChange: (value: number) => void;
  onUnitChange: (unit: FrequencyUnit) => void;
  className?: string;
}

const FREQUENCY_UNITS: { value: FrequencyUnit; label: string }[] = [
  { value: "days", label: "days" },
  { value: "weeks", label: "weeks" },
  { value: "months", label: "months" },
  { value: "years", label: "years" },
];

export function FrequencyPicker({
  value,
  unit,
  onValueChange,
  onUnitChange,
  className,
}: FrequencyPickerProps) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <span className="text-sm text-gray-600 dark:text-gray-400">Every</span>
      <input
        type="number"
        value={value}
        onChange={(e) => onValueChange(Math.max(1, parseInt(e.target.value) || 1))}
        min={1}
        className={cn(
          "w-16 px-2 py-1.5 text-center border border-gray-300 dark:border-gray-700 rounded-md",
          "bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100",
          "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        )}
      />
      <select
        value={unit}
        onChange={(e) => onUnitChange(e.target.value as FrequencyUnit)}
        className={cn(
          "px-2 py-1.5 border border-gray-300 dark:border-gray-700 rounded-md",
          "bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100",
          "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        )}
      >
        {FREQUENCY_UNITS.map((u) => (
          <option key={u.value} value={u.value}>
            {u.label}
          </option>
        ))}
      </select>
    </div>
  );
}
