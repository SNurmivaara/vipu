"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { GoalProgress, GoalType, TrackingPeriod } from "@/types";
import { deleteGoal } from "@/lib/api";
import { formatCurrency, formatPercentage, cn } from "@/lib/utils";
import { useToast } from "@/components/ui/Toast";
import { GoalForm } from "./GoalForm";

interface GoalsListProps {
  goals: GoalProgress[];
}

const GOAL_TYPE_LABELS: Record<GoalType, string> = {
  net_worth_target: "Net Worth",
  category_target: "Category Target",
  category_monthly: "Monthly",
  category_rate: "Rate",
};

const TRACKING_PERIOD_LABELS: Record<TrackingPeriod, string> = {
  month: "1M",
  quarter: "3M",
  half_year: "6M",
  year: "1Y",
};

function formatGoalValue(goalType: GoalType, value: number): string {
  if (goalType === "category_rate") {
    return formatPercentage(value);
  }
  return formatCurrency(value);
}

function formatTargetDate(dateString: string | null): string | null {
  if (!dateString) return null;
  const date = new Date(dateString);
  return date.toLocaleDateString("fi-FI", {
    month: "short",
    year: "numeric",
  });
}

export function GoalsList({ goals }: GoalsListProps) {
  const [editingGoal, setEditingGoal] = useState<GoalProgress | null>(null);
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const deleteMutation = useMutation({
    mutationFn: deleteGoal,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["goals"] });
      queryClient.invalidateQueries({ queryKey: ["goals-progress"] });
      toast({ title: "Goal deleted", type: "success" });
    },
    onError: () => {
      toast({ title: "Failed to delete goal", type: "error" });
    },
  });

  const handleDelete = (id: number, name: string) => {
    if (confirm(`Delete goal "${name}"?`)) {
      deleteMutation.mutate(id);
    }
  };

  if (goals.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500 dark:text-gray-400">
        <p>No goals yet. Create your first goal to start tracking progress.</p>
      </div>
    );
  }

  return (
    <>
      <div className="space-y-4">
        {goals.map((item) => (
          <GoalCard
            key={item.goal.id}
            item={item}
            onEdit={() => setEditingGoal(item)}
            onDelete={() => handleDelete(item.goal.id, item.goal.name)}
          />
        ))}
      </div>

      {editingGoal && (
        <GoalForm
          open={!!editingGoal}
          onOpenChange={(open) => !open && setEditingGoal(null)}
          existingGoal={editingGoal.goal}
        />
      )}
    </>
  );
}

interface GoalCardProps {
  item: GoalProgress;
  onEdit: () => void;
  onDelete: () => void;
}

function GoalCard({ item, onEdit, onDelete }: GoalCardProps) {
  const {
    goal,
    current_value,
    target_value,
    progress_percentage,
    is_achieved,
    details,
  } = item;
  const targetDate = formatTargetDate(goal.target_date);

  // Build subtitle showing category and/or tracking period
  const subtitleParts: string[] = [];
  if (details.category_name) {
    subtitleParts.push(details.category_name);
  }
  if (goal.tracking_period) {
    subtitleParts.push(TRACKING_PERIOD_LABELS[goal.tracking_period]);
  }

  return (
    <div
      className={cn(
        "bg-white dark:bg-gray-900 rounded-lg border p-4",
        is_achieved
          ? "border-emerald-200 dark:border-emerald-800"
          : "border-gray-200 dark:border-gray-800"
      )}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className="font-medium text-gray-900 dark:text-gray-100">
              {goal.name}
            </h3>
            {is_achieved && (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-300">
                Achieved
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400">
              {GOAL_TYPE_LABELS[goal.goal_type]}
            </span>
            {subtitleParts.length > 0 && (
              <span className="text-xs text-gray-500 dark:text-gray-400">
                {subtitleParts.join(" / ")}
              </span>
            )}
            {targetDate && (
              <span className="text-xs text-gray-500 dark:text-gray-400">
                Due: {targetDate}
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-1">
          <button
            onClick={onEdit}
            className="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
            title="Edit goal"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
              />
            </svg>
          </button>
          <button
            onClick={onDelete}
            className="p-1.5 text-gray-400 hover:text-red-600 dark:hover:text-red-400"
            title="Delete goal"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
              />
            </svg>
          </button>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="mb-2">
        <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
          <div
            className={cn(
              "h-full rounded-full transition-all duration-500",
              is_achieved
                ? "bg-emerald-500"
                : progress_percentage >= 75
                  ? "bg-blue-500"
                  : progress_percentage >= 50
                    ? "bg-yellow-500"
                    : "bg-orange-500"
            )}
            style={{ width: `${Math.min(progress_percentage, 100)}%` }}
          />
        </div>
      </div>

      {/* Progress Values */}
      <div className="flex justify-between items-center text-sm">
        <span className="text-gray-600 dark:text-gray-400">
          {formatGoalValue(goal.goal_type, current_value)}
        </span>
        <span className="font-medium text-gray-900 dark:text-gray-100">
          {progress_percentage.toFixed(1).replace(".", ",")} %
        </span>
        <span className="text-gray-600 dark:text-gray-400">
          {formatGoalValue(goal.goal_type, target_value)}
        </span>
      </div>

      {/* Details */}
      {goal.goal_type === "net_worth_target" && details.latest_month && (
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
          Based on {details.latest_month} snapshot
        </p>
      )}
      {goal.goal_type === "category_target" && details.latest_month && (
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
          Based on {details.latest_month} snapshot
        </p>
      )}
      {(goal.goal_type === "category_monthly" ||
        goal.goal_type === "category_rate") &&
        details.months_tracked !== undefined && (
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
            {details.months_tracked > 0
              ? `Based on ${details.months_tracked} month${details.months_tracked > 1 ? "s" : ""} of data`
              : "No history data yet"}
            {goal.goal_type === "category_rate" &&
              details.net_income !== undefined && (
                <span>
                  {" "}
                  | Net income: {formatCurrency(details.net_income)}
                </span>
              )}
          </p>
        )}
    </div>
  );
}
