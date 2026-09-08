import { useCallback } from "react";
import { fetchSummary } from "@/lib/api";

/**
 * The combined "Copy for AI" export, fetched from GET /api/summary.
 *
 * The digest used to be assembled client-side from five queries by
 * lib/aiSummary.ts. It is built on the backend now, so the web UI, the MCP
 * server and anything else pasting it into a chat read one document rather
 * than three implementations of it.
 *
 * Fetched when the button is pressed rather than held in a query. Invalidation
 * is spread across a dozen call sites, so a cached digest would have needed a
 * key added to every one of them and would have gone quietly stale behind the
 * first one anybody forgot. Fetching on demand removes the failure instead of
 * guarding against it.
 *
 * Returns null when the request fails, which the callers already handle as
 * "nothing to copy".
 */
export function useFinancialSummary(): () => Promise<string | null> {
  return useCallback(async () => {
    try {
      return (await fetchSummary()).markdown;
    } catch {
      return null;
    }
  }, []);
}
