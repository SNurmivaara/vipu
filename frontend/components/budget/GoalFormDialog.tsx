"use client";

import { useState, useEffect } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { GoalFormData, GoalType, NetWorthCategory } from "@/types";

interface GoalFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  categories: NetWorthCategory[];
  initialValues?: GoalFormData;
  onSave: (data: GoalFormData) => void;
  onDelete?: () => void;
  isNew: boolean;
}

const GOAL_TYPES: { value: GoalType; label: string; description: string }[] = [
  {
    value: "net_worth",
    label: "Net Worth Goal",
    description: "Track total net worth against a target",
  },
  {
    value: "savings_rate",
    label: "Savings Rate",
    description: "Track % of income saved monthly",
  },
  {
    value: "savings_goal",
    label: "Savings Goal",
    description: "Track a category balance against a target",
  },
];

const DEFAULT_VALUES: GoalFormData = {
  name: "",
  goal_type: "net_worth",
  target_value: 0,
  category_id: null,
  target_date: null,
  is_active: true,
};

export function GoalFormDialog({
  open,
  onOpenChange,
  categories,
  initialValues,
  onSave,
  onDelete,
  isNew,
}: GoalFormDialogProps) {
  const [values, setValues] = useState<GoalFormData>(
    initialValues ?? DEFAULT_VALUES
  );

  useEffect(() => {
    if (open) {
      setValues(initialValues ?? DEFAULT_VALUES);
    }
  }, [open, initialValues]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave(values);
    onOpenChange(false);
  };

  const handleDelete = () => {
    if (onDelete) {
      onDelete();
      onOpenChange(false);
    }
  };

  const needsCategory = values.goal_type === "savings_goal";
  const isPercentage = values.goal_type === "savings_rate";

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

  const isValid =
    values.name.trim() !== "" &&
    values.target_value > 0 &&
    (!needsCategory || values.category_id !== null);

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50" />
        <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white dark:bg-gray-900 rounded-lg p-6 w-full max-w-md shadow-lg">
          <Dialog.Title className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
            {isNew ? "Add Goal" : "Edit Goal"}
          </Dialog.Title>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Name
              </label>
              <input
                type="text"
                value={values.name}
                onChange={(e) =>
                  setValues({ ...values, name: e.target.value })
                }
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                placeholder="e.g., Reach €100k net worth"
                maxLength={100}
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Goal Type
              </label>
              <select
                value={values.goal_type}
                onChange={(e) =>
                  setValues({
                    ...values,
                    goal_type: e.target.value as GoalType,
                    category_id:
                      e.target.value === "savings_goal"
                        ? values.category_id
                        : null,
                  })
                }
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
              >
                {GOAL_TYPES.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                {GOAL_TYPES.find((t) => t.value === values.goal_type)
                  ?.description}
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                {isPercentage ? "Target Percentage (%)" : "Target Amount (€)"}
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
                max={isPercentage ? 100 : 1000000000}
                step={isPercentage ? 0.1 : 0.01}
                required
              />
            </div>

            {needsCategory && (
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Category
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
                  required
                >
                  <option value="">Select a category</option>
                  {Object.entries(categoriesByGroup).map(
                    ([groupName, cats]) => (
                      <optgroup key={groupName} label={groupName}>
                        {cats.map((cat) => (
                          <option key={cat.id} value={cat.id}>
                            {cat.name}
                          </option>
                        ))}
                      </optgroup>
                    )
                  )}
                </select>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Target Date (optional)
              </label>
              <input
                type="date"
                value={values.target_date?.split("T")[0] ?? ""}
                onChange={(e) =>
                  setValues({
                    ...values,
                    target_date: e.target.value
                      ? new Date(e.target.value).toISOString()
                      : null,
                  })
                }
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
              />
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                Set a deadline to track if you&apos;re on pace
              </p>
            </div>

            {!isNew && (
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="is_active"
                  checked={values.is_active}
                  onChange={(e) =>
                    setValues({ ...values, is_active: e.target.checked })
                  }
                  className="rounded border-gray-300 dark:border-gray-600"
                />
                <label
                  htmlFor="is_active"
                  className="text-sm text-gray-700 dark:text-gray-300"
                >
                  Active (show in progress)
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
