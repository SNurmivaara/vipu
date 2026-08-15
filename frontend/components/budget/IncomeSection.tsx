"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useInvalidateBudget } from "@/hooks/useInvalidateBudget";
import { IncomeItem, IncomeWithOccurrence, IncomeFormData, BudgetSettings } from "@/types";
import { createIncome, updateIncome, deleteIncome } from "@/lib/api";
import { cn, formatCurrency, formatOccurrenceDate } from "@/lib/utils";
import {
  parseSchedulingFormValues,
  getSchedulingInitialValues,
  getSchedulingDefaultValues,
} from "@/lib/schedulingMode";
import { EditDialog } from "./EditDialog";
import { CollapsibleSection } from "./CollapsibleSection";
import { SettleToggle, settleableOccurrence } from "./SettleToggle";
import { useToast } from "@/components/ui/Toast";

interface IncomeSectionProps {
  income: IncomeWithOccurrence[];
  settings: BudgetSettings;
  collapsible?: boolean;
  defaultOpen?: boolean;
}

// income_mode: "monthly" (default), "one_time", "custom"
const incomeFields = [
  { name: "name", label: "Name", type: "text" as const, required: true },
  {
    name: "gross_amount",
    label: "Gross Amount (€)",
    type: "number" as const,
    required: true,
    min: 0,
    step: 0.01,
  },
  { name: "is_taxed", label: "Subject to tax", type: "checkbox" as const },
  {
    name: "income_mode",
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
    showWhen: { field: "income_mode", value: "monthly" },
  },
  // One-time mode: date picker
  {
    name: "one_time_date",
    label: "Date",
    type: "date" as const,
    showWhen: { field: "income_mode", value: "one_time" },
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
    showWhen: { field: "income_mode", value: "custom" },
  },
  {
    name: "frequency_value",
    label: "Frequency",
    type: "frequency" as const,
    unitFieldName: "frequency_unit",
    showWhen: { field: "income_mode", value: "custom" },
  },
  {
    name: "start_date",
    label: "Start Date (optional)",
    type: "date" as const,
    showWhen: { field: "income_mode", value: "custom" },
  },
  {
    name: "end_date",
    label: "End Date (optional)",
    type: "date" as const,
    showWhen: { field: "income_mode", value: "custom" },
  },
];

/**
 * Calculate net income for an item.
 * - If not taxed: net = gross
 * - If taxed: net = gross * (1 - defaultTaxRate)
 */
function calculateNetAmount(
  item: IncomeItem,
  defaultTaxRate: number
): number {
  if (!item.is_taxed) {
    return item.gross_amount;
  }
  return item.gross_amount * (1 - defaultTaxRate / 100);
}

export function IncomeSection({
  income,
  settings,
  collapsible = false,
  defaultOpen = false,
}: IncomeSectionProps) {
  const [editItem, setEditItem] = useState<IncomeItem | null>(null);
  const [isNew, setIsNew] = useState(false);
  const invalidateBudget = useInvalidateBudget();
  const { toast } = useToast();

  const createMutation = useMutation({
    mutationFn: createIncome,
    onSuccess: () => {
      invalidateBudget();
      toast({ title: "Income created", type: "success" });
    },
    onError: () => {
      toast({ title: "Failed to create income", type: "error" });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: IncomeFormData }) =>
      updateIncome(id, data),
    onSuccess: () => {
      invalidateBudget();
      toast({ title: "Income updated", type: "success" });
    },
    onError: () => {
      toast({ title: "Failed to update income", type: "error" });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteIncome,
    onSuccess: () => {
      invalidateBudget();
      toast({ title: "Income deleted", type: "success" });
    },
    onError: () => {
      toast({ title: "Failed to delete income", type: "error" });
    },
  });

  const handleSave = (values: Record<string, string | number | boolean>) => {
    const scheduling = parseSchedulingFormValues(values, "income_mode");

    const data: IncomeFormData = {
      name: values.name as string,
      gross_amount: values.gross_amount as number,
      is_taxed: values.is_taxed as boolean,
      tax_percentage: undefined,
      is_deduction: false,
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

  const openEdit = (item: IncomeItem) => {
    setEditItem(item);
    setIsNew(false);
  };

  const closeDialog = () => {
    setEditItem(null);
    setIsNew(false);
  };

  const totalNet = income.reduce(
    (sum, item) => sum + calculateNetAmount(item, settings.tax_percentage),
    0
  );

  const content = (
    <div className="divide-y divide-gray-100 dark:divide-gray-800">
      {income.map((item) => {
        const netAmount = calculateNetAmount(item, settings.tax_percentage);
        // Pay that has already landed is ticked off, so it stops being counted
        // as still to arrive — the same tick can be undone when it hasn't.
        const occurrence = settleableOccurrence(item);
        const settled = occurrence?.settled ?? false;
        return (
          <div
            key={item.id}
            onClick={() => openEdit(item)}
            className="flex items-center gap-2 px-4 py-2 hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer"
          >
            {occurrence ? (
              <SettleToggle
                kind="income"
                itemId={item.id}
                occurrenceDate={occurrence.occurrenceDate}
                settled={settled}
                name={item.name}
              />
            ) : (
              <span className="w-4 shrink-0" aria-hidden="true" />
            )}
            <span
              className={cn(
                "flex-1 min-w-0 text-sm",
                settled
                  ? "text-gray-400 dark:text-gray-500"
                  : "text-gray-900 dark:text-gray-100"
              )}
            >
              {item.name}
              {occurrence && (
                <span className="text-gray-400 dark:text-gray-500 ml-1.5">
                  ({formatOccurrenceDate(occurrence.occurrenceDate)})
                </span>
              )}
              {item.is_taxed && (
                <span className="text-gray-400 dark:text-gray-500 ml-1.5">
                  (taxed)
                </span>
              )}
            </span>
            <span className="w-[5.5rem] text-right text-gray-400 dark:text-gray-500 text-sm">
              {formatCurrency(item.gross_amount)}
            </span>
            <span
              className={cn(
                "w-[5.5rem] text-right text-sm",
                settled
                  ? "text-gray-400 dark:text-gray-500"
                  : "text-gray-900 dark:text-gray-100"
              )}
            >
              {formatCurrency(netAmount)}
            </span>
          </div>
        );
      })}
      {income.length === 0 && (
        <div className="px-4 py-4 text-center text-gray-500 dark:text-gray-400 text-sm">
          No income items yet
        </div>
      )}
    </div>
  );

  const dialog = (
    <EditDialog
      open={editItem !== null || isNew}
      onOpenChange={(open) => !open && closeDialog()}
      title={isNew ? "Add Income" : "Edit Income"}
      fields={incomeFields}
      initialValues={
        editItem
          ? {
              name: editItem.name,
              gross_amount: editItem.gross_amount,
              is_taxed: editItem.is_taxed,
              ...getSchedulingInitialValues(editItem, "income_mode"),
            }
          : {
              name: "",
              gross_amount: 0,
              is_taxed: true,
              ...getSchedulingDefaultValues("income_mode"),
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
          title="Income"
          total={formatCurrency(totalNet)}
          totalClassName="text-green-600 dark:text-green-400"
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
          Income
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
