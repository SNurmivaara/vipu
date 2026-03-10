"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ExpenseItem, ExpenseFormData } from "@/types";
import { createExpense, updateExpense, deleteExpense } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { EditDialog } from "./EditDialog";
import { CollapsibleSection } from "./CollapsibleSection";
import { useToast } from "@/components/ui/Toast";

interface SavingsGoalsSectionProps {
  savingsGoals: ExpenseItem[];
  collapsible?: boolean;
  defaultOpen?: boolean;
}

const savingsGoalFields = [
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
    name: "due_day",
    label: "Due Day (of month)",
    type: "number" as const,
    required: true,
    min: 1,
    max: 31,
    step: 1,
  },
  {
    name: "frequency_value",
    label: "Frequency",
    type: "frequency" as const,
    unitFieldName: "frequency_unit",
  },
  { name: "is_ephemeral", label: "One-time goal", type: "checkbox" as const },
  { name: "start_date", label: "Start Date", type: "date" as const },
  { name: "end_date", label: "End Date", type: "date" as const },
];

export function SavingsGoalsSection({
  savingsGoals,
  collapsible = false,
  defaultOpen = false,
}: SavingsGoalsSectionProps) {
  const [editItem, setEditItem] = useState<ExpenseItem | null>(null);
  const [isNew, setIsNew] = useState(false);
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const createMutation = useMutation({
    mutationFn: (data: ExpenseFormData) =>
      createExpense({ ...data, is_savings_goal: true }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["budget"] });
      toast({ title: "Savings goal created", type: "success" });
    },
    onError: () => {
      toast({ title: "Failed to create savings goal", type: "error" });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: ExpenseFormData }) =>
      updateExpense(id, { ...data, is_savings_goal: true }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["budget"] });
      toast({ title: "Savings goal updated", type: "success" });
    },
    onError: () => {
      toast({ title: "Failed to update savings goal", type: "error" });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteExpense,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["budget"] });
      toast({ title: "Savings goal deleted", type: "success" });
    },
    onError: () => {
      toast({ title: "Failed to delete savings goal", type: "error" });
    },
  });

  const handleSave = (values: Record<string, string | number | boolean>) => {
    const data: ExpenseFormData = {
      name: values.name as string,
      amount: values.amount as number,
      is_savings_goal: true,
      due_day: (values.due_day as number) || 1,
      frequency_value: (values.frequency_value as number) || 1,
      frequency_unit: (values.frequency_unit as "days" | "weeks" | "months" | "years") || "months",
      start_date: (values.start_date as string) || null,
      end_date: (values.end_date as string) || null,
      is_ephemeral: values.is_ephemeral as boolean,
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

  const totalGoals = savingsGoals.reduce((sum, g) => sum + g.amount, 0);

  const content = (
    <div className="divide-y divide-gray-100 dark:divide-gray-800">
      <div className="grid grid-cols-2 px-4 py-2 text-sm text-gray-500 dark:text-gray-400 uppercase tracking-wider">
        <span>Goal</span>
        <span className="text-right">Target</span>
      </div>
      {savingsGoals.map((goal) => (
        <div
          key={goal.id}
          onClick={() => openEdit(goal)}
          className="grid grid-cols-2 px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer"
        >
          <span className="text-gray-900 dark:text-gray-100">{goal.name}</span>
          <span className="text-right text-gray-900 dark:text-gray-100 font-medium">
            {formatCurrency(goal.amount)}
          </span>
        </div>
      ))}
      {savingsGoals.length === 0 && (
        <div className="px-4 py-6 text-center text-gray-500 dark:text-gray-400">
          No savings goals yet
        </div>
      )}
      {savingsGoals.length > 0 && (
        <div className="grid grid-cols-2 px-4 py-3 bg-gray-50 dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700">
          <span className="font-semibold text-gray-900 dark:text-gray-100">
            Total
          </span>
          <span className="text-right font-semibold text-gray-900 dark:text-gray-100">
            {formatCurrency(totalGoals)}
          </span>
        </div>
      )}
    </div>
  );

  const dialog = (
    <EditDialog
      open={editItem !== null || isNew}
      onOpenChange={(open) => !open && closeDialog()}
      title={isNew ? "Add Savings Goal" : "Edit Savings Goal"}
      fields={savingsGoalFields}
      initialValues={
        editItem
          ? {
              name: editItem.name,
              amount: editItem.amount,
              due_day: editItem.due_day,
              frequency_value: editItem.frequency_value,
              frequency_unit: editItem.frequency_unit,
              is_ephemeral: editItem.is_ephemeral,
              start_date: editItem.start_date || "",
              end_date: editItem.end_date || "",
            }
          : {
              name: "",
              amount: 0,
              due_day: 1,
              frequency_value: 1,
              frequency_unit: "months",
              is_ephemeral: false,
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
          title="Monthly Savings"
          total={formatCurrency(totalGoals)}
          totalClassName="text-blue-600 dark:text-blue-400"
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
          Monthly Savings
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
