"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useInvalidateBudget } from "@/hooks/useInvalidateBudget";
import { IncomeItem, IncomeWithOccurrence, DeductionFormData } from "@/types";
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

interface DeductionsSectionProps {
  deductions: IncomeWithOccurrence[];
  /** Deductions coming out of the next pay period, negative */
  nextPeriodTotal: number;
  collapsible?: boolean;
  defaultOpen?: boolean;
}

// deduction_mode: "monthly" (default), "one_time", "custom"
const deductionFields = [
  { name: "name", label: "Name", type: "text" as const, required: true },
  {
    name: "gross_amount",
    label: "Gross (€)",
    type: "number" as const,
    required: true,
    min: 0,
    step: 0.01,
  },
  {
    name: "tax_percentage",
    label: "Rate (%)",
    type: "number" as const,
    required: true,
    min: 0,
    max: 100,
    step: 0.1,
  },
  {
    name: "deduction_mode",
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
    showWhen: { field: "deduction_mode", value: "monthly" },
  },
  // One-time mode: date picker
  {
    name: "one_time_date",
    label: "Date",
    type: "date" as const,
    showWhen: { field: "deduction_mode", value: "one_time" },
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
    showWhen: { field: "deduction_mode", value: "custom" },
  },
  {
    name: "frequency_value",
    label: "Frequency",
    type: "frequency" as const,
    unitFieldName: "frequency_unit",
    showWhen: { field: "deduction_mode", value: "custom" },
  },
  {
    name: "start_date",
    label: "Start Date (optional)",
    type: "date" as const,
    showWhen: { field: "deduction_mode", value: "custom" },
  },
  {
    name: "end_date",
    label: "End Date (optional)",
    type: "date" as const,
    showWhen: { field: "deduction_mode", value: "custom" },
  },
];

/**
 * Calculate net amount for a deduction.
 * net = -gross * rate/100
 */
function calculateNetAmount(item: IncomeItem): number {
  const rate = item.tax_percentage ?? 0;
  return -item.gross_amount * (rate / 100);
}

export function DeductionsSection({
  deductions,
  nextPeriodTotal,
  collapsible = false,
  defaultOpen = false,
}: DeductionsSectionProps) {
  const [editItem, setEditItem] = useState<IncomeItem | null>(null);
  const [isNew, setIsNew] = useState(false);
  const invalidateBudget = useInvalidateBudget();
  const { toast } = useToast();

  const createMutation = useMutation({
    mutationFn: createIncome,
    onSuccess: () => {
      invalidateBudget();
      toast({ title: "Deduction created", type: "success" });
    },
    onError: () => {
      toast({ title: "Failed to create deduction", type: "error" });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: DeductionFormData }) =>
      updateIncome(id, data),
    onSuccess: () => {
      invalidateBudget();
      toast({ title: "Deduction updated", type: "success" });
    },
    onError: () => {
      toast({ title: "Failed to update deduction", type: "error" });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteIncome,
    onSuccess: () => {
      invalidateBudget();
      toast({ title: "Deduction deleted", type: "success" });
    },
    onError: () => {
      toast({ title: "Failed to delete deduction", type: "error" });
    },
  });

  const handleSave = (values: Record<string, string | number | boolean>) => {
    const scheduling = parseSchedulingFormValues(values, "deduction_mode");

    const data: DeductionFormData = {
      name: values.name as string,
      gross_amount: values.gross_amount as number,
      is_taxed: true,
      tax_percentage: values.tax_percentage as number,
      is_deduction: true,
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


  const content = (
    <div className="divide-y divide-gray-100 dark:divide-gray-800">
      {deductions.map((item) => {
        const netAmount = calculateNetAmount(item);
        // A deduction rides along with the pay it comes out of, so it ticks off
        // the same way — leaving it unticked would count it on its own.
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
            </span>
            <span
              className={cn(
                "text-right text-sm",
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
      {deductions.length === 0 && (
        <div className="px-4 py-4 text-center text-gray-500 dark:text-gray-400 text-sm">
          No deductions yet
        </div>
      )}
    </div>
  );

  const dialog = (
    <EditDialog
      open={editItem !== null || isNew}
      onOpenChange={(open) => !open && closeDialog()}
      title={isNew ? "Add Deduction" : "Edit Deduction"}
      fields={deductionFields}
      initialValues={
        editItem
          ? {
              name: editItem.name,
              gross_amount: editItem.gross_amount,
              tax_percentage: editItem.tax_percentage ?? 0,
              ...getSchedulingInitialValues(editItem, "deduction_mode"),
            }
          : {
              name: "",
              gross_amount: 0,
              tax_percentage: 75,
              ...getSchedulingDefaultValues("deduction_mode"),
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
          title="Deductions"
          total={formatCurrency(nextPeriodTotal)}
          totalCaption="next period"
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
          Deductions
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
