import { useQuery } from "@tanstack/react-query";
import { fetchGoals, fetchGoalsProgress, fetchRoadmap } from "@/lib/api";
import { Goal, GoalProgress, RoadmapData } from "@/types";

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

export function useRoadmap() {
  return useQuery<RoadmapData>({
    queryKey: ["roadmap"],
    queryFn: fetchRoadmap,
  });
}
