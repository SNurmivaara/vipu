"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ExpenseItem, ExpenseWithOccurrence, ExpenseFormData } from "@/types";
import { createExpense, updateExpense, deleteExpense } from "@/lib/api";
import { cn, formatCurrency } from "@/lib/utils";
import {
  parseSchedulingFormValues,
  getSchedulingInitialValues,
  getSchedulingDefaultValues,
} from "@/lib/schedulingMode";
import { EditDialog } from "./EditDialog";
import { CollapsibleSection } from "./CollapsibleSection";
import { SettleToggle, settleableOccurrence } from "./SettleToggle";
import { useToast } from "@/components/ui/Toast";

interface ExpensesSectionProps {
  expenses: ExpenseWithOccurrence[];
  title?: string;
  collapsible?: boolean;
  defaultOpen?: boolean;
  /** Render as a subsection within a parent group (no outer card) */
  subsection?: boolean;
}

// expense_mode: "monthly" (default), "one_time", "custom"
export const expenseFields = [
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

export function ExpensesSection({
  expenses,
  title = "Monthly Expenses",
  collapsible = false,
  defaultOpen = false,
  subsection = false,
}: ExpensesSectionProps) {
  const [editItem, setEditItem] = useState<ExpenseItem | null>(null);
  const [isNew, setIsNew] = useState(false);
  const queryClient = useQueryClient();
  const { toast } = useToast();

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

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: ExpenseFormData }) =>
      updateExpense(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["budget"] });
      toast({ title: "Expense updated", type: "success" });
    },
    onError: () => {
      toast({ title: "Failed to update expense", type: "error" });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteExpense,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["budget"] });
      toast({ title: "Expense deleted", type: "success" });
    },
    onError: () => {
      toast({ title: "Failed to delete expense", type: "error" });
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

    if (isNew) {
      createMutation.mutate(data);
    } else if (editItem) {
      updateMutation.mutate({ id: editItem.id, data });
    }
  };

  const handleDelete = () => {
    if (editItem) {
      deleteMutation.mutate(editItem.id);
    }
  };

  const openNew = () => {
    setEditItem(null);
    setIsNew(true);
  };

  const openEdit = (item: ExpenseItem) => {
    setEditItem(item);
    setIsNew(false);
  };

  const closeDialog = () => {
    setEditItem(null);
    setIsNew(false);
  };

  // Occurrences already paid are excluded: this total is what is still due.
  const totalExpenses = expenses.reduce(
    (sum, e) => (e.is_settled ? sum : sum + e.amount),
    0
  );

  // Sort by occurrence date, then by name
  const sortedExpenses = [...expenses].sort((a, b) => {
    const aDate = a.next_occurrence_date;
    const bDate = b.next_occurrence_date;

    if (aDate && bDate) {
      const cmp = aDate.localeCompare(bDate);
      if (cmp !== 0) return cmp;
    } else if (aDate) {
      return -1;
    } else if (bDate) {
      return 1;
    }
    return a.name.localeCompare(b.name);
  });

  // Format due date for display: "dd.mm." or "dd.mm.yyyy" if not current year
  const formatDueDate = (expense: ExpenseWithOccurrence) => {
    const occurrenceDate = expense.next_occurrence_date;

    if (occurrenceDate) {
      const date = new Date(occurrenceDate);
      const day = date.getDate();
      const month = date.getMonth() + 1;
      const year = date.getFullYear();
      const currentYear = new Date().getFullYear();

      if (year !== currentYear) {
        return `${day}.${month}.${year}`;
      }
      return `${day}.${month}.`;
    }
    // Fallback for expenses without occurrence date
    return `${expense.due_day}.`;
  };

  // Generate unique key for expense (handles multiple occurrences of same expense)
  const getExpenseKey = (expense: ExpenseWithOccurrence) => {
    const occurrenceDate = expense.next_occurrence_date;
    return occurrenceDate ? `${expense.id}-${occurrenceDate}` : `${expense.id}`;
  };

  // Simplified content for subsections (no header row, no total row)
  // Each occurrence carries a tick box where its state can still be corrected;
  // ticked ones are struck through and drop out of the subsection total.
  const subsectionContent = (
    <div className="divide-y divide-gray-100 dark:divide-gray-800">
      {sortedExpenses.map((expense) => {
        const settled = expense.is_settled;
        const occurrence = settleableOccurrence(expense);
        return (
          <div
            key={getExpenseKey(expense)}
            onClick={() => openEdit(expense)}
            className="flex items-center gap-2 px-4 py-2 hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer"
          >
            {occurrence ? (
              <SettleToggle
                kind="expense"
                itemId={expense.id}
                occurrenceDate={occurrence.occurrenceDate}
                settled={settled}
                name={expense.name}
              />
            ) : (
              <span className="w-4 shrink-0" aria-hidden="true" />
            )}
            <span
              className={cn(
                "flex-1 min-w-0 text-sm",
                settled
                  ? "text-gray-400 dark:text-gray-500 line-through"
                  : "text-gray-900 dark:text-gray-100"
              )}
            >
              {expense.name}
              <span className="text-gray-400 dark:text-gray-500 ml-1.5">
                ({formatDueDate(expense)})
              </span>
            </span>
            <span
              className={cn(
                "text-right text-sm",
                settled
                  ? "text-gray-400 dark:text-gray-500 line-through"
                  : "text-gray-900 dark:text-gray-100"
              )}
            >
              {formatCurrency(-expense.amount)}
            </span>
          </div>
        );
      })}
      {expenses.length === 0 && (
        <div className="px-4 py-4 text-center text-gray-500 dark:text-gray-400 text-sm">
          No expenses
        </div>
      )}
    </div>
  );

  const content = (
    <div className="divide-y divide-gray-100 dark:divide-gray-800">
      <div className="grid grid-cols-2 px-4 py-2 text-sm text-gray-500 dark:text-gray-400 uppercase tracking-wider">
        <span>Expense</span>
        <span className="text-right">Monthly</span>
      </div>
      {sortedExpenses.map((expense) => (
        <div
          key={getExpenseKey(expense)}
          onClick={() => openEdit(expense)}
          className="grid grid-cols-2 px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer"
        >
          <span className="text-gray-900 dark:text-gray-100">
            {expense.name}
          </span>
          <span className="text-right text-gray-900 dark:text-gray-100 font-medium">
            {formatCurrency(expense.amount)}
          </span>
        </div>
      ))}
      {expenses.length === 0 && (
        <div className="px-4 py-6 text-center text-gray-500 dark:text-gray-400">
          No expenses yet
        </div>
      )}
      {expenses.length > 0 && (
        <div className="grid grid-cols-2 px-4 py-3 bg-gray-50 dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700">
          <span className="font-semibold text-gray-900 dark:text-gray-100">
            Total
          </span>
          <span className="text-right font-semibold text-gray-900 dark:text-gray-100">
            {formatCurrency(totalExpenses)}
          </span>
        </div>
      )}
    </div>
  );

  const dialog = (
    <EditDialog
      open={editItem !== null || isNew}
      onOpenChange={(open) => !open && closeDialog()}
      title={isNew ? "Add Expense" : "Edit Expense"}
      fields={expenseFields}
      initialValues={
        editItem
          ? {
              name: editItem.name,
              amount: editItem.amount,
              ...getSchedulingInitialValues(editItem, "expense_mode"),
            }
          : {
              name: "",
              amount: 0,
              ...getSchedulingDefaultValues("expense_mode"),
            }
      }
      onSave={handleSave}
      onDelete={handleDelete}
      isNew={isNew}
    />
  );

  if (subsection) {
    return (
      <>
        <SubsectionCollapsible
          title={title}
          total={formatCurrency(-totalExpenses)}
          defaultOpen={defaultOpen}
        >
          {subsectionContent}
        </SubsectionCollapsible>
        {dialog}
      </>
    );
  }

  if (collapsible) {
    return (
      <>
        <CollapsibleSection
          title={title}
          total={formatCurrency(totalExpenses)}
          totalClassName="text-red-600 dark:text-red-400"
          defaultOpen={defaultOpen}
          onAdd={openNew}
        >
          {content}
        </CollapsibleSection>
        {dialog}
      </>
    );
  }

  return (
    <section className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800">
      <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-800 flex justify-between items-center">
        <h2 className="font-semibold text-gray-900 dark:text-gray-100">
          {title}
        </h2>
        <button
          onClick={openNew}
          className="text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
        >
          + Add
        </button>
      </div>
      {content}
      {dialog}
    </section>
  );
}

/** Lightweight collapsible for subsections within a parent group */
function SubsectionCollapsible({
  title,
  total,
  defaultOpen = false,
  children,
}: {
  title: string;
  total: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border-b border-gray-200 dark:border-gray-700 last:border-b-0">
      <div className="px-4 py-2 flex items-center justify-between">
        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          className="flex items-center gap-2 hover:opacity-80 transition-opacity focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
            className={`text-gray-400 transition-transform ${isOpen ? "rotate-90" : ""}`}
          >
            <polyline points="9 18 15 12 9 6" />
          </svg>
          <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
            {title}
          </span>
        </button>
        <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
          {total}
        </span>
      </div>
      {isOpen && (
        <div className="bg-gray-50 dark:bg-gray-800/50">
          {children}
        </div>
      )}
    </div>
  );
}
