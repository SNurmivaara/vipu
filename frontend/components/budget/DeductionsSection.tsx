"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { IncomeItem, DeductionFormData } from "@/types";
import { createIncome, updateIncome, deleteIncome } from "@/lib/api";
import { formatCurrency, formatPercentage } from "@/lib/utils";
import { EditDialog } from "./EditDialog";
import { CollapsibleSection } from "./CollapsibleSection";
import { useToast } from "@/components/ui/Toast";

interface DeductionsSectionProps {
  deductions: IncomeItem[];
  collapsible?: boolean;
  defaultOpen?: boolean;
}

const deductionFields = [
  { name: "name", label: "Name", type: "text" as const, required: true },
  {
    name: "gross_amount",
    label: "Loaded Amount (€)",
    type: "number" as const,
    required: true,
    min: 0,
    step: 0.01,
  },
  {
    name: "tax_percentage",
    label: "Deduction Rate (%)",
    type: "number" as const,
    required: true,
    min: 0,
    max: 100,
    step: 0.1,
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
  collapsible = false,
  defaultOpen = false,
}: DeductionsSectionProps) {
  const [editItem, setEditItem] = useState<IncomeItem | null>(null);
  const [isNew, setIsNew] = useState(false);
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const createMutation = useMutation({
    mutationFn: createIncome,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["budget"] });
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
      queryClient.invalidateQueries({ queryKey: ["budget"] });
      toast({ title: "Deduction updated", type: "success" });
    },
    onError: () => {
      toast({ title: "Failed to update deduction", type: "error" });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteIncome,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["budget"] });
      toast({ title: "Deduction deleted", type: "success" });
    },
    onError: () => {
      toast({ title: "Failed to delete deduction", type: "error" });
    },
  });

  const handleSave = (values: Record<string, string | number | boolean>) => {
    const data: DeductionFormData = {
      name: values.name as string,
      gross_amount: values.gross_amount as number,
      is_taxed: true,
      tax_percentage: values.tax_percentage as number,
      is_deduction: true,
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

  const totalDeduction = deductions.reduce(
    (sum, item) => sum + calculateNetAmount(item),
    0
  );

  const content = (
    <div className="divide-y divide-gray-100 dark:divide-gray-800">
      <div className="grid grid-cols-4 px-4 py-2 text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">
        <span>Name</span>
        <span className="text-right">Loaded</span>
        <span className="text-right">Rate</span>
        <span className="text-right">Deducted</span>
      </div>
      {deductions.map((item) => {
        const netAmount = calculateNetAmount(item);
        return (
          <div
            key={item.id}
            onClick={() => openEdit(item)}
            className="grid grid-cols-4 px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer"
          >
            <span className="text-gray-900 dark:text-gray-100">
              {item.name}
            </span>
            <span className="text-right text-gray-700 dark:text-gray-300">
              {formatCurrency(item.gross_amount)}
            </span>
            <span className="text-right text-gray-500 dark:text-gray-400">
              {formatPercentage(item.tax_percentage ?? 0)}
            </span>
            <span className="text-right font-medium text-red-600 dark:text-red-400">
              {formatCurrency(netAmount)}
            </span>
          </div>
        );
      })}
      {deductions.length === 0 && (
        <div className="px-4 py-6 text-center text-gray-500 dark:text-gray-400">
          No deductions yet
        </div>
      )}
      {deductions.length > 0 && (
        <div className="grid grid-cols-4 px-4 py-3 bg-gray-50 dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700">
          <span className="font-semibold text-gray-900 dark:text-gray-100">
            Total
          </span>
          <span className="text-right text-gray-700 dark:text-gray-300">
            —
          </span>
          <span className="text-right text-gray-500 dark:text-gray-400">
            —
          </span>
          <span className="text-right font-semibold text-red-600 dark:text-red-400">
            {formatCurrency(totalDeduction)}
          </span>
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
            }
          : {
              name: "",
              gross_amount: 0,
              tax_percentage: 75,
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
          total={formatCurrency(totalDeduction)}
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
