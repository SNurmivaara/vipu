"use client";

import { useState, useEffect } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { GoalFormData } from "@/types";

// Net worth goals only — roadmap goals are edited via RoadmapFormDialog.

interface GoalFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialValues?: GoalFormData;
  onSave: (data: GoalFormData) => void;
  onDelete?: () => void;
  isNew: boolean;
}

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

  const isValid = values.name.trim() !== "" && values.target_value > 0;

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50" />
        <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white dark:bg-gray-900 rounded-lg p-6 w-full max-w-md shadow-lg">
          <Dialog.Title className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
            {isNew ? "Add Net Worth Goal" : "Edit Net Worth Goal"}
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
                Target Amount (€)
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
