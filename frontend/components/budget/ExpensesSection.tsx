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
  collapsible?: boolean;
  defaultOpen?: boolean;
}

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
  { name: "is_ephemeral", label: "One-time payment", type: "checkbox" as const },
  // For one-time: show date picker
  {
    name: "one_time_date",
    label: "Date",
    type: "date" as const,
    showWhen: { field: "is_ephemeral", value: true },
  },
  // For recurring: show due day, frequency, and optional date range
  {
    name: "due_day",
    label: "Due Day (of month)",
    type: "number" as const,
    required: true,
    min: 1,
    max: 31,
    step: 1,
    hideWhen: { field: "is_ephemeral", value: true },
  },
  {
    name: "frequency_value",
    label: "Frequency",
    type: "frequency" as const,
    unitFieldName: "frequency_unit",
    hideWhen: { field: "is_ephemeral", value: true },
  },
  {
    name: "start_date",
    label: "Start Date (optional)",
    type: "date" as const,
    hideWhen: { field: "is_ephemeral", value: true },
  },
  {
    name: "end_date",
    label: "End Date (optional)",
    type: "date" as const,
    hideWhen: { field: "is_ephemeral", value: true },
  },
];

export function ExpensesSection({
  expenses,
  collapsible = false,
  defaultOpen = false,
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
    const isEphemeral = values.is_ephemeral as boolean;
    const oneTimeDate = values.one_time_date as string;

    // For one-time payments, extract due_day from the date and set start_date
    let dueDay = (values.due_day as number) || 1;
    let startDate = (values.start_date as string) || null;

    if (isEphemeral && oneTimeDate) {
      const date = new Date(oneTimeDate);
      dueDay = date.getDate();
      startDate = oneTimeDate;
    }

    const data: ExpenseFormData = {
      name: values.name as string,
      amount: values.amount as number,
      is_savings_goal: false,
      due_day: dueDay,
      frequency_value: (values.frequency_value as number) || 1,
      frequency_unit: (values.frequency_unit as "days" | "weeks" | "months" | "years") || "months",
      start_date: startDate,
      end_date: isEphemeral ? null : ((values.end_date as string) || null),
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
              due_day: editItem.due_day,
              frequency_value: editItem.frequency_value,
              frequency_unit: editItem.frequency_unit,
              is_ephemeral: editItem.is_ephemeral,
              one_time_date: editItem.is_ephemeral ? (editItem.start_date || "") : "",
              start_date: editItem.is_ephemeral ? "" : (editItem.start_date || ""),
              end_date: editItem.end_date || "",
            }
          : {
              name: "",
              amount: 0,
              due_day: 1,
              frequency_value: 1,
              frequency_unit: "months",
              is_ephemeral: false,
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

  if (collapsible) {
    return (
      <>
        <CollapsibleSection
          title="Monthly Expenses"
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
          Monthly Expenses
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
