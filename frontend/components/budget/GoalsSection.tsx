"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { GoalProgress, GoalFormData } from "@/types";
import { createGoal, updateGoal, deleteGoal } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { CollapsibleSection } from "./CollapsibleSection";
import { GoalFormDialog } from "./GoalFormDialog";
import { useToast } from "@/components/ui/Toast";

// Net worth milestones tracked against snapshots. Savings/debt goals live on
// the Budget page's Financial Roadmap instead.

interface GoalsSectionProps {
  goals: GoalProgress[];
  collapsible?: boolean;
  defaultOpen?: boolean;
}

function getProgressColor(percentage: number, isAchieved: boolean): string {
  if (isAchieved) return "bg-green-500";
  if (percentage >= 75) return "bg-blue-500";
  if (percentage >= 50) return "bg-yellow-500";
  return "bg-orange-500";
}

// Build the explanatory pace text shown on hover over the on-track/behind badge.
function buildStatusHint(gp: GoalProgress): string | null {
  if (!gp.status_reason) return null;

  let hint = gp.status_reason;
  if (gp.recent_monthly != null && gp.required_monthly != null) {
    hint += ` — saving ${formatCurrency(gp.recent_monthly)}/mo vs ${formatCurrency(
      gp.required_monthly
    )}/mo needed`;
  }
  if (gp.projected_value != null && gp.months_remaining != null) {
    hint += `. At this pace you'll have ~${formatCurrency(
      gp.projected_value
    )} by the deadline`;
  }
  return hint;
}

export function GoalsSection({
  goals,
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
              {/* Monthly amount still needed to hit the target on time */}
              {!gp.is_achieved &&
                gp.required_monthly != null &&
                gp.required_monthly > 0 && (
                  <span className="text-sm text-gray-400 dark:text-gray-500">
                    {formatCurrency(gp.required_monthly)}/mo needed
                  </span>
                )}
              {gp.is_achieved && (
                <span className="text-sm px-2 py-0.5 rounded-full bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300">
                  Achieved
                </span>
              )}
            </div>
            {gp.status &&
              (() => {
                const hint = buildStatusHint(gp);
                const badge = (
                  <span
                    className={`text-sm px-2 py-0.5 rounded-full ${
                      gp.status === "on_track"
                        ? "bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300"
                        : "bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-300"
                    } ${hint ? "cursor-help" : ""}`}
                  >
                    {gp.status === "on_track" ? "On track" : "Behind"}
                  </span>
                );
                if (!hint) return badge;
                return (
                  <span className="relative group/status">
                    {badge}
                    <span
                      role="tooltip"
                      className="pointer-events-none invisible opacity-0 group-hover/status:visible group-hover/status:opacity-100 transition-opacity absolute right-0 top-full mt-1 z-10 w-64 rounded-md bg-gray-900 dark:bg-gray-700 px-3 py-2 text-xs font-normal text-gray-100 shadow-lg"
                    >
                      {hint}
                    </span>
                  </span>
                );
              })()}
          </div>

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
              {formatCurrency(gp.current_value)} /{" "}
              {formatCurrency(gp.target_value)}
            </span>
            <span>{gp.progress_percentage.toFixed(1)}%</span>
          </div>

          {/* Setup guidance when there's no on-track/behind badge to hover */}
          {!gp.status && gp.status_reason && (
            <div className="text-sm mt-1 text-gray-500 dark:text-gray-400">
              {gp.status_reason}
            </div>
          )}
        </div>
      ))}
      {goals.length === 0 && (
        <div className="px-4 py-6 text-center text-gray-500 dark:text-gray-400">
          No net worth goals yet. Create one to track your progress!
        </div>
      )}
    </div>
  );

  const dialog = (
    <GoalFormDialog
      open={editGoal !== null || isNew}
      onOpenChange={(open) => !open && closeDialog()}
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
          title="Net Worth Goals"
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
          Net Worth Goals
        </h2>
        <button
          onClick={openNew}
          className="text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 px-3 py-2 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        >
          + Add
        </button>
      </div>
      {content}
      {dialog}
    </section>
  );
}
