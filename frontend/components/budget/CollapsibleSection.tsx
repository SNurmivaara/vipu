"use client";

import { useState, ReactNode } from "react";
import { cn } from "@/lib/utils";

interface CollapsibleSectionProps {
  title: string;
  total?: string;
  totalClassName?: string;
  children: ReactNode;
  defaultOpen?: boolean;
  onAdd?: () => void;
}

export function CollapsibleSection({
  title,
  total,
  totalClassName,
  children,
  defaultOpen = false,
  onAdd,
}: CollapsibleSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <section className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors rounded-t-lg"
      >
        <div className="flex items-center gap-3">
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
            className={cn(
              "text-gray-400 transition-transform",
              isOpen && "rotate-90"
            )}
          >
            <polyline points="9 18 15 12 9 6" />
          </svg>
          <span className="font-semibold text-gray-900 dark:text-gray-100">
            {title}
          </span>
        </div>
        <div className="flex items-center gap-3">
          {total && (
            <span className={cn("font-medium", totalClassName)}>{total}</span>
          )}
          {onAdd && (
            <span
              role="button"
              onClick={(e) => {
                e.stopPropagation();
                onAdd();
              }}
              className="text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 px-2 py-1 -my-1 rounded hover:bg-blue-50 dark:hover:bg-blue-900/20"
            >
              + Add
            </span>
          )}
        </div>
      </button>
      {isOpen && (
        <div className="border-t border-gray-200 dark:border-gray-800">
          {children}
        </div>
      )}
    </section>
  );
}
