"use client";

import * as Dialog from "@radix-ui/react-dialog";
import * as Label from "@radix-ui/react-label";
import { useState, useEffect, useCallback } from "react";
import { cn } from "@/lib/utils";
import { FrequencyUnit } from "@/types";
import { FrequencyPicker } from "./FrequencyPicker";
import { SegmentedControl } from "@/components/ui/SegmentedControl";

interface SelectOption {
  value: string;
  label: string;
}

interface Field {
  name: string;
  label: string;
  type: "text" | "number" | "checkbox" | "signed_number" | "frequency" | "date" | "due_day" | "select" | "segment";
  required?: boolean;
  min?: number;
  max?: number;
  step?: number;
  placeholder?: string;
  defaultSign?: "positive" | "negative";
  // For frequency fields, specify the unit field name
  unitFieldName?: string;
  // For select fields
  options?: SelectOption[];
  // Conditional visibility: show field only when condition is met
  showWhen?: { field: string; value: string | boolean };
  hideWhen?: { field: string; value: string | boolean };
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
      // Numeric fields are edited as raw strings (so they can be cleared and
      // typed freely). Coerce them to clamped numbers here so the API never
      // receives an empty string or an out-of-range value, and apply the sign
      // for signed_number fields.
      const finalValues = { ...values };
      fields.forEach((field) => {
        if (field.type !== "number" && field.type !== "signed_number") return;

        let num = parseFloat(String(finalValues[field.name]));
        if (Number.isNaN(num)) num = field.min ?? 0;

        if (field.type === "signed_number") {
          num = Math.abs(num);
          if (field.max !== undefined) num = Math.min(field.max, num);
          finalValues[field.name] =
            signs[field.name] === "negative" ? -num : num;
        } else {
          if (field.min !== undefined) num = Math.max(field.min, num);
          if (field.max !== undefined) num = Math.min(field.max, num);
          finalValues[field.name] = num;
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
            {fields.map((field) => {
              // Check conditional visibility
              if (field.showWhen && values[field.showWhen.field] !== field.showWhen.value) {
                return null;
              }
              if (field.hideWhen && values[field.hideWhen.field] === field.hideWhen.value) {
                return null;
              }
              return (
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
                        // Raw string while editing (clearable); sign is applied
                        // and the value coerced on submit.
                        value={
                          values[field.name] === ""
                            ? ""
                            : Math.abs(Number(values[field.name]) || 0)
                        }
                        onChange={(e) =>
                          setValues((prev) => ({
                            ...prev,
                            [field.name]: e.target.value,
                          }))
                        }
                        required={field.required}
                        min={0}
                        max={field.max}
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
                ) : field.type === "frequency" ? (
                  <>
                    <Label.Root
                      htmlFor={field.name}
                      className="text-sm font-medium text-gray-700 dark:text-gray-300"
                    >
                      {field.label}
                    </Label.Root>
                    <FrequencyPicker
                      value={values[field.name] as number}
                      unit={(values[field.unitFieldName || "frequency_unit"] as FrequencyUnit) || "months"}
                      onValueChange={(v) =>
                        setValues((prev) => ({ ...prev, [field.name]: v }))
                      }
                      onUnitChange={(u) =>
                        setValues((prev) => ({
                          ...prev,
                          [field.unitFieldName || "frequency_unit"]: u,
                        }))
                      }
                    />
                  </>
                ) : field.type === "date" ? (
                  <>
                    <Label.Root
                      htmlFor={field.name}
                      className="text-sm font-medium text-gray-700 dark:text-gray-300"
                    >
                      {field.label}
                    </Label.Root>
                    <input
                      type="date"
                      id={field.name}
                      value={(values[field.name] as string) || ""}
                      onChange={(e) =>
                        setValues((prev) => ({
                          ...prev,
                          [field.name]: e.target.value,
                        }))
                      }
                      className={cn(
                        "w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md",
                        "bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100",
                        "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      )}
                    />
                  </>
                ) : field.type === "select" ? (
                  <>
                    <Label.Root
                      htmlFor={field.name}
                      className="text-sm font-medium text-gray-700 dark:text-gray-300"
                    >
                      {field.label}
                    </Label.Root>
                    <select
                      id={field.name}
                      value={(values[field.name] as string) || ""}
                      onChange={(e) =>
                        setValues((prev) => ({
                          ...prev,
                          [field.name]: e.target.value,
                        }))
                      }
                      className={cn(
                        "w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md",
                        "bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100",
                        "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      )}
                    >
                      {field.options?.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </>
                ) : field.type === "segment" ? (
                  <>
                    {field.label && (
                      <Label.Root
                        htmlFor={field.name}
                        className="text-sm font-medium text-gray-700 dark:text-gray-300"
                      >
                        {field.label}
                      </Label.Root>
                    )}
                    <SegmentedControl
                      options={field.options || []}
                      value={(values[field.name] as string) || ""}
                      onChange={(v) =>
                        setValues((prev) => ({
                          ...prev,
                          [field.name]: v,
                        }))
                      }
                    />
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
                      // Keep the raw string while editing so the field can be
                      // cleared and retyped (no forced 0); coerced on submit.
                      value={(values[field.name] as string | number) ?? ""}
                      onChange={(e) =>
                        setValues((prev) => ({
                          ...prev,
                          [field.name]: e.target.value,
                        }))
                      }
                      required={field.required}
                      min={field.min}
                      max={field.max}
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
            );
            })}

            <div className="flex justify-between pt-4">
              <div>
                {onDelete && !isNew && (
                  <button
                    type="button"
                    onClick={() => {
                      onDelete();
                      onOpenChange(false);
                    }}
                    className="px-4 py-2 text-sm text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
                  >
                    Delete
                  </button>
                )}
              </div>
              <div className="flex gap-2">
                <Dialog.Close asChild>
                  <button
                    type="button"
                    className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gray-500"
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
