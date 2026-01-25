"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { IncomeItem, IncomeFormData, BudgetSettings } from "@/types";
import { createIncome, updateIncome, deleteIncome } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { EditDialog } from "./EditDialog";
import { CollapsibleSection } from "./CollapsibleSection";
import { useToast } from "@/components/ui/Toast";

interface IncomeSectionProps {
  income: IncomeItem[];
  settings: BudgetSettings;
  collapsible?: boolean;
  defaultOpen?: boolean;
}

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
  { name: "is_taxed", label: "Is Taxed", type: "checkbox" as const },
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
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const createMutation = useMutation({
    mutationFn: createIncome,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["budget"] });
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
      queryClient.invalidateQueries({ queryKey: ["budget"] });
      toast({ title: "Income updated", type: "success" });
    },
    onError: () => {
      toast({ title: "Failed to update income", type: "error" });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteIncome,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["budget"] });
      toast({ title: "Income deleted", type: "success" });
    },
    onError: () => {
      toast({ title: "Failed to delete income", type: "error" });
    },
  });

  const handleSave = (values: Record<string, string | number | boolean>) => {
    const data: IncomeFormData = {
      name: values.name as string,
      gross_amount: values.gross_amount as number,
      is_taxed: values.is_taxed as boolean,
      tax_percentage: undefined,
      is_deduction: false,
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
      <div className="grid grid-cols-3 px-4 py-2 text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">
        <span>Name</span>
        <span className="text-right">Gross</span>
        <span className="text-right">Net</span>
      </div>
      {income.map((item) => {
        const netAmount = calculateNetAmount(item, settings.tax_percentage);
        return (
          <div
            key={item.id}
            onClick={() => openEdit(item)}
            className="grid grid-cols-3 px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer"
          >
            <span className="text-gray-900 dark:text-gray-100">
              {item.name}
              {item.is_taxed && (
                <span className="ml-2 text-xs text-gray-500 dark:text-gray-400">
                  (taxed)
                </span>
              )}
            </span>
            <span className="text-right text-gray-700 dark:text-gray-300">
              {formatCurrency(item.gross_amount)}
            </span>
            <span className="text-right font-medium text-gray-900 dark:text-gray-100">
              {formatCurrency(netAmount)}
            </span>
          </div>
        );
      })}
      {income.length === 0 && (
        <div className="px-4 py-6 text-center text-gray-500 dark:text-gray-400">
          No income items yet
        </div>
      )}
      {income.length > 0 && (
        <div className="grid grid-cols-3 px-4 py-3 bg-gray-50 dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700">
          <span className="font-semibold text-gray-900 dark:text-gray-100">
            Total
          </span>
          <span className="text-right font-semibold text-gray-900 dark:text-gray-100">
            {formatCurrency(
              income.reduce((sum, item) => sum + item.gross_amount, 0)
            )}
          </span>
          <span className="text-right font-semibold text-gray-900 dark:text-gray-100">
            {formatCurrency(totalNet)}
          </span>
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
            }
          : {
              name: "",
              gross_amount: 0,
              is_taxed: true,
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
