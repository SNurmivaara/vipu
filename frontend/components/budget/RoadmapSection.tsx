"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { GoalFormData, RoadmapStep } from "@/types";
import { createGoal, updateGoal, deleteGoal, reorderGoals } from "@/lib/api";
import { useRoadmap } from "@/hooks/useGoals";
import { useNetWorthCategories } from "@/hooks/useNetWorth";
import { formatCurrency } from "@/lib/utils";
import { useToast } from "@/components/ui/Toast";
import { RoadmapFormDialog } from "./RoadmapFormDialog";

// The sequential financial plan: "pay off X" -> "save 6k" -> "do Y", funded
// by the monthly budget surplus. Each step shows how fast it completes at the
// current surplus; the whole surplus flows into the first unfinished step.

function formatMonthYear(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString("en-GB", {
    month: "short",
    year: "numeric",
  });
}

function formatMonths(months: number): string {
  if (months < 1) return "<1 mo";
  const rounded = Math.round(months * 10) / 10;
  return `${rounded % 1 === 0 ? rounded.toFixed(0) : rounded.toFixed(1)} mo`;
}

const STEP_TYPE_LABELS: Record<string, string> = {
  savings_goal: "Save up",
  debt_payoff: "Pay off",
};

export function RoadmapSection() {
  const { data, isLoading } = useRoadmap();
  const { data: categories } = useNetWorthCategories();
  const [editStep, setEditStep] = useState<RoadmapStep | null>(null);
  const [isNew, setIsNew] = useState(false);
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["roadmap"] });
    queryClient.invalidateQueries({ queryKey: ["goals"] });
    queryClient.invalidateQueries({ queryKey: ["goals-progress"] });
  };

  const createMutation = useMutation({
    mutationFn: createGoal,
    onSuccess: () => {
      invalidate();
      toast({ title: "Goal added to roadmap", type: "success" });
    },
    onError: () => {
      toast({ title: "Failed to add goal", type: "error" });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<GoalFormData> }) =>
      updateGoal(id, data),
    onSuccess: () => {
      invalidate();
      toast({ title: "Goal updated", type: "success" });
    },
    onError: () => {
      toast({ title: "Failed to update goal", type: "error" });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteGoal,
    onSuccess: () => {
      invalidate();
      toast({ title: "Goal deleted", type: "success" });
    },
    onError: () => {
      toast({ title: "Failed to delete goal", type: "error" });
    },
  });

  const reorderMutation = useMutation({
    mutationFn: reorderGoals,
    onSuccess: invalidate,
    onError: () => {
      toast({ title: "Failed to reorder goals", type: "error" });
    },
  });

  const steps = data?.goals ?? [];
  const surplus = data?.surplus_monthly ?? 0;
  const startingPosition = data?.starting_position ?? 0;
  const pendingOneTime = data?.pending_one_time_net ?? 0;
  const shortfallMonths = data?.shortfall_months ?? 0;

  const handleSave = (formData: GoalFormData) => {
    if (isNew) {
      createMutation.mutate(formData);
    } else if (editStep) {
      updateMutation.mutate({ id: editStep.goal.id, data: formData });
    }
  };

  const handleDelete = () => {
    if (editStep) {
      deleteMutation.mutate(editStep.goal.id);
    }
  };

  const moveStep = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= steps.length) return;
    const ids = steps.map((s) => s.goal.id);
    [ids[index], ids[target]] = [ids[target], ids[index]];
    reorderMutation.mutate(ids);
  };

  const openNew = () => {
    setEditStep(null);
    setIsNew(true);
  };

  const openEdit = (step: RoadmapStep) => {
    setEditStep(step);
    setIsNew(false);
  };

  const closeDialog = () => {
    setEditStep(null);
    setIsNew(false);
  };

  return (
    <section className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800">
      <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-800 flex justify-between items-center">
        <div className="flex items-baseline gap-3">
          <h2 className="font-semibold text-gray-900 dark:text-gray-100">
            Financial Roadmap
          </h2>
          {data && (
            <span
              className={`text-sm ${
                surplus > 0
                  ? "text-emerald-600 dark:text-emerald-400"
                  : "text-red-600 dark:text-red-400"
              }`}
            >
              {formatCurrency(surplus)}/mo surplus
            </span>
          )}
        </div>
        <button
          onClick={openNew}
          className="text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 px-3 py-2 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        >
          + Add
        </button>
      </div>

      {surplus <= 0 && steps.some((s) => s.status !== "completed") && (
        <div className="px-4 py-2 bg-amber-50 dark:bg-amber-900/20 border-b border-amber-200 dark:border-amber-800 text-sm text-amber-800 dark:text-amber-200">
          No monthly surplus — income doesn&apos;t cover expenses, so the
          roadmap won&apos;t progress.
        </div>
      )}

      {/* A shortfall is cleared before step 1 moves, so say why the dates slip
          rather than leaving the delay unexplained. */}
      {surplus > 0 && startingPosition < 0 && (
        <div className="px-4 py-2 bg-amber-50 dark:bg-amber-900/20 border-b border-amber-200 dark:border-amber-800 text-sm text-amber-800 dark:text-amber-200">
          Starting {formatCurrency(startingPosition)} behind
          {pendingOneTime < 0 &&
            ` (incl. ${formatCurrency(-pendingOneTime)} of one-off bills)`}
          . The first {formatMonths(shortfallMonths)} of surplus covers that
          before step 1 moves.
        </div>
      )}

      {isLoading ? (
        <div className="px-4 py-6 text-center text-gray-500 dark:text-gray-400">
          Loading...
        </div>
      ) : steps.length === 0 ? (
        <div className="px-4 py-6 text-center text-gray-500 dark:text-gray-400">
          No goals yet. Build your plan: pay off a debt, save an emergency
          fund, then whatever comes next.
        </div>
      ) : (
        <div className="p-4 overflow-x-auto">
          <div className="flex items-stretch gap-2 min-w-max">
            {steps.map((step, index) => (
              <StepCard
                key={step.goal.id}
                step={step}
                index={index}
                isLast={index === steps.length - 1}
                onClick={() => openEdit(step)}
                onMove={(direction) => moveStep(index, direction)}
              />
            ))}
          </div>
        </div>
      )}

      <RoadmapFormDialog
        open={editStep !== null || isNew}
        onOpenChange={(open) => !open && closeDialog()}
        categories={categories ?? []}
        step={editStep}
        onSave={handleSave}
        onDelete={handleDelete}
        isNew={isNew}
      />
    </section>
  );
}

