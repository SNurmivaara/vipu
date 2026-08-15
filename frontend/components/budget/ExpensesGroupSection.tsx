"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ExpenseWithOccurrence, ExpenseFormData } from "@/types";
import { createExpense } from "@/lib/api";
import { formatCurrency, cn } from "@/lib/utils";
import {
  parseSchedulingFormValues,
  getSchedulingDefaultValues,
} from "@/lib/schedulingMode";
import { ExpensesSection, expenseFields } from "./ExpensesSection";
import { EditDialog } from "./EditDialog";
import { useToast } from "@/components/ui/Toast";

interface ExpensesGroupSectionProps {
  expensesBeforePayday: ExpenseWithOccurrence[];
  expensesAfterPayday: ExpenseWithOccurrence[];
  /** Expenses that don't fall in either period (future scheduled) */
  expensesFuture?: ExpenseWithOccurrence[];
  defaultOpen?: boolean;
}

export function ExpensesGroupSection({
  expensesBeforePayday,
  expensesAfterPayday,
  expensesFuture = [],
  defaultOpen = false,
}: ExpensesGroupSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const [isNewDialogOpen, setIsNewDialogOpen] = useState(false);
  const queryClient = useQueryClient();
  const { toast } = useToast();

  // Occurrences already ticked off are money that has moved, so they don't
  // count towards what is still ahead of us.
  const stillDue = (items: ExpenseWithOccurrence[]) =>
    items.reduce((sum, e) => (e.is_settled ? sum : sum + e.amount), 0);

  const totalExpenses =
    stillDue(expensesBeforePayday) +
    stillDue(expensesAfterPayday) +
    stillDue(expensesFuture);

  const createMutation = useMutation({
    mutationFn: createExpense,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["budget"] });
      toast({ title: "Expense created", type: "success" });
    },
    onError: () => {
      toast({ title: "Failed to create expense", type: "error" });
    },
  });

  const handleSave = (values: Record<string, string | number | boolean>) => {
    const scheduling = parseSchedulingFormValues(values, "expense_mode");

    const data: ExpenseFormData = {
      name: values.name as string,
      amount: values.amount as number,
      is_savings_goal: false,
      ...scheduling,
      archived_at: null,
    };

    createMutation.mutate(data);
  };

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
            Expenses
          </span>
        </button>
        <div className="flex items-center gap-3">
          <span className="font-medium text-red-600 dark:text-red-400">
            {formatCurrency(-totalExpenses)}
          </span>
          <button
            type="button"
            aria-label="Add Expense"
            onClick={() => setIsNewDialogOpen(true)}
            className="text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 px-3 py-2 -my-1 rounded hover:bg-blue-50 dark:hover:bg-blue-900/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          >
            + Add
          </button>
        </div>
      </div>
      {isOpen && (
        <div className="border-t border-gray-200 dark:border-gray-800">
          <ExpensesSection
            expenses={expensesBeforePayday}
            title="This month"
            subsection
          />
          <ExpensesSection
            expenses={expensesAfterPayday}
            title="Next month"
            subsection
          />
          {expensesFuture.length > 0 && (
            <ExpensesSection
              expenses={expensesFuture}
              title="Future"
              subsection
            />
          )}
        </div>
      )}

      <EditDialog
        open={isNewDialogOpen}
        onOpenChange={setIsNewDialogOpen}
        title="Add Expense"
        fields={expenseFields}
        initialValues={{
          name: "",
          amount: 0,
          ...getSchedulingDefaultValues("expense_mode"),
        }}
        onSave={handleSave}
        isNew
      />
    </section>
  );
}
