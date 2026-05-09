"use client";

import { useState, useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import * as Dialog from "@radix-ui/react-dialog";
import { BudgetSnapshot } from "@/types";
import { deleteBudgetSnapshot, updateBudgetSnapshot } from "@/lib/api";
import { formatCurrencyRounded, cn } from "@/lib/utils";
import { useToast } from "@/components/ui/Toast";
import { BudgetChart } from "./BudgetChart";

interface BudgetHistoryProps {
  snapshots: BudgetSnapshot[];
}

function formatSnapshotDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString("fi-FI", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function formatChange(value: number): string {
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${formatCurrencyRounded(value)}`;
}

function changeColor(value: number): string {
  if (value > 0) return "text-emerald-600 dark:text-emerald-400";
  if (value < 0) return "text-red-600 dark:text-red-400";
  return "text-gray-500 dark:text-gray-400";
}

function SnapshotRow({
  snapshot,
  isExpanded,
  onToggle,
  onEdit,
  onDelete,
}: {
  snapshot: BudgetSnapshot;
  isExpanded: boolean;
  onToggle: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const accounts = snapshot.entries.filter((e) => !e.is_credit);
  const creditCards = snapshot.entries.filter((e) => e.is_credit);

  return (
    <div>
      <div
        className="px-4 py-3 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors cursor-pointer"
        onClick={onToggle}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-4">
            <svg
              className={cn(
                "w-4 h-4 text-gray-400 transition-transform flex-shrink-0",
                isExpanded && "rotate-90"
              )}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
            <div className="text-sm font-medium text-gray-900 dark:text-gray-100 min-w-[100px]">
              {formatSnapshotDate(snapshot.date)}
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-lg font-semibold tabular-nums text-gray-900 dark:text-gray-100">
                {formatCurrencyRounded(snapshot.current_balance)}
              </span>
              {snapshot.change_from_previous !== 0 && (
                <span className={cn("text-sm tabular-nums", changeColor(snapshot.change_from_previous))}>
                  ({formatChange(snapshot.change_from_previous)})
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={onEdit}
            className="p-1.5 text-gray-500 hover:text-blue-600 dark:text-gray-400 dark:hover:text-blue-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
            title="Edit"
          >
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
              <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
              <path d="m15 5 4 4" />
            </svg>
          </button>
          <button
            onClick={onDelete}
            className="p-1.5 text-gray-500 hover:text-red-600 dark:text-gray-400 dark:hover:text-red-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
            title="Delete"
          >
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
              <path d="M3 6h18" />
              <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
              <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
            </svg>
          </button>
        </div>
      </div>
      {isExpanded && (
        <div className="px-4 pb-4 pt-1 bg-gray-50 dark:bg-gray-800/30">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-3">
            {accounts.length > 0 && (
              <div className="min-w-0">
                <div className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">
                  Accounts
                </div>
                <div className="space-y-0.5">
                  {accounts.map((entry) => (
                    <div key={entry.id} className="flex justify-between gap-2 text-sm">
                      <span className="text-gray-600 dark:text-gray-400 truncate min-w-0">
                        {entry.account_name}
                      </span>
                      <span
                        className={cn(
                          "tabular-nums whitespace-nowrap flex-shrink-0",
                          entry.balance >= 0
                            ? "text-emerald-600 dark:text-emerald-400"
                            : "text-red-600 dark:text-red-400"
                        )}
                      >
                        {formatCurrencyRounded(entry.balance)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {creditCards.length > 0 && (
              <div className="min-w-0">
                <div className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-1">
                  Credit Cards
                </div>
                <div className="space-y-0.5">
                  {creditCards.map((entry) => (
                    <div key={entry.id} className="flex justify-between gap-2 text-sm">
                      <span className="text-gray-600 dark:text-gray-400 truncate min-w-0">
                        {entry.account_name}
                      </span>
                      <span
                        className={cn(
                          "tabular-nums whitespace-nowrap flex-shrink-0",
                          entry.balance >= 0
                            ? "text-emerald-600 dark:text-emerald-400"
                            : "text-red-600 dark:text-red-400"
                        )}
                      >
                        {formatCurrencyRounded(entry.balance)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export function BudgetHistory({ snapshots }: BudgetHistoryProps) {
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
  const [olderOpen, setOlderOpen] = useState(false);
  const [editingSnapshot, setEditingSnapshot] = useState<BudgetSnapshot | null>(null);
  const [editEntries, setEditEntries] = useState<Record<number, string>>({});
  const [editNotes, setEditNotes] = useState("");
  const [deletingSnapshot, setDeletingSnapshot] = useState<BudgetSnapshot | null>(null);
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const toggleExpanded = (id: number) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const { currentPeriod, older } = useMemo(() => {
    if (snapshots.length === 0) {
      return { currentPeriod: [], older: [] };
    }

    // The most recent snapshot's pay_period_start defines the current period
    const currentPeriodStart = snapshots[0].pay_period_start;

    const current: BudgetSnapshot[] = [];
    const old: BudgetSnapshot[] = [];

    for (const s of snapshots) {
      if (s.pay_period_start === currentPeriodStart) {
        current.push(s);
      } else {
        old.push(s);
      }
    }
    return { currentPeriod: current, older: old };
  }, [snapshots]);

  const openEditDialog = (snapshot: BudgetSnapshot) => {
    setEditingSnapshot(snapshot);
    const balances: Record<number, string> = {};
    for (const entry of snapshot.entries) {
      balances[entry.id] = String(entry.balance);
    }
    setEditEntries(balances);
    setEditNotes(snapshot.notes ?? "");
  };

  const editMutation = useMutation({
    mutationFn: () => {
      if (!editingSnapshot) return Promise.reject();
      return updateBudgetSnapshot(editingSnapshot.id, {
        entries: editingSnapshot.entries.map((entry) => ({
          account_name: entry.account_name,
          balance: parseFloat(editEntries[entry.id] ?? String(entry.balance)),
          is_credit: entry.is_credit,
          account_id: entry.account_id,
        })),
        notes: editNotes || null,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["budget-snapshots"] });
      toast({ title: "Snapshot updated", type: "success" });
      setEditingSnapshot(null);
    },
    onError: () => {
      toast({ title: "Failed to update snapshot", type: "error" });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteBudgetSnapshot,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["budget-snapshots"] });
      toast({ title: "Snapshot deleted", type: "success" });
      setDeletingSnapshot(null);
    },
    onError: () => {
      toast({ title: "Failed to delete snapshot", type: "error" });
    },
  });

  if (snapshots.length === 0) {
    return null;
  }

  return (
    <div className="space-y-4">
      <BudgetChart snapshots={snapshots} />

      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between">
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Monthly budget change
          </h3>
          {expandedIds.size > 0 && (
            <button
              onClick={() => setExpandedIds(new Set())}
              className="text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
            >
              Collapse all
            </button>
          )}
        </div>

        {/* Current pay period */}
        {currentPeriod.length > 0 && (
          <div className="divide-y divide-gray-200 dark:divide-gray-800">
            {currentPeriod.map((snapshot) => (
              <SnapshotRow
                key={snapshot.id}
                snapshot={snapshot}
                isExpanded={expandedIds.has(snapshot.id)}
                onToggle={() => toggleExpanded(snapshot.id)}
                onEdit={() => openEditDialog(snapshot)}
                onDelete={() => setDeletingSnapshot(snapshot)}
              />
            ))}
          </div>
        )}

        {currentPeriod.length === 0 && (
          <div className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
            No snapshots in current pay period
          </div>
        )}

        {/* Older snapshots */}
        {older.length > 0 && (
          <>
            <div
              className="px-4 py-2.5 border-t border-gray-200 dark:border-gray-800 flex items-center gap-2 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
              onClick={() => setOlderOpen(!olderOpen)}
            >
              <svg
                className={cn(
                  "w-3.5 h-3.5 text-gray-400 transition-transform",
                  olderOpen && "rotate-90"
                )}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
                Older ({older.length})
              </span>
            </div>
            {olderOpen && (
              <div className="divide-y divide-gray-200 dark:divide-gray-800">
                {older.map((snapshot) => (
                  <SnapshotRow
                    key={snapshot.id}
                    snapshot={snapshot}
                    isExpanded={expandedIds.has(snapshot.id)}
                    onToggle={() => toggleExpanded(snapshot.id)}
                    onEdit={() => openEditDialog(snapshot)}
                    onDelete={() => setDeletingSnapshot(snapshot)}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </div>

      {/* Edit Dialog */}
      <Dialog.Root
        open={!!editingSnapshot}
        onOpenChange={(open) => !open && setEditingSnapshot(null)}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50" />
          <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-md bg-white dark:bg-gray-900 rounded-lg shadow-xl p-6 max-h-[85vh] overflow-y-auto">
            <Dialog.Title className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              Edit Snapshot
            </Dialog.Title>
            <Dialog.Description className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              {editingSnapshot && formatSnapshotDate(editingSnapshot.date)}
            </Dialog.Description>

            {editingSnapshot && (
              <div className="mt-4 space-y-4">
                {editingSnapshot.entries.filter((e) => !e.is_credit).length > 0 && (
                  <div>
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Accounts</div>
                    <div className="space-y-2">
                      {editingSnapshot.entries.filter((e) => !e.is_credit).map((entry) => (
                        <div key={entry.id} className="flex items-center gap-3">
                          <label className="text-sm text-gray-600 dark:text-gray-400 w-28 truncate flex-shrink-0">
                            {entry.account_name}
                          </label>
                          <input
                            type="number"
                            step="0.01"
                            value={editEntries[entry.id] ?? ""}
                            onChange={(e) => setEditEntries((prev) => ({ ...prev, [entry.id]: e.target.value }))}
                            className="flex-1 px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 tabular-nums"
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {editingSnapshot.entries.filter((e) => e.is_credit).length > 0 && (
                  <div>
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Credit Cards</div>
                    <div className="space-y-2">
                      {editingSnapshot.entries.filter((e) => e.is_credit).map((entry) => (
                        <div key={entry.id} className="flex items-center gap-3">
                          <label className="text-sm text-gray-600 dark:text-gray-400 w-28 truncate flex-shrink-0">
                            {entry.account_name}
                          </label>
                          <input
                            type="number"
                            step="0.01"
                            value={editEntries[entry.id] ?? ""}
                            onChange={(e) => setEditEntries((prev) => ({ ...prev, [entry.id]: e.target.value }))}
                            className="flex-1 px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 tabular-nums"
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div>
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Notes</label>
                  <input
                    type="text"
                    maxLength={500}
                    value={editNotes}
                    onChange={(e) => setEditNotes(e.target.value)}
                    placeholder="Optional notes"
                    className="mt-1 w-full px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                  />
                </div>

                <div className="flex justify-end gap-3 pt-2">
                  <Dialog.Close asChild>
                    <button className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200">
                      Cancel
                    </button>
                  </Dialog.Close>
                  <button
                    onClick={() => editMutation.mutate()}
                    disabled={editMutation.isPending}
                    className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
                  >
                    {editMutation.isPending ? "Saving..." : "Save"}
                  </button>
                </div>
              </div>
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      {/* Delete Confirmation Dialog */}
      <Dialog.Root
        open={!!deletingSnapshot}
        onOpenChange={(open) => !open && setDeletingSnapshot(null)}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50" />
          <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-sm bg-white dark:bg-gray-900 rounded-lg shadow-xl p-6">
            <Dialog.Title className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              Delete Budget Snapshot
            </Dialog.Title>
            <Dialog.Description className="mt-2 text-sm text-gray-600 dark:text-gray-400">
              Are you sure you want to delete the snapshot from{" "}
              {deletingSnapshot && (
                <span className="font-medium">
                  {formatSnapshotDate(deletingSnapshot.date)}
                </span>
              )}
              ? This action cannot be undone.
            </Dialog.Description>
            <div className="flex justify-end gap-3 mt-6">
              <Dialog.Close asChild>
                <button className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200">
                  Cancel
                </button>
              </Dialog.Close>
              <button
                onClick={() => deletingSnapshot && deleteMutation.mutate(deletingSnapshot.id)}
                disabled={deleteMutation.isPending}
                className="px-4 py-2 text-sm bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50"
              >
                {deleteMutation.isPending ? "Deleting..." : "Delete"}
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
