"use client";

import * as Dialog from "@radix-ui/react-dialog";
import * as Label from "@radix-ui/react-label";
import { useState, useEffect, useCallback } from "react";
import { cn } from "@/lib/utils";

interface Field {
  name: string;
  label: string;
  type: "text" | "number" | "checkbox";
  required?: boolean;
  min?: number;
  step?: number;
  placeholder?: string;
}

interface EditDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  fields: Field[];
  initialValues: Record<string, string | number | boolean>;
  onSave: (values: Record<string, string | number | boolean>) => void;
  onDelete?: () => void;
  isNew?: boolean;
}

export function EditDialog({
  open,
  onOpenChange,
  title,
  fields,
  initialValues,
  onSave,
  onDelete,
  isNew = false,
}: EditDialogProps) {
  const [values, setValues] =
    useState<Record<string, string | number | boolean>>(initialValues);

  useEffect(() => {
    if (open) {
      setValues(initialValues);
    }
  }, [open, initialValues]);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      onSave(values);
      onOpenChange(false);
    },
    [values, onSave, onOpenChange]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape") {
        onOpenChange(false);
      }
    },
    [onOpenChange]
  );

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50" />
        <Dialog.Content
          className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-md bg-white dark:bg-gray-900 rounded-lg shadow-xl p-6"
          onKeyDown={handleKeyDown}
        >
          <Dialog.Title className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">
            {title}
          </Dialog.Title>

          <form onSubmit={handleSubmit} className="space-y-4">
            {fields.map((field) => (
              <div key={field.name} className="space-y-1">
                {field.type === "checkbox" ? (
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id={field.name}
                      checked={values[field.name] as boolean}
                      onChange={(e) =>
                        setValues((prev) => ({
                          ...prev,
                          [field.name]: e.target.checked,
                        }))
                      }
                      className="h-4 w-4 rounded border-gray-300"
                    />
                    <Label.Root
                      htmlFor={field.name}
                      className="text-sm font-medium text-gray-700 dark:text-gray-300"
                    >
                      {field.label}
                    </Label.Root>
                  </div>
                ) : (
                  <>
                    <Label.Root
                      htmlFor={field.name}
                      className="text-sm font-medium text-gray-700 dark:text-gray-300"
                    >
                      {field.label}
                    </Label.Root>
                    <input
                      type={field.type}
                      id={field.name}
                      value={values[field.name] as string | number}
                      onChange={(e) =>
                        setValues((prev) => ({
                          ...prev,
                          [field.name]:
                            field.type === "number"
                              ? parseFloat(e.target.value) || 0
                              : e.target.value,
                        }))
                      }
                      required={field.required}
                      min={field.min}
                      step={field.step}
                      placeholder={field.placeholder}
                      className={cn(
                        "w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md",
                        "bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100",
                        "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      )}
                    />
                  </>
                )}
              </div>
            ))}

            <div className="flex justify-between pt-4">
              <div>
                {onDelete && !isNew && (
                  <button
                    type="button"
                    onClick={() => {
                      onDelete();
                      onOpenChange(false);
                    }}
                    className="px-4 py-2 text-sm text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300"
                  >
                    Delete
                  </button>
                )}
              </div>
              <div className="flex gap-2">
                <Dialog.Close asChild>
                  <button
                    type="button"
                    className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
                  >
                    Cancel
                  </button>
                </Dialog.Close>
                <button
                  type="submit"
                  className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
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
