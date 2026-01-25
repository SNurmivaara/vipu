"use client";

import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { NetWorthSnapshot, NetWorthCategory } from "@/types";
import { deleteSnapshot } from "@/lib/api";
import { formatCurrency, cn } from "@/lib/utils";
import { useToast } from "@/components/ui/Toast";
import { SnapshotForm } from "./SnapshotForm";

interface SnapshotListProps {
  snapshots: NetWorthSnapshot[];
  categories: NetWorthCategory[];
}

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"
];

export function SnapshotList({ snapshots, categories }: SnapshotListProps) {
  const [editingSnapshot, setEditingSnapshot] = useState<NetWorthSnapshot | null>(null);
  const [deletingSnapshot, setDeletingSnapshot] = useState<NetWorthSnapshot | null>(null);

  const queryClient = useQueryClient();
  const { toast } = useToast();

  const deleteMutation = useMutation({
    mutationFn: deleteSnapshot,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["networth-snapshots"] });
      toast({ title: "Snapshot deleted", type: "success" });
      setDeletingSnapshot(null);
    },
    onError: () => {
      toast({ title: "Failed to delete snapshot", type: "error" });
    },
  });

  if (snapshots.length === 0) {
    return (
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800 p-6">
        <div className="text-center text-gray-500 dark:text-gray-400">
          No snapshots yet. Create your first snapshot to start tracking your net worth.
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-800">
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            History
          </h3>
        </div>
        <div className="divide-y divide-gray-200 dark:divide-gray-800">
          {snapshots.map((snapshot) => {
            const changeColor =
              snapshot.change_from_previous > 0
                ? "text-emerald-600 dark:text-emerald-400"
                : snapshot.change_from_previous < 0
                  ? "text-red-600 dark:text-red-400"
                  : "text-gray-500 dark:text-gray-400";
            const changePrefix = snapshot.change_from_previous > 0 ? "+" : "";

            return (
              <div
                key={snapshot.id}
                className="px-4 py-3 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-4">
                    <div className="text-sm font-medium text-gray-900 dark:text-gray-100">
                      {MONTH_NAMES[snapshot.month - 1]} {snapshot.year}
                    </div>
                    <div
                      className={cn(
                        "text-lg font-semibold",
                        snapshot.net_worth >= 0
                          ? "text-emerald-700 dark:text-emerald-400"
                          : "text-red-600 dark:text-red-400"
                      )}
                    >
                      {formatCurrency(snapshot.net_worth)}
                    </div>
                  </div>
                  <div className="flex items-center gap-4 mt-1 text-xs text-gray-500 dark:text-gray-400">
                    <span>
                      Assets: {formatCurrency(snapshot.total_assets)}
                    </span>
                    <span>
                      Liabilities: {formatCurrency(Math.abs(snapshot.total_liabilities))}
                    </span>
                    <span className={changeColor}>
                      {changePrefix}{formatCurrency(snapshot.change_from_previous)}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-2 ml-4">
                  <button
                    onClick={() => setEditingSnapshot(snapshot)}
                    className="p-1.5 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded"
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
                    onClick={() => setDeletingSnapshot(snapshot)}
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
            );
          })}
        </div>
      </div>

      {/* Edit Dialog */}
      <SnapshotForm
        open={!!editingSnapshot}
        onOpenChange={(open) => !open && setEditingSnapshot(null)}
        categories={categories}
        existingSnapshot={editingSnapshot}
      />

      {/* Delete Confirmation Dialog */}
      <Dialog.Root
        open={!!deletingSnapshot}
        onOpenChange={(open) => !open && setDeletingSnapshot(null)}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50" />
          <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-sm bg-white dark:bg-gray-900 rounded-lg shadow-xl p-6">
            <Dialog.Title className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              Delete Snapshot
            </Dialog.Title>
            <Dialog.Description className="mt-2 text-sm text-gray-600 dark:text-gray-400">
              Are you sure you want to delete the snapshot for{" "}
              {deletingSnapshot && (
                <span className="font-medium">
                  {MONTH_NAMES[deletingSnapshot.month - 1]} {deletingSnapshot.year}
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
    </>
  );
}