interface StepCardProps {
  step: RoadmapStep;
  index: number;
  isLast: boolean;
  onClick: () => void;
  onMove: (direction: -1 | 1) => void;
}

const STATUS_STYLES: Record<RoadmapStep["status"], string> = {
  completed:
    "border-emerald-300 dark:border-emerald-800 bg-emerald-50/50 dark:bg-emerald-900/10",
  active: "border-blue-400 dark:border-blue-700 bg-blue-50/50 dark:bg-blue-900/10",
  upcoming: "border-gray-200 dark:border-gray-700",
};

function StepCard({ step, index, isLast, onClick, onMove }: StepCardProps) {
  const goal = step.goal;
  const isDebt = goal.goal_type === "debt_payoff";
  const completed = step.status === "completed";

  return (
    <>
      <div
        onClick={onClick}
        className={`group relative w-56 shrink-0 rounded-lg border p-3 cursor-pointer hover:shadow-sm transition-shadow ${STATUS_STYLES[step.status]}`}
      >
        <div className="flex items-center justify-between mb-1.5">
          <div className="flex items-center gap-2 min-w-0">
            <span
              className={`flex items-center justify-center w-5 h-5 rounded-full text-xs shrink-0 ${
                completed
                  ? "bg-emerald-500 text-white"
                  : step.status === "active"
                    ? "bg-blue-500 text-white"
                    : "bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300"
              }`}
            >
              {completed ? "✓" : index + 1}
            </span>
            <span className="font-medium text-sm text-gray-900 dark:text-gray-100 truncate">
              {goal.name}
            </span>
          </div>
          {/* Reorder controls, shown on hover */}
          <div className="hidden group-hover:flex items-center gap-0.5 shrink-0">
            <button
              onClick={(e) => {
                e.stopPropagation();
                onMove(-1);
              }}
              disabled={index === 0}
              aria-label="Move earlier"
              className="px-1 text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 disabled:opacity-30"
            >
              ←
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onMove(1);
              }}
              disabled={isLast}
              aria-label="Move later"
              className="px-1 text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 disabled:opacity-30"
            >
              →
            </button>
          </div>
        </div>

        <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">
          {STEP_TYPE_LABELS[goal.goal_type]}
          {goal.category && ` · ${goal.category.name}`}
        </div>

        <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 mb-2">
          <div
            className={`h-1.5 rounded-full ${
              completed ? "bg-emerald-500" : "bg-blue-500"
            }`}
            style={{ width: `${Math.min(step.progress_percentage, 100)}%` }}
          />
        </div>

        <div className="flex justify-between text-xs text-gray-600 dark:text-gray-400">
          <span>
            {isDebt
              ? `${formatCurrency(step.remaining)} left`
              : `${formatCurrency(step.current_value)} / ${formatCurrency(goal.target_value)}`}
          </span>
          <span>{step.progress_percentage.toFixed(0)}%</span>
        </div>

        <div className="mt-1.5 text-xs">
          {completed ? (
            <span className="text-emerald-600 dark:text-emerald-400">Done</span>
          ) : step.projected_completion_date ? (
            <span className="text-gray-500 dark:text-gray-400">
              ~{formatMonthYear(step.projected_completion_date)}
              {step.months_to_complete !== null &&
                ` · ${formatMonths(step.months_to_complete)}`}
            </span>
          ) : (
            <span className="text-gray-400 dark:text-gray-500">
              No projection without surplus
            </span>
          )}
        </div>
      </div>

      {!isLast && (
        <div className="flex items-center text-gray-300 dark:text-gray-600 shrink-0">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M5 12h14" />
            <path d="m12 5 7 7-7 7" />
          </svg>
        </div>
      )}
    </>
  );
}
