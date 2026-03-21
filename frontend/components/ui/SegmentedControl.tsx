"use client";

import { cn } from "@/lib/utils";

interface SegmentOption {
  value: string;
  label: string;
}

interface SegmentedControlProps {
  options: SegmentOption[];
  value: string;
  onChange: (value: string) => void;
  className?: string;
  /** Accessible label for the control group */
  ariaLabel?: string;
}

export function SegmentedControl({
  options,
  value,
  onChange,
  className,
  ariaLabel = "Options",
}: SegmentedControlProps) {
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className={cn(
        "inline-flex rounded-lg bg-gray-100 dark:bg-gray-800 p-1",
        className
      )}
    >
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={value === option.value}
          onClick={() => onChange(option.value)}
          className={cn(
            "px-3 py-1.5 text-sm font-medium rounded-md transition-all",
            "focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1",
            value === option.value
              ? "bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm"
              : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200"
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
