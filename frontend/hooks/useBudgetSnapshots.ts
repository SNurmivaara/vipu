import { useQuery } from "@tanstack/react-query";
import { fetchBudgetSnapshots } from "@/lib/api";
import { BudgetSnapshot } from "@/types";

export function useBudgetSnapshots() {
  return useQuery<BudgetSnapshot[]>({
    queryKey: ["budget-snapshots"],
    queryFn: fetchBudgetSnapshots,
  });
}
