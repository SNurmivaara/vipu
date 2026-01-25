"use client";

import { useState, useEffect, useMemo } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import * as Select from "@radix-ui/react-select";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { NetWorthCategory, NetWorthSnapshot, NetWorthGroup } from "@/types";
import { createSnapshot, updateSnapshot } from "@/lib/api";
import { formatCurrency, cn } from "@/lib/utils";
import { useToast } from "@/components/ui/Toast";
import { useNetWorthGroups } from "@/hooks/useNetWorth";

interface SnapshotFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  categories: NetWorthCategory[];
  existingSnapshot?: NetWorthSnapshot | null;
}

const MONTHS = [
  { value: 1, label: "January" },
  { value: 2, label: "February" },
  { value: 3, label: "March" },
  { value: 4, label: "April" },
  { value: 5, label: "May" },
  { value: 6, label: "June" },
  { value: 7, label: "July" },
  { value: 8, label: "August" },
  { value: 9, label: "September" },
  { value: 10, label: "October" },
  { value: 11, label: "November" },
  { value: 12, label: "December" },
];

export function SnapshotForm({
  open,
  onOpenChange,
  categories,
  existingSnapshot,
}: SnapshotFormProps) {
  const { data: groups = [] } = useNetWorthGroups();
  const now = useMemo(() => new Date(), []);
  const [month, setMonth] = useState(existingSnapshot?.month ?? now.getMonth() + 1);
  const [year, setYear] = useState(existingSnapshot?.year ?? now.getFullYear());
  const [amounts, setAmounts] = useState<Record<number, number>>({});

  const queryClient = useQueryClient();
  const { toast } = useToast();
  const isEditing = !!existingSnapshot;

  useEffect(() => {
    if (open) {
      if (existingSnapshot) {
        setMonth(existingSnapshot.month);
        setYear(existingSnapshot.year);
        const entryAmounts: Record<number, number> = {};
        existingSnapshot.entries.forEach((entry) => {
          entryAmounts[entry.category_id] = Math.abs(entry.amount);
        });
        setAmounts(entryAmounts);
      } else {
        setMonth(now.getMonth() + 1);
        setYear(now.getFullYear());
        setAmounts({});
      }
    }
  }, [open, existingSnapshot, now]);

  const createMutation = useMutation({
    mutationFn: createSnapshot,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["networth-snapshots"] });
      toast({ title: "Snapshot created", type: "success" });
      onOpenChange(false);
    },
    onError: () => {
      toast({ title: "Failed to create snapshot", type: "error" });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, entries }: { id: number; entries: { category_id: number; amount: number }[] }) =>
      updateSnapshot(id, { entries }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["networth-snapshots"] });
      toast({ title: "Snapshot updated", type: "success" });
      onOpenChange(false);
    },
    onError: () => {
      toast({ title: "Failed to update snapshot", type: "error" });
    },
  });

  // Group categories by their group
  const categoriesByGroup = useMemo(() => {
    const result: Record<number, NetWorthCategory[]> = {};
    for (const group of groups) {
      result[group.id] = categories
        .filter((c) => c.group_id === group.id)
        .sort((a, b) => a.display_order - b.display_order);
    }
    return result;
  }, [categories, groups]);

  // Sort groups by display_order
  const sortedGroups = useMemo(() => {
    return [...groups].sort((a, b) => a.display_order - b.display_order);
  }, [groups]);

  const totals = useMemo(() => {
    let assets = 0;
    let liabilities = 0;

    categories.forEach((cat) => {
      const amount = amounts[cat.id] || 0;
      const group = groups.find((g) => g.id === cat.group_id);
      if (group?.group_type === "asset") {
        assets += amount;
      } else {
        liabilities += amount;
      }
    });

    return {
      assets,
      liabilities,
      netWorth: assets - liabilities,
    };
  }, [amounts, categories, groups]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const entries = categories
      .filter((cat) => amounts[cat.id] && amounts[cat.id] > 0)
      .map((cat) => {
        const group = groups.find((g) => g.id === cat.group_id);
        const isLiability = group?.group_type === "liability";
        return {
          category_id: cat.id,
          amount: isLiability ? -amounts[cat.id] : amounts[cat.id],
        };
      });

    if (isEditing && existingSnapshot) {
      updateMutation.mutate({ id: existingSnapshot.id, entries });
    } else {
      createMutation.mutate({ month, year, entries });
    }
  };

  const years = useMemo(() => {
    const currentYear = now.getFullYear();
    return Array.from({ length: 5 }, (_, i) => currentYear - 2 + i);
  }, [now]);

  const isPending = createMutation.isPending || updateMutation.isPending;

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50" />
        <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-lg max-h-[85vh] overflow-y-auto bg-white dark:bg-gray-900 rounded-lg shadow-xl p-6">
          <Dialog.Title className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">
            {isEditing ? "Edit Snapshot" : "New Snapshot"}
          </Dialog.Title>

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Month/Year Selection */}
            {!isEditing && (
              <div className="flex gap-4">
                <div className="flex-1">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Month
                  </label>
                  <Select.Root
                    value={String(month)}
                    onValueChange={(val) => setMonth(Number(val))}
                  >
                    <Select.Trigger className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-left flex justify-between items-center">
                      <Select.Value />
                      <Select.Icon className="text-gray-500">
                        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                          <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                        </svg>
                      </Select.Icon>
                    </Select.Trigger>
                    <Select.Portal>
                      <Select.Content className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md shadow-lg z-[100] overflow-hidden">
                        <Select.Viewport className="p-1">
                          {MONTHS.map((m) => (
                            <Select.Item
                              key={m.value}
                              value={String(m.value)}
                              className="px-3 py-2 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 rounded text-gray-900 dark:text-gray-100 outline-none"
                            >
                              <Select.ItemText>{m.label}</Select.ItemText>
                            </Select.Item>
                          ))}
                        </Select.Viewport>
                      </Select.Content>
                    </Select.Portal>
                  </Select.Root>
                </div>
                <div className="flex-1">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Year
                  </label>
                  <Select.Root
                    value={String(year)}
                    onValueChange={(val) => setYear(Number(val))}
                  >
                    <Select.Trigger className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-left flex justify-between items-center">
                      <Select.Value />
                      <Select.Icon className="text-gray-500">
                        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                          <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                        </svg>
                      </Select.Icon>
                    </Select.Trigger>
                    <Select.Portal>
                      <Select.Content className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md shadow-lg z-[100] overflow-hidden">
                        <Select.Viewport className="p-1">
                          {years.map((y) => (
                            <Select.Item
                              key={y}
                              value={String(y)}
                              className="px-3 py-2 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 rounded text-gray-900 dark:text-gray-100 outline-none"
                            >
                              <Select.ItemText>{y}</Select.ItemText>
                            </Select.Item>
                          ))}
                        </Select.Viewport>
                      </Select.Content>
                    </Select.Portal>
                  </Select.Root>
                </div>
              </div>
            )}

            {isEditing && (
              <div className="text-sm text-gray-600 dark:text-gray-400">
                {MONTHS.find((m) => m.value === month)?.label} {year}
              </div>
            )}

            {/* Category Entries */}
            <div className="space-y-4">
              {sortedGroups.map((group) => {
                const cats = categoriesByGroup[group.id] || [];
                if (cats.length === 0) return null;

                const isLiability = group.group_type === "liability";

                return (
                  <GroupSection
                    key={group.id}
                    group={group}
                    categories={cats}
                    amounts={amounts}
                    setAmounts={setAmounts}
                    isLiability={isLiability}
                  />
                );
              })}
            </div>

            {/* Live Totals */}
            <div className="border-t border-gray-200 dark:border-gray-700 pt-4 space-y-1">
              <div className="flex justify-between text-sm">
                <span className="text-gray-600 dark:text-gray-400">Total Assets</span>
                <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                  {formatCurrency(totals.assets)}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600 dark:text-gray-400">Total Liabilities</span>
                <span className="text-red-600 dark:text-red-400 font-medium">
                  {formatCurrency(totals.liabilities)}
                </span>
              </div>
              <div className="flex justify-between text-base font-semibold pt-2 border-t border-gray-200 dark:border-gray-700">
                <span className="text-gray-900 dark:text-gray-100">Net Worth</span>
                <span
                  className={cn(
                    totals.netWorth >= 0
                      ? "text-emerald-600 dark:text-emerald-400"
                      : "text-red-600 dark:text-red-400"
                  )}
                >
                  {formatCurrency(totals.netWorth)}
                </span>
              </div>
            </div>

            {/* Actions */}
            <div className="flex justify-end gap-3 pt-2">
              <Dialog.Close asChild>
                <button
                  type="button"
                  className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
                >
                  Cancel
                </button>
              </Dialog.Close>
              <button
                type="submit"
                disabled={isPending}
                className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
              >
                {isPending ? "Saving..." : isEditing ? "Update" : "Create"}
              </button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function GroupSection({
  group,
  categories,
  amounts,
  setAmounts,
  isLiability,
}: {
  group: NetWorthGroup;
  categories: NetWorthCategory[];
  amounts: Record<number, number>;
  setAmounts: React.Dispatch<React.SetStateAction<Record<number, number>>>;
  isLiability: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border p-3",
        isLiability
          ? "border-red-200 dark:border-red-900/50 bg-red-50/50 dark:bg-red-900/10"
          : "border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-800/30"
      )}
    >
      <div className="flex items-center gap-2 mb-3">
        <span
          className="w-3 h-3 rounded-full"
          style={{ backgroundColor: group.color }}
        />
        <span
          className={cn(
            "text-xs font-semibold uppercase tracking-wide",
            isLiability
              ? "text-red-600 dark:text-red-400"
              : "text-gray-500 dark:text-gray-400"
          )}
        >
          {group.name}
          {isLiability && " (liability)"}
        </span>
      </div>
      <div className="space-y-2">
        {categories.map((cat) => (
          <div key={cat.id} className="flex items-center gap-3">
            <label
              htmlFor={`cat-${cat.id}`}
              className="flex-1 text-sm text-gray-700 dark:text-gray-300"
            >
              {cat.name}
              {!cat.is_personal && (
                <span className="ml-1 text-xs text-gray-400 dark:text-gray-500">
                  (company)
                </span>
              )}
            </label>
            <div className="w-32">
              <input
                type="number"
                id={`cat-${cat.id}`}
                value={amounts[cat.id] || ""}
                onChange={(e) =>
                  setAmounts((prev) => ({
                    ...prev,
                    [cat.id]: parseFloat(e.target.value) || 0,
                  }))
                }
                min={0}
                step={0.01}
                placeholder="0,00"
                className={cn(
                  "w-full px-3 py-1.5 text-right border rounded-md text-sm",
                  "bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100",
                  "border-gray-300 dark:border-gray-700",
                  "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                )}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
