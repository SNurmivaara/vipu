"use client";

import { useState, ReactNode } from "react";
import { cn } from "@/lib/utils";

interface CollapsibleSectionProps {
  title: string;
  total?: string;
  totalClassName?: string;
  /** What the total covers, e.g. "next period". Says which days it counts. */
  totalCaption?: string;
  children: ReactNode;
  defaultOpen?: boolean;
  onAdd?: () => void;
}

export function CollapsibleSection({
  title,
  total,
  totalClassName,
  totalCaption,
  children,
  defaultOpen = false,
  onAdd,
}: CollapsibleSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <section className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800">
      <div className="w-full px-4 py-3 flex items-center justify-between rounded-t-lg">
        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          className="flex items-center gap-3 hover:opacity-80 transition-opacity focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
            className={cn(
              "text-gray-500 transition-transform",
              isOpen && "rotate-90"
            )}
          >
            <polyline points="9 18 15 12 9 6" />
          </svg>
          <span className="font-semibold text-gray-900 dark:text-gray-100">
            {title}
          </span>
        </button>
        <div className="flex items-center gap-3">
          {total && (
            <span className="flex items-baseline gap-1.5">
              {totalCaption && (
                <span className="text-xs text-gray-400 dark:text-gray-500">
                  {totalCaption}
                </span>
              )}
              <span className={cn("font-medium", totalClassName)}>{total}</span>
            </span>
          )}
          {onAdd && (
            <button
              type="button"
              aria-label={`Add ${title}`}
              onClick={onAdd}
              className="text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 px-3 py-2 -my-1 rounded hover:bg-blue-50 dark:hover:bg-blue-900/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            >
              + Add
            </button>
          )}
        </div>
      </div>
      {isOpen && (
        <div className="border-t border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/50">
          {children}
        </div>
      )}
    </section>
  );
}
