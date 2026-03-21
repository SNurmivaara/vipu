"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ExpenseItem, ExpenseFormData } from "@/types";
import { createExpense } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { ExpensesSection } from "./ExpensesSection";
import { EditDialog } from "./EditDialog";
import { useToast } from "@/components/ui/Toast";
import { cn } from "@/lib/utils";

interface ExpensesGroupSectionProps {
  expensesBeforePayday: ExpenseItem[];
  expensesAfterPayday: ExpenseItem[];
  defaultOpen?: boolean;
}

// expense_mode: "monthly" (default), "one_time", "custom"
const expenseFields = [
  { name: "name", label: "Name", type: "text" as const, required: true },
  {
    name: "amount",
    label: "Amount (€)",
    type: "number" as const,
    required: true,
    min: 0,
    step: 0.01,
  },
  {
    name: "expense_mode",
    label: "",
    type: "segment" as const,
    options: [
      { value: "monthly", label: "Monthly" },
      { value: "one_time", label: "One-time" },
      { value: "custom", label: "Custom" },
    ],
  },
  // Monthly mode: just due day
  {
    name: "due_day",
    label: "Due Day (of month)",
    type: "number" as const,
    required: true,
    min: 1,
    max: 31,
    step: 1,
    showWhen: { field: "expense_mode", value: "monthly" },
  },
  // One-time mode: date picker
  {
    name: "one_time_date",
    label: "Date",
    type: "date" as const,
    showWhen: { field: "expense_mode", value: "one_time" },
  },
  // Custom mode: due day, frequency, start/end dates
  {
    name: "custom_due_day",
    label: "Due Day (of month)",
    type: "number" as const,
    required: true,
    min: 1,
    max: 31,
    step: 1,
    showWhen: { field: "expense_mode", value: "custom" },
  },
  {
    name: "frequency_value",
    label: "Frequency",
    type: "frequency" as const,
    unitFieldName: "frequency_unit",
    showWhen: { field: "expense_mode", value: "custom" },
  },
  {
    name: "start_date",
    label: "Start Date (optional)",
    type: "date" as const,
    showWhen: { field: "expense_mode", value: "custom" },
  },
  {
    name: "end_date",
    label: "End Date (optional)",
    type: "date" as const,
    showWhen: { field: "expense_mode", value: "custom" },
  },
];

export function ExpensesGroupSection({
  expensesBeforePayday,
  expensesAfterPayday,
  defaultOpen = false,
}: ExpensesGroupSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const [isNewDialogOpen, setIsNewDialogOpen] = useState(false);
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const totalBeforePayday = expensesBeforePayday.reduce((sum, e) => sum + e.amount, 0);
  const totalAfterPayday = expensesAfterPayday.reduce((sum, e) => sum + e.amount, 0);
  const totalExpenses = totalBeforePayday + totalAfterPayday;

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
    const mode = (values.expense_mode as string) || "monthly";
    const oneTimeDate = values.one_time_date as string;

    let dueDay: number;
    let startDate: string | null = null;
    let endDate: string | null = null;
    let frequencyValue = 1;
    let frequencyUnit: "days" | "weeks" | "months" | "years" = "months";
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
      frequencyUnit = (values.frequency_unit as "days" | "weeks" | "months" | "years") || "months";
      startDate = (values.start_date as string) || null;
      endDate = (values.end_date as string) || null;
    }

    const data: ExpenseFormData = {
      name: values.name as string,
      amount: values.amount as number,
      is_savings_goal: false,
      due_day: dueDay,
      frequency_value: frequencyValue,
      frequency_unit: frequencyUnit,
      start_date: startDate,
      end_date: endDate,
      is_ephemeral: isEphemeral,
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
          <span className="font-medium text-gray-900 dark:text-gray-100">
            {formatCurrency(totalExpenses)}
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
            title="Before Payday"
            subsection
          />
          <ExpensesSection
            expenses={expensesAfterPayday}
            title="After Payday"
            subsection
          />
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
          expense_mode: "monthly",
          due_day: 1,
          custom_due_day: 1,
          frequency_value: 1,
          frequency_unit: "months",
          one_time_date: "",
          start_date: "",
          end_date: "",
        }}
        onSave={handleSave}
        isNew
      />
    </section>
  );
}
