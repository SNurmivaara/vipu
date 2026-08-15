import { useQueryClient } from "@tanstack/react-query";
import { FORECASTING_PROJECTION_KEY } from "./useForecastingProjection";

/**
 * Everything that is recomputed from budget items, and therefore everything a
 * change to one has to refetch: the totals themselves, the roadmap that walks
 * the same periods, and the FIRE projection that runs on the surplus.
 *
 * Kept in one place because the failure is silent. Invalidating only ["budget"]
 * leaves the roadmap showing figures from before the edit, and it looks right
 * until you reload the page.
 */
const BUDGET_DERIVED_KEYS = [
  ["budget"],
  ["roadmap"],
  FORECASTING_PROJECTION_KEY,
];

export function useInvalidateBudget(): () => void {
  const queryClient = useQueryClient();

  return () => {
    for (const queryKey of BUDGET_DERIVED_KEYS) {
      queryClient.invalidateQueries({ queryKey });
    }
  };
}
