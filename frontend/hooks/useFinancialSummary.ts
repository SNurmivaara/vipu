import { useBudget } from "@/hooks/useBudget";
import { useGoalsProgress, useRoadmap } from "@/hooks/useGoals";
import { useNetWorthSnapshots } from "@/hooks/useNetWorth";
import { useForecastingProjection } from "@/hooks/useForecastingProjection";
import { buildFinancialSummary } from "@/lib/aiSummary";

/**
 * Gathers everything the combined "Copy for AI" export needs.
 *
 * The export spans budget and wealth, so both pages need the same five
 * sources. React Query dedupes and caches them, so pulling the other page's
 * data here costs nothing once it is warm.
 *
 * Returns null until the budget has loaded, since the export is built around
 * it; the wealth half degrades to "no snapshots yet" on its own.
 */
export function useFinancialSummary(): () => string | null {
  const { data: budget } = useBudget();
  const { data: roadmap } = useRoadmap();
  const { data: snapshots } = useNetWorthSnapshots();
  const { data: goalsProgress } = useGoalsProgress();
  // Falls back to an all-zero default rather than undefined, so gate on the
  // load state: a FIRE section full of zeros reads as a real projection.
  const { result: projection, isLoading: projectionLoading } =
    useForecastingProjection();

  return () => {
    if (!budget) return null;
    return buildFinancialSummary(
      budget,
      roadmap,
      snapshots ?? [],
      goalsProgress ?? [],
      projectionLoading ? null : projection
    );
  };
}
