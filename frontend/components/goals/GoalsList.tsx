"use client";

import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
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

function getGoalTypeLabel(goalType: GoalType, isLiability: boolean): string {
  if (goalType === "category_target" && isLiability) {
    return "Debt Payoff";
  }
  return GOAL_TYPE_LABELS[goalType];
}

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

function formatMonthsRemaining(months: number | null): string | null {
  if (months === null) return null;
  if (months === 0) return "Now";
  if (months === 1) return "1 month";
  if (months < 12) return `${months} months`;
  const years = Math.floor(months / 12);
  const remainingMonths = months % 12;
  if (remainingMonths === 0) {
    return years === 1 ? "1 year" : `${years} years`;
  }
  return years === 1
    ? `1 year ${remainingMonths}mo`
    : `${years}y ${remainingMonths}mo`;
}

export function GoalsList({ goals }: GoalsListProps) {
  const [editingGoal, setEditingGoal] = useState<GoalProgress | null>(null);
  const [deletingGoal, setDeletingGoal] = useState<{
    id: number;
    name: string;
  } | null>(null);
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const deleteMutation = useMutation({
    mutationFn: deleteGoal,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["goals"] });
      queryClient.invalidateQueries({ queryKey: ["goals-progress"] });
      toast({ title: "Goal deleted", type: "success" });
      setDeletingGoal(null);
    },
    onError: () => {
      toast({ title: "Failed to delete goal", type: "error" });
    },
  });

  const handleDeleteConfirm = () => {
    if (deletingGoal) {
      deleteMutation.mutate(deletingGoal.id);
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
            onDelete={() =>
              setDeletingGoal({ id: item.goal.id, name: item.goal.name })
            }
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

      {/* Delete Confirmation Dialog */}
      <Dialog.Root
        open={!!deletingGoal}
        onOpenChange={(open) => !open && setDeletingGoal(null)}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50" />
          <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-sm bg-white dark:bg-gray-900 rounded-lg shadow-xl p-6">
            <Dialog.Title className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              Delete Goal
            </Dialog.Title>
            <Dialog.Description className="mt-2 text-sm text-gray-600 dark:text-gray-400">
              Are you sure you want to delete &quot;{deletingGoal?.name}&quot;?
              This action cannot be undone.
            </Dialog.Description>
            <div className="flex justify-end gap-3 mt-6">
              <Dialog.Close asChild>
                <button
                  type="button"
                  className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
                >
                  Cancel
                </button>
              </Dialog.Close>
              <button
                type="button"
                onClick={handleDeleteConfirm}
                disabled={deleteMutation.isPending}
                className="px-4 py-2 text-sm bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50"
              >
                {deleteMutation.isPending ? "Deleting..." : "Delete"}
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
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
    forecast,
  } = item;
  const targetDate = formatTargetDate(goal.target_date);
  const hasTargetDate = goal.target_date !== null;
  const isLiability = details.is_liability ?? false;

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
            <span className={cn(
              "text-xs px-2 py-0.5 rounded-full",
              isLiability
                ? "bg-red-100 dark:bg-red-900/50 text-red-600 dark:text-red-400"
                : "bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400"
            )}>
              {getGoalTypeLabel(goal.goal_type, isLiability)}
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
        {isLiability && details.starting_value !== undefined && details.starting_value !== null ? (
          <>
            <span className="text-gray-600 dark:text-gray-400">
              <span className="text-xs text-gray-400 dark:text-gray-500">Remaining: </span>
              {formatGoalValue(goal.goal_type, current_value)}
            </span>
            <span className="font-medium text-gray-900 dark:text-gray-100">
              {progress_percentage.toFixed(1).replace(".", ",")} %
            </span>
            <span className="text-gray-600 dark:text-gray-400">
              <span className="text-xs text-gray-400 dark:text-gray-500">Target: </span>
              {formatGoalValue(goal.goal_type, target_value)}
            </span>
          </>
        ) : (
          <>
            <span className="text-gray-600 dark:text-gray-400">
              {formatGoalValue(goal.goal_type, current_value)}
            </span>
            <span className="font-medium text-gray-900 dark:text-gray-100">
              {progress_percentage.toFixed(1).replace(".", ",")} %
            </span>
            <span className="text-gray-600 dark:text-gray-400">
              {formatGoalValue(goal.goal_type, target_value)}
            </span>
          </>
        )}
      </div>
      {/* Starting value info for debt payoff goals */}
      {isLiability && details.starting_value !== undefined && details.starting_value !== null && (
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          Started at {formatCurrency(details.starting_value)} • Paid off {formatCurrency(details.starting_value - current_value)}
        </p>
      )}

      {/* Forecast info for target-based goals */}
      {forecast && !is_achieved && (
        <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-800">
          <div className="flex items-center gap-2 flex-wrap text-xs">
            {/* On-track indicator */}
            {hasTargetDate && (
              <span
                className={cn(
                  "inline-flex items-center gap-1 px-2 py-0.5 rounded-full font-medium",
                  forecast.on_track
                    ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300"
                    : "bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300"
                )}
              >
                {forecast.on_track ? (
                  <>
                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                    On track
                  </>
                ) : (
                  <>
                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                    </svg>
                    Behind
                  </>
                )}
              </span>
            )}

            {/* Projected completion */}
            {forecast.months_until_target !== null && (
              <span className="text-gray-500 dark:text-gray-400">
                ETA: {formatMonthsRemaining(forecast.months_until_target)}
              </span>
            )}
            {forecast.months_until_target === null && forecast.current_monthly_change <= 0 && (
              <span className="text-gray-500 dark:text-gray-400">
                Not on track to reach goal
              </span>
            )}
          </div>

          {/* Required vs current rate */}
          {hasTargetDate && !forecast.on_track && forecast.required_monthly_change > 0 && (
            <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">
              <span>
                Need {formatCurrency(forecast.required_monthly_change)}/mo
                {forecast.current_monthly_change > 0 && (
                  <span> (current: {formatCurrency(forecast.current_monthly_change)}/mo)</span>
                )}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Details */}
      {goal.goal_type === "net_worth_target" && details.latest_month && !forecast && (
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
          Based on {details.latest_month} snapshot
        </p>
      )}
      {goal.goal_type === "category_target" && details.latest_month && !forecast && (
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
