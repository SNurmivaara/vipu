"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ExpenseItem, ExpenseFormData } from "@/types";
import { createExpense, updateExpense, deleteExpense } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { EditDialog } from "./EditDialog";
import { CollapsibleSection } from "./CollapsibleSection";
import { useToast } from "@/components/ui/Toast";

interface ExpensesSectionProps {
  expenses: ExpenseItem[];
  title?: string;
  collapsible?: boolean;
  defaultOpen?: boolean;
  /** Render as a subsection within a parent group (no outer card) */
  subsection?: boolean;
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

  const totalExpenses = expenses.reduce((sum, e) => sum + e.amount, 0);

  // Simplified content for subsections (no header row, no total row)
  const subsectionContent = (
    <div className="divide-y divide-gray-100 dark:divide-gray-800">
      {expenses.map((expense) => (
        <div
          key={expense.id}
          onClick={() => openEdit(expense)}
          className="grid grid-cols-2 px-4 py-2 hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer"
        >
          <span className="text-gray-900 dark:text-gray-100 text-sm">
            {expense.name}
          </span>
          <span className="text-right text-gray-900 dark:text-gray-100 text-sm">
            {formatCurrency(expense.amount)}
          </span>
        </div>
      ))}
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
      {expenses.map((expense) => (
        <div
          key={expense.id}
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

  // Determine expense mode from existing item
  const getExpenseMode = (item: ExpenseItem): string => {
    if (item.is_ephemeral) return "one_time";
    // If non-monthly frequency or has start/end date, it's custom
    if (item.frequency_value !== 1 || item.frequency_unit !== "months" || item.start_date || item.end_date) {
      return "custom";
    }
    return "monthly";
  };

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
              expense_mode: getExpenseMode(editItem),
              due_day: editItem.due_day,
              custom_due_day: editItem.due_day,
              frequency_value: editItem.frequency_value,
              frequency_unit: editItem.frequency_unit,
              one_time_date: editItem.is_ephemeral ? (editItem.start_date || "") : "",
              start_date: editItem.start_date || "",
              end_date: editItem.end_date || "",
            }
          : {
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
          total={formatCurrency(totalExpenses)}
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
          totalClassName="text-gray-900 dark:text-gray-100"
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
  onAdd,
  children,
}: {
  title: string;
  total: string;
  defaultOpen?: boolean;
  onAdd?: () => void;
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
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
            {total}
          </span>
          {onAdd && (
            <button
              type="button"
              onClick={onAdd}
              className="text-xs text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 px-2 py-1 rounded hover:bg-blue-50 dark:hover:bg-blue-900/20"
            >
              + Add
            </button>
          )}
        </div>
      </div>
      {isOpen && (
        <div className="bg-gray-50 dark:bg-gray-800/50">
          {children}
        </div>
      )}
    </div>
  );
}
