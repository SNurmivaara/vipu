"use client";

import { useState, useEffect } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { GoalFormData, GoalType, NetWorthCategory, RoadmapStep } from "@/types";

interface RoadmapFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  categories: NetWorthCategory[];
  step?: RoadmapStep | null;
  onSave: (data: GoalFormData) => void;
  onDelete?: () => void;
  isNew: boolean;
}

const STEP_TYPES: { value: GoalType; label: string; description: string }[] = [
  {
    value: "savings_goal",
    label: "Save up",
    description: "Build a fund toward a target amount",
  },
  {
    value: "debt_payoff",
    label: "Pay off debt",
    description: "Clear a debt, then move on to the next goal",
  },
];

interface StepFormValues {
  name: string;
  goal_type: GoalType;
  target_value: number;
  // For savings: amount already saved. For debt: remaining debt.
  progress_input: number;
  category_id: number | null;
  is_active: boolean;
}

const DEFAULT_VALUES: StepFormValues = {
  name: "",
  goal_type: "savings_goal",
  target_value: 0,
  progress_input: 0,
  category_id: null,
  is_active: true,
};

function toFormValues(step: RoadmapStep): StepFormValues {
  const goal = step.goal;
  const current = goal.current_amount ?? 0;
  return {
    name: goal.name,
    goal_type: goal.goal_type,
    target_value: goal.target_value,
    progress_input:
      goal.goal_type === "debt_payoff"
        ? Math.max(0, goal.target_value - current)
        : current,
    category_id: goal.category_id,
    is_active: goal.is_active,
  };
}

export function RoadmapFormDialog({
  open,
  onOpenChange,
  categories,
  step,
  onSave,
  onDelete,
  isNew,
}: RoadmapFormDialogProps) {
  const [values, setValues] = useState<StepFormValues>(DEFAULT_VALUES);

  useEffect(() => {
    if (open) {
      setValues(step ? toFormValues(step) : DEFAULT_VALUES);
    }
  }, [open, step]);

  const isDebt = values.goal_type === "debt_payoff";
  const hasCategory = !isDebt && values.category_id !== null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // The dialog asks for "remaining debt" (what a loan statement shows);
    // the API stores progress as the amount paid off so far.
    const current_amount = isDebt
      ? Math.max(0, values.target_value - values.progress_input)
      : values.progress_input;
    onSave({
      name: values.name,
      goal_type: values.goal_type,
      target_value: values.target_value,
      category_id: isDebt ? null : values.category_id,
      current_amount: hasCategory ? null : current_amount,
      target_date: null,
      is_active: values.is_active,
    });
    onOpenChange(false);
  };

  const handleDelete = () => {
    if (onDelete) {
      onDelete();
      onOpenChange(false);
    }
  };

  // Group categories by their group name for the select dropdown
  const categoriesByGroup = categories.reduce(
    (acc, cat) => {
      const groupName = cat.group?.name ?? "Other";
      if (!acc[groupName]) {
        acc[groupName] = [];
      }
      acc[groupName].push(cat);
      return acc;
    },
    {} as Record<string, NetWorthCategory[]>
  );

  const isValid = values.name.trim() !== "" && values.target_value > 0;

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50" />
        <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 bg-white dark:bg-gray-900 rounded-lg p-6 w-full max-w-md shadow-lg">
          <Dialog.Title className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
            {isNew ? "Add Roadmap Goal" : "Edit Roadmap Goal"}
          </Dialog.Title>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Name
              </label>
              <input
                type="text"
                value={values.name}
                onChange={(e) => setValues({ ...values, name: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                placeholder="e.g., Emergency fund"
                maxLength={100}
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Type
              </label>
              <select
                value={values.goal_type}
                onChange={(e) =>
                  setValues({
                    ...values,
                    goal_type: e.target.value as GoalType,
                    category_id: null,
                  })
                }
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
              >
                {STEP_TYPES.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                {STEP_TYPES.find((t) => t.value === values.goal_type)?.description}
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {isDebt ? "Total debt to pay off (€)" : "Target amount (€)"}
              </label>
              <input
                type="number"
                value={values.target_value}
                onChange={(e) =>
                  setValues({
                    ...values,
                    target_value: parseFloat(e.target.value) || 0,
                  })
                }
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                min={0}
                max={1000000000}
                step={0.01}
                required
              />
            </div>

            {!hasCategory && (
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  {isDebt ? "Remaining debt (€)" : "Already saved (€)"}
                </label>
                <input
                  type="number"
                  value={values.progress_input}
                  onChange={(e) =>
                    setValues({
                      ...values,
                      progress_input: parseFloat(e.target.value) || 0,
                    })
                  }
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                  min={0}
                  max={1000000000}
                  step={0.01}
                />
              </div>
            )}

            {!isDebt && (
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Track from wealth category (optional)
                </label>
                <select
                  value={values.category_id ?? ""}
                  onChange={(e) =>
                    setValues({
                      ...values,
                      category_id: e.target.value
                        ? parseInt(e.target.value)
                        : null,
                    })
                  }
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                >
                  <option value="">Manual — update the saved amount yourself</option>
                  {Object.entries(categoriesByGroup).map(([groupName, cats]) => (
                    <optgroup key={groupName} label={groupName}>
                      {cats.map((cat) => (
                        <option key={cat.id} value={cat.id}>
                          {cat.name}
                        </option>
                      ))}
                    </optgroup>
                  ))}
                </select>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  Linked goals read their progress from your latest net worth
                  snapshot
                </p>
              </div>
            )}

            {!isNew && (
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="roadmap_is_active"
                  checked={values.is_active}
                  onChange={(e) =>
                    setValues({ ...values, is_active: e.target.checked })
                  }
                  className="rounded border-gray-300 dark:border-gray-600"
                />
                <label
                  htmlFor="roadmap_is_active"
                  className="text-sm text-gray-700 dark:text-gray-300"
                >
                  Active (show on the roadmap)
                </label>
              </div>
            )}

            <div className="flex justify-between pt-4">
              <div>
                {!isNew && onDelete && (
                  <button
                    type="button"
                    onClick={handleDelete}
                    className="px-4 py-2 text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300"
                  >
                    Delete
                  </button>
                )}
              </div>
              <div className="flex gap-2">
                <Dialog.Close asChild>
                  <button
                    type="button"
                    className="px-4 py-2 text-gray-600 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200"
                  >
                    Cancel
                  </button>
                </Dialog.Close>
                <button
                  type="submit"
                  disabled={!isValid}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isNew ? "Create" : "Save"}
                </button>
              </div>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
