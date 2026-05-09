import { useQuery } from "@tanstack/react-query";
import { fetchBudgetSnapshots, BudgetSnapshotsResponse } from "@/lib/api";

export function useBudgetSnapshots() {
  return useQuery<BudgetSnapshotsResponse>({
    queryKey: ["budget-snapshots"],
    queryFn: () => fetchBudgetSnapshots(),
  });
}
