import { useQuery } from "@tanstack/react-query";
import { fetchGoals, fetchGoalsProgress } from "@/lib/api";
import { Goal, GoalProgress } from "@/types";

export function useGoals() {
  return useQuery<Goal[]>({
    queryKey: ["goals"],
    queryFn: fetchGoals,
  });
}

export function useGoalsProgress() {
  return useQuery<GoalProgress[]>({
    queryKey: ["goals-progress"],
    queryFn: fetchGoalsProgress,
  });
}
