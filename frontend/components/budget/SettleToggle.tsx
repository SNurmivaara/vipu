"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { setExpenseOccurrence, setIncomeOccurrence } from "@/lib/api";
import { OccurrenceState } from "@/types";
import { cn } from "@/lib/utils";
import { useToast } from "@/components/ui/Toast";

/**
 * The occurrence a row can tick off, if it has one. Rows without a correctable
 * occurrence (further-out ones, archived items) get no tick box.
 */
export function settleableOccurrence(
  item: OccurrenceState
): { occurrenceDate: string; settled: boolean } | null {
  if (!item.can_settle || !item.next_occurrence_date) {
    return null;
  }
  return {
    occurrenceDate: item.next_occurrence_date,
    settled: item.is_settled,
  };
}

interface SettleToggleProps {
  kind: "expense" | "income";
  itemId: number;
  /** The occurrence this tick box applies to */
  occurrenceDate: string;
  /** Whether that occurrence's money has already moved */
  settled: boolean;
  /** Item name, for the accessible label */
  name: string;
}

/**
 * Ticks a single occurrence off as already paid/received, or back on as still
 * outstanding. Only that one occurrence moves: the item keeps its schedule, so
 * every later occurrence — and everything projected from them — is unaffected.
 *
 * The two directions it covers are a payment made ahead of its due day, and one
 * whose due day has passed without the money actually moving (a debit that
 * waits for the next banking day).
 */
export function SettleToggle({
  kind,
  itemId,
  occurrenceDate,
  settled,
  name,
}: SettleToggleProps) {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const verb = kind === "expense" ? "paid" : "received";

  const mutation = useMutation({
    mutationFn: async (next: boolean) => {
      const input = { id: itemId, occurrenceDate, settled: next };
      return kind === "expense"
        ? setExpenseOccurrence(input)
        : setIncomeOccurrence(input);
    },
    onSuccess: (_data, next) => {
      queryClient.invalidateQueries({ queryKey: ["budget"] });
      // A one-time item ticked off changes what the roadmap starts from
      queryClient.invalidateQueries({ queryKey: ["roadmap"] });
      toast({
        title: next ? `Marked ${verb}` : `Marked not ${verb} yet`,
        type: "success",
      });
    },
    onError: (error) => {
      const message = axios.isAxiosError(error)
        ? error.response?.data?.error
        : undefined;
      toast({ title: message ?? "Failed to update payment", type: "error" });
    },
  });

  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={settled}
      aria-label={`${name} ${occurrenceDate}: mark ${verb}`}
      title={
        settled
          ? `Already ${verb} — click if it hasn't gone through yet`
          : `Not ${verb} yet — click once it has`
      }
      disabled={mutation.isPending}
      onClick={(event) => {
        // The row itself opens the edit dialog
        event.stopPropagation();
        mutation.mutate(!settled);
      }}
      className={cn(
        "shrink-0 w-4 h-4 rounded border flex items-center justify-center transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500",
        "disabled:opacity-50",
        settled
          ? "bg-emerald-600 border-emerald-600 text-white hover:bg-emerald-700"
          : "border-gray-300 dark:border-gray-600 hover:border-emerald-500 dark:hover:border-emerald-500"
      )}
    >
      {settled && (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="10"
          height="10"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="4"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <polyline points="20 6 9 17 4 12" />
        </svg>
      )}
    </button>
  );
}
