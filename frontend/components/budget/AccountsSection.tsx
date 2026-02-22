"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Account, AccountFormData } from "@/types";
import { createAccount, updateAccount, deleteAccount } from "@/lib/api";
import { formatCurrency, getBalanceColor, cn } from "@/lib/utils";
import { EditDialog } from "./EditDialog";
import { CollapsibleSection } from "./CollapsibleSection";
import { useToast } from "@/components/ui/Toast";

interface AccountsSectionProps {
  accounts: Account[];
  collapsible?: boolean;
  defaultOpen?: boolean;
}

const accountFields = [
  { name: "name", label: "Name", type: "text" as const, required: true },
  {
    name: "balance",
    label: "Balance (€)",
    type: "signed_number" as const,
    required: true,
    step: 0.01,
    defaultSign: "positive" as const,
  },
];

export function AccountsSection({
  accounts,
  collapsible = false,
  defaultOpen = false,
}: AccountsSectionProps) {
  const [editItem, setEditItem] = useState<Account | null>(null);
  const [isNew, setIsNew] = useState(false);
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const createMutation = useMutation({
    mutationFn: createAccount,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["budget"] });
      toast({ title: "Account created", type: "success" });
    },
    onError: () => {
      toast({ title: "Failed to create account", type: "error" });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: AccountFormData }) =>
      updateAccount(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["budget"] });
      toast({ title: "Account updated", type: "success" });
    },
    onError: () => {
      toast({ title: "Failed to update account", type: "error" });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteAccount,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["budget"] });
      toast({ title: "Account deleted", type: "success" });
    },
    onError: () => {
      toast({ title: "Failed to delete account", type: "error" });
    },
  });

  const handleSave = (values: Record<string, string | number | boolean>) => {
    const data: AccountFormData = {
      name: values.name as string,
      balance: values.balance as number,
      is_credit: false,
    };

    if (isNew) {
      createMutation.mutate(data);
    } else if (editItem) {
      updateMutation.mutate({ id: editItem.id, data });
    }
  };

  const handleDelete = () => {
    if (editItem) {
      deleteMutation.mutate(editItem.id);
    }
  };

  const openNew = () => {
    setEditItem(null);
    setIsNew(true);
  };

  const openEdit = (item: Account) => {
    setEditItem(item);
    setIsNew(false);
  };

  const closeDialog = () => {
    setEditItem(null);
    setIsNew(false);
  };

  const totalBalance = accounts.reduce((sum, a) => sum + a.balance, 0);

  const content = (
    <div className="divide-y divide-gray-100 dark:divide-gray-800">
      <div className="grid grid-cols-2 px-4 py-2 text-sm text-gray-500 dark:text-gray-400 uppercase tracking-wider">
        <span>Account</span>
        <span className="text-right">Balance</span>
      </div>
      {accounts.map((account) => (
        <div
          key={account.id}
          onClick={() => openEdit(account)}
          className="grid grid-cols-2 px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer"
        >
          <span className="text-gray-900 dark:text-gray-100">
            {account.name}
          </span>
          <span
            className={cn(
              "text-right font-medium",
              getBalanceColor(account.balance)
            )}
          >
            {formatCurrency(account.balance)}
          </span>
        </div>
      ))}
      {accounts.length === 0 && (
        <div className="px-4 py-6 text-center text-gray-500 dark:text-gray-400">
          No accounts yet
        </div>
      )}
      {accounts.length > 0 && (
        <div className="grid grid-cols-2 px-4 py-3 bg-gray-50 dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700">
          <span className="font-semibold text-gray-900 dark:text-gray-100">
            Total
          </span>
          <span
            className={cn(
              "text-right font-semibold",
              getBalanceColor(totalBalance)
            )}
          >
            {formatCurrency(totalBalance)}
          </span>
        </div>
      )}
    </div>
  );

  const dialog = (
    <EditDialog
      open={editItem !== null || isNew}
      onOpenChange={(open) => !open && closeDialog()}
      title={isNew ? "Add Account" : "Edit Account"}
      fields={accountFields}
      initialValues={
        editItem
          ? {
              name: editItem.name,
              balance: editItem.balance,
            }
          : {
              name: "",
              balance: 0,
            }
      }
      onSave={handleSave}
      onDelete={handleDelete}
      isNew={isNew}
    />
  );

  if (collapsible) {
    return (
      <>
        <CollapsibleSection
          title="Accounts"
          total={formatCurrency(totalBalance)}
          totalClassName={getBalanceColor(totalBalance)}
          defaultOpen={defaultOpen}
          onAdd={openNew}
        >
          {content}
        </CollapsibleSection>
        {dialog}
      </>
    );
  }

  return (
    <section className="bg-white dark:bg-gray-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800">
      <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-800 flex justify-between items-center">
        <h2 className="font-semibold text-gray-900 dark:text-gray-100">
          Accounts
        </h2>
        <button
          onClick={openNew}
          className="text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300"
        >
          + Add
        </button>
      </div>
      {content}
      {dialog}
    </section>
  );
}
