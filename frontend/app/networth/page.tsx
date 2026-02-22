"use client";

import { useState, useRef } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNetWorthSnapshots, useNetWorthCategories } from "@/hooks/useNetWorth";
import { useTheme } from "@/hooks/useTheme";
import {
  SummaryCards,
  NetWorthChart,
  AllocationChart,
  SnapshotForm,
  SnapshotList,
  CategoryManager,
} from "@/components/networth";
import { GoalsSection } from "@/components/budget";
import { Menu, MenuItem, MenuSeparator } from "@/components/ui/Menu";
import { useToast } from "@/components/ui/Toast";
import {
  seedCategories,
  seedNetWorth,
  resetNetWorth,
  exportBudget,
  importBudget,
  fetchGoalsProgress,
  ExportData,
} from "@/lib/api";

export default function NetWorthPage() {
  const { data: snapshots, isLoading: snapshotsLoading, error: snapshotsError } = useNetWorthSnapshots();
  const { data: categories, isLoading: categoriesLoading, error: categoriesError } = useNetWorthCategories();
  const { data: goalsProgress = [] } = useQuery({
    queryKey: ["goals-progress"],
    queryFn: fetchGoalsProgress,
  });
  const { resolvedTheme, setTheme } = useTheme();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const [formOpen, setFormOpen] = useState(false);
  const [categoryManagerOpen, setCategoryManagerOpen] = useState(false);
  const [confirmResetOpen, setConfirmResetOpen] = useState(false);
  const [confirmImportOpen, setConfirmImportOpen] = useState(false);
  const [pendingImportData, setPendingImportData] = useState<ExportData | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const toggleTheme = () => {
    setTheme(resolvedTheme === "dark" ? "light" : "dark");
  };

  const seedCategoriesMutation = useMutation({
    mutationFn: seedCategories,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["networth-groups"] });
      queryClient.invalidateQueries({ queryKey: ["networth-categories"] });
      toast({ title: "Categories created", type: "success" });
    },
    onError: () => {
      toast({ title: "Failed to create categories", type: "error" });
    },
  });

  const seedDataMutation = useMutation({
    mutationFn: seedNetWorth,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["networth-groups"] });
      queryClient.invalidateQueries({ queryKey: ["networth-snapshots"] });
      queryClient.invalidateQueries({ queryKey: ["networth-categories"] });
      toast({ title: "Example data loaded", type: "success" });
    },
    onError: () => {
      toast({ title: "Failed to load example data", type: "error" });
    },
  });

  const resetMutation = useMutation({
    mutationFn: resetNetWorth,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["networth-groups"] });
      queryClient.invalidateQueries({ queryKey: ["networth-snapshots"] });
      queryClient.invalidateQueries({ queryKey: ["networth-categories"] });
      toast({ title: "Net worth data reset", type: "success" });
      setConfirmResetOpen(false);
    },
    onError: () => {
      toast({ title: "Failed to reset data", type: "error" });
    },
  });

  const importMutation = useMutation({
    mutationFn: importBudget,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["budget"] });
      queryClient.invalidateQueries({ queryKey: ["networth-groups"] });
      queryClient.invalidateQueries({ queryKey: ["networth-categories"] });
      queryClient.invalidateQueries({ queryKey: ["networth-snapshots"] });
      queryClient.invalidateQueries({ queryKey: ["goals"] });
      queryClient.invalidateQueries({ queryKey: ["goals-progress"] });
      toast({ title: "Data imported successfully", type: "success" });
      setConfirmImportOpen(false);
      setPendingImportData(null);
    },
    onError: () => {
      toast({ title: "Failed to import data", type: "error" });
    },
  });

  const handleExport = async () => {
    try {
      const exportData = await exportBudget();
      const blob = new Blob([JSON.stringify(exportData, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `vipu-export-${new Date().toISOString().split("T")[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast({ title: "Data exported successfully", type: "success" });
    } catch {
      toast({ title: "Failed to export data", type: "error" });
    }
  };

  const handleImportClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      const text = await file.text();
      const importData = JSON.parse(text) as ExportData;

      if (importData.version !== 1 && importData.version !== 2) {
        toast({ title: "Unsupported file version", type: "error" });
        return;
      }

      setPendingImportData(importData);
      setConfirmImportOpen(true);
    } catch {
      toast({ title: "Invalid file format", type: "error" });
    }

    e.target.value = "";
  };

  const isLoading = snapshotsLoading || categoriesLoading;
  const hasError = snapshotsError || categoriesError;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="text-gray-500 dark:text-gray-400">Loading...</div>
      </div>
    );
  }

  if (hasError) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] gap-4">
        <div className="text-red-500">Failed to load net worth data</div>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Make sure the backend is running and accessible at /api
        </p>
      </div>
    );
  }

  const snapshotList = snapshots ?? [];
  const categoryList = categories ?? [];
  const hasCategories = categoryList.length > 0;
  const hasSnapshots = snapshotList.length > 0;
  const latestSnapshot = snapshotList[0] ?? null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
          Wealth
        </h2>
        <div className="flex items-center gap-3">
          {hasCategories && (
            <button
              onClick={() => setFormOpen(true)}
              className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
            >
              Record balances
            </button>
          )}
          <Menu
            trigger={
              <button className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="text-gray-600 dark:text-gray-400"
                >
                  <circle cx="12" cy="12" r="1" />
                  <circle cx="12" cy="5" r="1" />
                  <circle cx="12" cy="19" r="1" />
                </svg>
              </button>
            }
          >
            <MenuItem onClick={toggleTheme}>
              {resolvedTheme === "dark" ? "Light mode" : "Dark mode"}
            </MenuItem>
            <MenuSeparator />
            <MenuItem onClick={() => setCategoryManagerOpen(true)}>
              Manage categories
            </MenuItem>
            <MenuSeparator />
            <MenuItem onClick={handleExport}>Export data</MenuItem>
            <MenuItem onClick={handleImportClick}>Import data</MenuItem>
            <MenuSeparator />
            {!hasCategories && (
              <MenuItem onClick={() => seedCategoriesMutation.mutate()}>
                Create default categories
              </MenuItem>
            )}
            <MenuItem onClick={() => seedDataMutation.mutate()}>
              Load example data
            </MenuItem>
            <MenuSeparator />
            <MenuItem destructive onClick={() => setConfirmResetOpen(true)}>
              Reset net worth data
            </MenuItem>
          </Menu>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            onChange={handleFileSelect}
            className="hidden"
          />
        </div>
      </div>

      {/* Empty State: No Categories */}
      {!hasCategories && (
        <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
          <p className="text-blue-800 dark:text-blue-200 text-sm">
            No categories set up yet. Create your own categories or use the defaults to get started.
          </p>
          <div className="flex gap-4 mt-2">
            <button
              onClick={() => setCategoryManagerOpen(true)}
              className="text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 underline"
            >
              Manage categories
            </button>
            <button
              onClick={() => seedCategoriesMutation.mutate()}
              disabled={seedCategoriesMutation.isPending}
              className="text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 underline disabled:opacity-50"
            >
              {seedCategoriesMutation.isPending ? "Creating..." : "Create default categories"}
            </button>
          </div>
        </div>
      )}

      {/* Empty State: No Snapshots */}
      {hasCategories && !hasSnapshots && (
        <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
          <p className="text-blue-800 dark:text-blue-200 text-sm">
            No snapshots yet. Create your first snapshot to start tracking your net worth over time.
          </p>
          <div className="flex gap-4 mt-2">
            <button
              onClick={() => setFormOpen(true)}
              className="text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 underline"
            >
              Create first snapshot
            </button>
            <button
              onClick={() => seedDataMutation.mutate()}
              disabled={seedDataMutation.isPending}
              className="text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 underline disabled:opacity-50"
            >
              {seedDataMutation.isPending ? "Loading..." : "Load example data"}
            </button>
          </div>
        </div>
      )}

      {/* Summary Cards */}
      <SummaryCards snapshots={snapshotList} />

      {/* Charts Row */}
      {hasSnapshots && (
        <div className="grid gap-4 md:grid-cols-2">
          <NetWorthChart snapshots={snapshotList} />
          <AllocationChart snapshot={latestSnapshot} />
        </div>
      )}

      {/* Financial Goals */}
      <GoalsSection
        goals={goalsProgress}
        categories={categoryList}
      />

      {/* Snapshot List */}
      {hasCategories && (
        <SnapshotList snapshots={snapshotList} categories={categoryList} />
      )}

      {/* Snapshot Form */}
      <SnapshotForm
        open={formOpen}
        onOpenChange={setFormOpen}
        categories={categoryList}
      />

      {/* Category Manager */}
      <CategoryManager
        open={categoryManagerOpen}
        onOpenChange={setCategoryManagerOpen}
        categories={categoryList}
      />

      {/* Reset Confirmation Dialog */}
      <Dialog.Root open={confirmResetOpen} onOpenChange={setConfirmResetOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50" />
          <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-sm bg-white dark:bg-gray-900 rounded-lg shadow-xl p-6">
            <Dialog.Title className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              Reset Net Worth Data
            </Dialog.Title>
            <Dialog.Description className="mt-2 text-sm text-gray-600 dark:text-gray-400">
              This will delete all snapshots and categories. This action cannot be undone.
            </Dialog.Description>
            <div className="flex justify-end gap-3 mt-6">
              <Dialog.Close asChild>
                <button className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200">
                  Cancel
                </button>
              </Dialog.Close>
              <button
                onClick={() => resetMutation.mutate()}
                disabled={resetMutation.isPending}
                className="px-4 py-2 text-sm bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50"
              >
                {resetMutation.isPending ? "Resetting..." : "Reset"}
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      {/* Import Confirmation Dialog */}
      <Dialog.Root open={confirmImportOpen} onOpenChange={setConfirmImportOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50" />
          <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-sm bg-white dark:bg-gray-900 rounded-lg shadow-xl p-6">
            <Dialog.Title className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              Import Data
            </Dialog.Title>
            <Dialog.Description className="mt-2 text-sm text-gray-600 dark:text-gray-400">
              This will replace all existing data with the imported data. This
              action cannot be undone.
            </Dialog.Description>
            {pendingImportData && (
              <div className="mt-4 p-3 bg-gray-100 dark:bg-gray-800 rounded-md text-sm text-gray-700 dark:text-gray-300 space-y-1">
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                  Version {pendingImportData.version}
                  {pendingImportData.version === 2 && " (includes net worth)"}
                </p>
                <p>
                  <strong>Accounts:</strong> {pendingImportData.accounts.length}
                </p>
                <p>
                  <strong>Income items:</strong> {pendingImportData.income.length}
                </p>
                <p>
                  <strong>Expenses:</strong> {pendingImportData.expenses.length}
                </p>
                {pendingImportData.version === 2 && (
                  <>
                    <p>
                      <strong>Net worth snapshots:</strong>{" "}
                      {pendingImportData.networth_snapshots?.length ?? 0}
                    </p>
                    <p>
                      <strong>Goals:</strong> {pendingImportData.goals?.length ?? 0}
                    </p>
                  </>
                )}
              </div>
            )}
            <div className="flex justify-end gap-3 mt-6">
              <Dialog.Close asChild>
                <button
                  onClick={() => setPendingImportData(null)}
                  className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
                >
                  Cancel
                </button>
              </Dialog.Close>
              <button
                onClick={() =>
                  pendingImportData && importMutation.mutate(pendingImportData)
                }
                disabled={importMutation.isPending}
                className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
              >
                {importMutation.isPending ? "Importing..." : "Import"}
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
