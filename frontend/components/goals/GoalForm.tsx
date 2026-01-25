"use client";

import { useState, useEffect } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import * as Select from "@radix-ui/react-select";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Goal, GoalType, TrackingPeriod, NetWorthCategory } from "@/types";
import { createGoal, updateGoal } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import { useNetWorthCategories } from "@/hooks/useNetWorth";

interface GoalFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  existingGoal?: Goal | null;
}

const GOAL_TYPES: { value: GoalType; label: string; description: string }[] = [
  {
    value: "net_worth_target",
    label: "Net Worth Target",
    description: "Track progress toward a total net worth goal",
  },
  {
    value: "category_target",
    label: "Category Target",
    description: "Target balance for a specific category/account",
  },
  {
    value: "category_monthly",
    label: "Monthly Contribution",
    description: "Track average monthly change in a category",
  },
  {
    value: "category_rate",
    label: "Savings Rate",
    description: "Percentage of income as change in a category",
  },
];

const TRACKING_PERIODS: {
  value: TrackingPeriod;
  label: string;
  description: string;
}[] = [
  { value: "month", label: "Month", description: "Last month only" },
  { value: "quarter", label: "Quarter", description: "Average over 3 months" },
  {
    value: "half_year",
    label: "Half Year",
    description: "Average over 6 months",
  },
  { value: "year", label: "Year", description: "Average over 12 months" },
];

