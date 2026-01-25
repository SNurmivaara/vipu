import { useQuery } from "@tanstack/react-query";
import { fetchBudget } from "@/lib/api";
import { BudgetData } from "@/types";

export function useBudget() {
  return useQuery<BudgetData>({
    queryKey: ["budget"],
    queryFn: fetchBudget,
  });
}
