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

// savings_mode: "monthly" (default), "one_time", "custom"
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
    name: "savings_mode",
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
    showWhen: { field: "savings_mode", value: "monthly" },
  },
  // One-time mode: date picker
  {
    name: "one_time_date",
    label: "Date",
    type: "date" as const,
    showWhen: { field: "savings_mode", value: "one_time" },
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
    showWhen: { field: "savings_mode", value: "custom" },
  },
  {
    name: "frequency_value",
    label: "Frequency",
    type: "frequency" as const,
    unitFieldName: "frequency_unit",
    showWhen: { field: "savings_mode", value: "custom" },
  },
  {
    name: "start_date",
    label: "Start Date (optional)",
    type: "date" as const,
    showWhen: { field: "savings_mode", value: "custom" },
  },
  {
    name: "end_date",
    label: "End Date (optional)",
    type: "date" as const,
    showWhen: { field: "savings_mode", value: "custom" },
  },
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
    const mode = (values.savings_mode as string) || "monthly";
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
      is_savings_goal: true,
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

  // Determine savings mode from existing item
  const getSavingsMode = (item: ExpenseItem): string => {
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
      title={isNew ? "Add Savings Goal" : "Edit Savings Goal"}
      fields={savingsGoalFields}
      initialValues={
        editItem
          ? {
              name: editItem.name,
              amount: editItem.amount,
              savings_mode: getSavingsMode(editItem),
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
              savings_mode: "monthly",
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