export function GoalForm({ open, onOpenChange, existingGoal }: GoalFormProps) {
  const [name, setName] = useState("");
  const [goalType, setGoalType] = useState<GoalType>("net_worth_target");
  const [targetValue, setTargetValue] = useState("");
  const [categoryId, setCategoryId] = useState<number | null>(null);
  const [trackingPeriod, setTrackingPeriod] =
    useState<TrackingPeriod>("quarter");
  const [targetDate, setTargetDate] = useState("");
  const [isActive, setIsActive] = useState(true);

  const { data: categories = [] } = useNetWorthCategories();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const isEditing = !!existingGoal;

  // Does this goal type need a category?
  const needsCategory =
    goalType === "category_target" ||
    goalType === "category_monthly" ||
    goalType === "category_rate";

  // Does this goal type need a tracking period?
  const needsTrackingPeriod =
    goalType === "category_monthly" || goalType === "category_rate";

  useEffect(() => {
    if (open) {
      if (existingGoal) {
        setName(existingGoal.name);
        setGoalType(existingGoal.goal_type);
        setTargetValue(String(existingGoal.target_value));
        setCategoryId(existingGoal.category_id);
        setTrackingPeriod(existingGoal.tracking_period || "quarter");
        setTargetDate(
          existingGoal.target_date
            ? existingGoal.target_date.split("T")[0]
            : ""
        );
        setIsActive(existingGoal.is_active);
      } else {
        setName("");
        setGoalType("net_worth_target");
        setTargetValue("");
        setCategoryId(null);
        setTrackingPeriod("quarter");
        setTargetDate("");
        setIsActive(true);
      }
    }
  }, [open, existingGoal]);

  const createMutation = useMutation({
    mutationFn: createGoal,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["goals"] });
      queryClient.invalidateQueries({ queryKey: ["goals-progress"] });
      toast({ title: "Goal created", type: "success" });
      onOpenChange(false);
    },
    onError: () => {
      toast({ title: "Failed to create goal", type: "error" });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: number;
      data: Parameters<typeof updateGoal>[1];
    }) => updateGoal(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["goals"] });
      queryClient.invalidateQueries({ queryKey: ["goals-progress"] });
      toast({ title: "Goal updated", type: "success" });
      onOpenChange(false);
    },
    onError: () => {
      toast({ title: "Failed to update goal", type: "error" });
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const parsedValue = parseFloat(targetValue) || 0;
    const formattedDate = targetDate
      ? new Date(targetDate + "T00:00:00Z").toISOString()
      : null;

    const goalData = {
      name,
      goal_type: goalType,
      target_value: parsedValue,
      category_id: needsCategory ? categoryId : null,
      tracking_period: needsTrackingPeriod ? trackingPeriod : null,
      target_date: formattedDate,
      is_active: isActive,
    };

    if (isEditing && existingGoal) {
      updateMutation.mutate({
        id: existingGoal.id,
        data: goalData,
      });
    } else {
      createMutation.mutate(goalData);
    }
  };

  const isPending = createMutation.isPending || updateMutation.isPending;

  const getValueLabel = () => {
    switch (goalType) {
      case "category_rate":
        return "Target Percentage (%)";
      case "category_monthly":
        return "Monthly Amount (EUR)";
      default:
        return "Target Amount (EUR)";
    }
  };

  const getValuePlaceholder = () => {
    switch (goalType) {
      case "category_rate":
        return "30";
      case "category_monthly":
        return "500";
      default:
        return "100000";
    }
  };

  const canSubmit =
    name &&
    targetValue &&
    (!needsCategory || categoryId !== null) &&
    (!needsTrackingPeriod || trackingPeriod);

  // Group categories by their group name for better UX
  const categoriesByGroup = categories.reduce(
    (acc, cat) => {
      const groupName = cat.group?.name || "Other";
      if (!acc[groupName]) acc[groupName] = [];
      acc[groupName].push(cat);
      return acc;
    },
    {} as Record<string, NetWorthCategory[]>
  );

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50" />
        <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-md bg-white dark:bg-gray-900 rounded-lg shadow-xl p-6 max-h-[90vh] overflow-y-auto">
          <Dialog.Title className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">
            {isEditing ? "Edit Goal" : "Create Goal"}
          </Dialog.Title>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Name */}
            <div>
              <label
                htmlFor="goal-name"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
              >
                Goal Name
              </label>
              <input
                type="text"
                id="goal-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Hit 100k net worth"
                required
                maxLength={100}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            {/* Goal Type */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Goal Type
              </label>
              <Select.Root
                value={goalType}
                onValueChange={(val) => setGoalType(val as GoalType)}
              >
                <Select.Trigger className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-left flex justify-between items-center focus:outline-none focus:ring-2 focus:ring-blue-500">
                  <Select.Value />
                  <Select.Icon className="text-gray-500">
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path
                        d="M3 4.5L6 7.5L9 4.5"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </Select.Icon>
                </Select.Trigger>
                <Select.Portal>
                  <Select.Content className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md shadow-lg z-[100] overflow-hidden">
                    <Select.Viewport className="p-1">
                      {GOAL_TYPES.map((type) => (
                        <Select.Item
                          key={type.value}
                          value={type.value}
                          className="px-3 py-2 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 rounded text-gray-900 dark:text-gray-100 outline-none"
                        >
                          <Select.ItemText>{type.label}</Select.ItemText>
                        </Select.Item>
                      ))}
                    </Select.Viewport>
                  </Select.Content>
                </Select.Portal>
              </Select.Root>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                {GOAL_TYPES.find((t) => t.value === goalType)?.description}
              </p>
            </div>

            {/* Category (for category-based goals) */}
            {needsCategory && (
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Category
                </label>
                <Select.Root
                  value={categoryId?.toString() || ""}
                  onValueChange={(val) => setCategoryId(Number(val))}
                >
                  <Select.Trigger className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-left flex justify-between items-center focus:outline-none focus:ring-2 focus:ring-blue-500">
                    <Select.Value placeholder="Select a category" />
                    <Select.Icon className="text-gray-500">
                      <svg
                        width="12"
                        height="12"
                        viewBox="0 0 12 12"
                        fill="none"
                      >
                        <path
                          d="M3 4.5L6 7.5L9 4.5"
                          stroke="currentColor"
                          strokeWidth="1.5"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    </Select.Icon>
                  </Select.Trigger>
                  <Select.Portal>
                    <Select.Content className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md shadow-lg z-[100] overflow-hidden max-h-60">
                      <Select.Viewport className="p-1">
                        {Object.entries(categoriesByGroup).map(
                          ([groupName, cats]) => (
                            <Select.Group key={groupName}>
                              <Select.Label className="px-3 py-1 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase">
                                {groupName}
                              </Select.Label>
                              {cats.map((cat) => (
                                <Select.Item
                                  key={cat.id}
                                  value={cat.id.toString()}
                                  className="px-3 py-2 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 rounded text-gray-900 dark:text-gray-100 outline-none"
                                >
                                  <Select.ItemText>{cat.name}</Select.ItemText>
                                </Select.Item>
                              ))}
                            </Select.Group>
                          )
                        )}
                      </Select.Viewport>
                    </Select.Content>
                  </Select.Portal>
                </Select.Root>
                {categories.length === 0 && (
                  <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">
                    No categories found. Create categories first.
                  </p>
                )}
              </div>
            )}

            {/* Tracking Period (for monthly/rate goals) */}
            {needsTrackingPeriod && (
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Tracking Period
                </label>
                <Select.Root
                  value={trackingPeriod}
                  onValueChange={(val) =>
                    setTrackingPeriod(val as TrackingPeriod)
                  }
                >
                  <Select.Trigger className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-left flex justify-between items-center focus:outline-none focus:ring-2 focus:ring-blue-500">
                    <Select.Value />
                    <Select.Icon className="text-gray-500">
                      <svg
                        width="12"
                        height="12"
                        viewBox="0 0 12 12"
                        fill="none"
                      >
                        <path
                          d="M3 4.5L6 7.5L9 4.5"
                          stroke="currentColor"
                          strokeWidth="1.5"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    </Select.Icon>
                  </Select.Trigger>
                  <Select.Portal>
                    <Select.Content className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md shadow-lg z-[100] overflow-hidden">
                      <Select.Viewport className="p-1">
                        {TRACKING_PERIODS.map((period) => (
                          <Select.Item
                            key={period.value}
                            value={period.value}
                            className="px-3 py-2 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 rounded text-gray-900 dark:text-gray-100 outline-none"
                          >
                            <Select.ItemText>{period.label}</Select.ItemText>
                          </Select.Item>
                        ))}
                      </Select.Viewport>
                    </Select.Content>
                  </Select.Portal>
                </Select.Root>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {
                    TRACKING_PERIODS.find((p) => p.value === trackingPeriod)
                      ?.description
                  }
                </p>
              </div>
            )}

            {/* Target Value */}
            <div>
              <label
                htmlFor="target-value"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
              >
                {getValueLabel()}
              </label>
              <input
                type="number"
                id="target-value"
                value={targetValue}
                onChange={(e) => setTargetValue(e.target.value)}
                placeholder={getValuePlaceholder()}
                required
                min={0}
                max={goalType === "category_rate" ? 100 : 1000000000}
                step={goalType === "category_rate" ? 0.1 : 1}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            {/* Target Date (optional) */}
            <div>
              <label
                htmlFor="target-date"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1"
              >
                Target Date (optional)
              </label>
              <input
                type="date"
                id="target-date"
                value={targetDate}
                onChange={(e) => setTargetDate(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Set a deadline for achieving this goal
              </p>
            </div>

            {/* Active Toggle (only when editing) */}
            {isEditing && (
              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  id="is-active"
                  checked={isActive}
                  onChange={(e) => setIsActive(e.target.checked)}
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <label
                  htmlFor="is-active"
                  className="text-sm text-gray-700 dark:text-gray-300"
                >
                  Active (inactive goals won&apos;t show progress)
                </label>
              </div>
            )}

            {/* Actions */}
            <div className="flex justify-end gap-3 pt-4">
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
                disabled={isPending || !canSubmit}
                className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
              >
                {isPending ? "Saving..." : isEditing ? "Update" : "Create"}
              </button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
