"use client";

import * as Dialog from "@radix-ui/react-dialog";
import * as Label from "@radix-ui/react-label";
import { useState, useEffect, useCallback } from "react";
import { cn } from "@/lib/utils";

interface Field {
  name: string;
  label: string;
  type: "text" | "number" | "checkbox" | "signed_number";
  required?: boolean;
  min?: number;
  max?: number;
  step?: number;
  placeholder?: string;
  defaultSign?: "positive" | "negative";
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

  // Track sign state for signed_number fields
  const [signs, setSigns] = useState<Record<string, "positive" | "negative">>(
    {}
  );

  useEffect(() => {
    if (open) {
      setValues(initialValues);
      // Initialize signs based on initial values and field defaults
      const initialSigns: Record<string, "positive" | "negative"> = {};
      fields.forEach((field) => {
        if (field.type === "signed_number") {
          const value = initialValues[field.name] as number;
          if (value < 0) {
            initialSigns[field.name] = "negative";
          } else if (value > 0) {
            initialSigns[field.name] = "positive";
          } else {
            initialSigns[field.name] = field.defaultSign || "positive";
          }
        }
      });
      setSigns(initialSigns);
    }
  }, [open, initialValues, fields]);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      // Apply signs to signed_number fields
      const finalValues = { ...values };
      fields.forEach((field) => {
        if (field.type === "signed_number") {
          const absValue = Math.abs(finalValues[field.name] as number);
          finalValues[field.name] =
            signs[field.name] === "negative" ? -absValue : absValue;
        }
      });
      onSave(finalValues);
      onOpenChange(false);
    },
    [values, signs, fields, onSave, onOpenChange]
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
                ) : field.type === "signed_number" ? (
                  <>
                    <Label.Root
                      htmlFor={field.name}
                      className="text-sm font-medium text-gray-700 dark:text-gray-300"
                    >
                      {field.label}
                    </Label.Root>
                    <div className="flex">
                      <button
                        type="button"
                        onClick={() =>
                          setSigns((prev) => ({
                            ...prev,
                            [field.name]:
                              prev[field.name] === "positive"
                                ? "negative"
                                : "positive",
                          }))
                        }
                        className={cn(
                          "px-3 py-2 border border-r-0 rounded-l-md font-medium text-lg",
                          "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:z-10",
                          signs[field.name] === "negative"
                            ? "bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400 border-red-300 dark:border-red-700"
                            : "bg-emerald-100 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400 border-emerald-300 dark:border-emerald-700"
                        )}
                      >
                        {signs[field.name] === "negative" ? "−" : "+"}
                      </button>
                      <input
                        type="number"
                        id={field.name}
                        value={Math.abs(values[field.name] as number)}
                        onChange={(e) =>
                          setValues((prev) => ({
                            ...prev,
                            [field.name]: parseFloat(e.target.value) || 0,
                          }))
                        }
                        required={field.required}
                        min={0}
                        step={field.step}
                        placeholder={field.placeholder}
                        className={cn(
                          "flex-1 px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-r-md",
                          "bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100",
                          "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        )}
                      />
                    </div>
                  </>
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
