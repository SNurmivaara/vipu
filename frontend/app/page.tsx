"use client";

import { useState, useRef } from "react";
import { useBudget } from "@/hooks/useBudget";
import { useTheme } from "@/hooks/useTheme";
import { useNetWorthCategories } from "@/hooks/useNetWorth";
import {
  IncomeSection,
  DeductionsSection,
  AccountsSection,
  CreditCardsSection,
  ExpensesSection,
  SavingsGoalsSection,
  SettingsCard,
  BudgetSummary,
} from "@/components/budget";
import { SnapshotForm } from "@/components/networth";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  seedData,
  resetBudget,
  exportBudget,
  importBudget,
  ExportData,
} from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import { Menu, MenuItem, MenuSeparator } from "@/components/ui/Menu";
import * as Dialog from "@radix-ui/react-dialog";

export default function BudgetPage() {
  const { data, isLoading, error } = useBudget();
  const { data: categories = [] } = useNetWorthCategories();
  const { resolvedTheme, setTheme } = useTheme();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [confirmResetOpen, setConfirmResetOpen] = useState(false);
  const [confirmImportOpen, setConfirmImportOpen] = useState(false);
  const [pendingImportData, setPendingImportData] = useState<ExportData | null>(null);
  const [snapshotFormOpen, setSnapshotFormOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const toggleTheme = () => {
    setTheme(resolvedTheme === "dark" ? "light" : "dark");
  };

  const seedMutation = useMutation({
    mutationFn: seedData,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["budget"] });
      toast({ title: "Example data loaded", type: "success" });
    },
    onError: () => {
      toast({ title: "Failed to load example data", type: "error" });
    },
  });

  const resetMutation = useMutation({
    mutationFn: resetBudget,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["budget"] });
      toast({ title: "Budget reset successfully", type: "success" });
      setConfirmResetOpen(false);
    },
    onError: () => {
      toast({ title: "Failed to reset budget", type: "error" });
    },
  });

  const importMutation = useMutation({
    mutationFn: importBudget,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["budget"] });
      // Invalidate net worth queries for version 2 imports
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

    // Reset file input
    e.target.value = "";
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="text-gray-500 dark:text-gray-400">Loading...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] gap-4">
        <div className="text-red-500">Failed to load budget data</div>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Make sure the backend is running and accessible at /api
        </p>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  const isEmpty =
    data.income.length === 0 &&
    data.accounts.length === 0 &&
    data.expenses.length === 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
          Monthly Budget
        </h2>
        <div className="flex items-center gap-3">
          {categories.length > 0 && (
            <button
              onClick={() => setSnapshotFormOpen(true)}
              className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
            >
              Record balances
            </button>
          )}
          <SettingsCard settings={data.settings} />
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
            <MenuItem onClick={handleExport}>Export data</MenuItem>
            <MenuItem onClick={handleImportClick}>Import data</MenuItem>
            <MenuSeparator />
            <MenuItem onClick={() => seedMutation.mutate()}>
              Load example data
            </MenuItem>
            <MenuSeparator />
            <MenuItem destructive onClick={() => setConfirmResetOpen(true)}>
              Reset monthly budget
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

      {isEmpty && (
        <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
          <p className="text-blue-800 dark:text-blue-200 text-sm">
            No budget data yet. Add your income, accounts, and expenses to get
            started.
          </p>
          <button
            onClick={() => seedMutation.mutate()}
            disabled={seedMutation.isPending}
            className="mt-2 text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 underline disabled:opacity-50"
          >
            {seedMutation.isPending ? "Loading..." : "Load example data"}
          </button>
        </div>
      )}

      <BudgetSummary data={data} />

      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-4">
          <IncomeSection
            income={data.income.filter((i) => !i.is_deduction)}
            settings={data.settings}
            collapsible
          />
          <DeductionsSection
            deductions={data.income.filter((i) => i.is_deduction)}
            collapsible
          />
          <AccountsSection
            accounts={data.accounts.filter((a) => !a.is_credit)}
            collapsible
            defaultOpen
          />
          <CreditCardsSection
            creditCards={data.accounts.filter((a) => a.is_credit)}
            collapsible
          />
        </div>
        <div className="space-y-4">
          <ExpensesSection
            expenses={data.expenses.filter((e) => !e.is_savings_goal)}
            collapsible
          />
          <SavingsGoalsSection
            savingsGoals={data.expenses.filter((e) => e.is_savings_goal)}
            collapsible
          />
        </div>
      </div>

      {/* Reset Confirmation Dialog */}
      <Dialog.Root open={confirmResetOpen} onOpenChange={setConfirmResetOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50" />
          <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-sm bg-white dark:bg-gray-900 rounded-lg shadow-xl p-6">
            <Dialog.Title className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              Reset Monthly Budget
            </Dialog.Title>
            <Dialog.Description className="mt-2 text-sm text-gray-600 dark:text-gray-400">
              This will delete all income, accounts, and expenses. This action
              cannot be undone.
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

      {/* Snapshot Form */}
      <SnapshotForm
        open={snapshotFormOpen}
        onOpenChange={setSnapshotFormOpen}
        categories={categories}
      />
    </div>
  );
}
