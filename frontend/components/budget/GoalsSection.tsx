"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  GoalProgress,
  GoalFormData,
  NetWorthCategory,
  GoalType,
} from "@/types";
import { createGoal, updateGoal, deleteGoal } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { CollapsibleSection } from "./CollapsibleSection";
import { GoalFormDialog } from "./GoalFormDialog";
import { useToast } from "@/components/ui/Toast";

interface GoalsSectionProps {
  goals: GoalProgress[];
  categories: NetWorthCategory[];
  collapsible?: boolean;
  defaultOpen?: boolean;
}

const GOAL_TYPE_LABELS: Record<string, string> = {
  net_worth: "Net Worth",
  savings_rate: "Savings Rate",
  savings_goal: "Savings Goal",
  // Backward compatibility with old goal types
  net_worth_target: "Net Worth",
  category_target: "Savings Goal",
  category_rate: "Savings Rate",
};

function getProgressColor(percentage: number, isAchieved: boolean): string {
  if (isAchieved) return "bg-green-500";
  if (percentage >= 75) return "bg-blue-500";
  if (percentage >= 50) return "bg-yellow-500";
  return "bg-orange-500";
}

function formatValue(value: number, goalType: GoalType): string {
  if (goalType === "savings_rate") {
    return `${value.toFixed(1)}%`;
  }
  return formatCurrency(value);
}

function calculateMonthlyRequired(
  currentValue: number,
  targetValue: number,
  targetDate: string | null,
  isAchieved: boolean
): number | null {
  // Don't show for achieved goals or goals without a deadline
  if (isAchieved || !targetDate) return null;

  const now = new Date();
  const target = new Date(targetDate);

  // Calculate months remaining
  const monthsRemaining =
    (target.getFullYear() - now.getFullYear()) * 12 +
    (target.getMonth() - now.getMonth());

  // If deadline passed or less than 1 month, don't show
  if (monthsRemaining < 1) return null;

  const remaining = targetValue - currentValue;
  if (remaining <= 0) return null;

  return remaining / monthsRemaining;
}

export function GoalsSection({
  goals,
  categories,
  collapsible = false,
  defaultOpen = false,
}: GoalsSectionProps) {
  const [editGoal, setEditGoal] = useState<GoalProgress | null>(null);
  const [isNew, setIsNew] = useState(false);
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const createMutation = useMutation({
    mutationFn: createGoal,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["goals-progress"] });
      toast({ title: "Goal created", type: "success" });
    },
    onError: () => {
      toast({ title: "Failed to create goal", type: "error" });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<GoalFormData> }) =>
      updateGoal(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["goals-progress"] });
      toast({ title: "Goal updated", type: "success" });
    },
    onError: () => {
      toast({ title: "Failed to update goal", type: "error" });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteGoal,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["goals-progress"] });
      toast({ title: "Goal deleted", type: "success" });
    },
    onError: () => {
      toast({ title: "Failed to delete goal", type: "error" });
    },
  });

  const handleSave = (data: GoalFormData) => {
    if (isNew) {
      createMutation.mutate(data);
    } else if (editGoal) {
      updateMutation.mutate({ id: editGoal.goal.id, data });
    }
  };

  const handleDelete = () => {
    if (editGoal) {
      deleteMutation.mutate(editGoal.goal.id);
    }
  };

  const openNew = () => {
    setEditGoal(null);
    setIsNew(true);
  };

  const openEdit = (goalProgress: GoalProgress) => {
    setEditGoal(goalProgress);
    setIsNew(false);
  };

  const closeDialog = () => {
    setEditGoal(null);
    setIsNew(false);
  };

  const content = (
    <div className="divide-y divide-gray-100 dark:divide-gray-800">
      {goals.map((gp) => (
        <div
          key={gp.goal.id}
          onClick={() => openEdit(gp)}
          className="px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer"
        >
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="text-gray-900 dark:text-gray-100 font-medium">
                {gp.goal.name}
              </span>
              <span className="text-sm px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300">
                {GOAL_TYPE_LABELS[gp.goal.goal_type]}
              </span>
              {/* Monthly required for numeric goals with deadlines */}
              {!["savings_rate", "category_rate"].includes(gp.goal.goal_type) && (() => {
                const monthlyRequired = calculateMonthlyRequired(
                  gp.current_value,
                  gp.target_value,
                  gp.goal.target_date,
                  gp.is_achieved
                );
                if (monthlyRequired === null) return null;
                return (
                  <span className="text-sm text-gray-400 dark:text-gray-500">
                    {formatCurrency(monthlyRequired)}/mo
                  </span>
                );
              })()}
              {gp.is_achieved && !["savings_rate", "category_rate"].includes(gp.goal.goal_type) && (
                <span className="text-sm px-2 py-0.5 rounded-full bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300">
                  Achieved
                </span>
              )}
            </div>
            {gp.status && (
              <span
                className={`text-sm px-2 py-0.5 rounded-full ${
                  gp.status === "on_track"
                    ? "bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300"
                    : "bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-300"
                }`}
              >
                {gp.status === "on_track" ? "On track" : "Behind"}
              </span>
            )}
          </div>

          {gp.category_name && (
            <div className="text-sm text-gray-500 dark:text-gray-400 mb-2">
              {gp.category_name}
            </div>
          )}

          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2 mb-2">
            <div
              className={`h-2 rounded-full ${getProgressColor(
                gp.progress_percentage,
                gp.is_achieved
              )}`}
              style={{ width: `${Math.min(gp.progress_percentage, 100)}%` }}
            />
          </div>

          <div className="flex justify-between text-sm text-gray-600 dark:text-gray-400">
            <span>
              {formatValue(gp.current_value, gp.goal.goal_type)} /{" "}
              {formatValue(gp.target_value, gp.goal.goal_type)}
            </span>
            <span>{gp.progress_percentage.toFixed(1)}%</span>
          </div>

          {gp.goal.goal_type === "savings_rate" && gp.data_months < 2 && (
            <div className="text-sm text-amber-600 dark:text-amber-400 mt-1">
              Needs more snapshot data
            </div>
          )}
        </div>
      ))}
      {goals.length === 0 && (
        <div className="px-4 py-6 text-center text-gray-500 dark:text-gray-400">
          No goals yet. Create one to track your progress!
        </div>
      )}
    </div>
  );

  const dialog = (
    <GoalFormDialog
      open={editGoal !== null || isNew}
      onOpenChange={(open) => !open && closeDialog()}
      categories={categories}
      initialValues={
        editGoal
          ? {
              name: editGoal.goal.name,
              goal_type: editGoal.goal.goal_type,
              target_value: editGoal.goal.target_value,
              category_id: editGoal.goal.category_id,
              target_date: editGoal.goal.target_date,
              is_active: editGoal.goal.is_active,
            }
          : undefined
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
          title="Financial Goals"
          total={`${goals.length} goal${goals.length !== 1 ? "s" : ""}`}
          totalClassName="text-gray-500 dark:text-gray-400"
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
          Financial Goals
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
