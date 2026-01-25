"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { BudgetSettings, SettingsFormData } from "@/types";
import { updateSettings } from "@/lib/api";
import { formatPercentage } from "@/lib/utils";
import { EditDialog } from "./EditDialog";
import { useToast } from "@/components/ui/Toast";

interface SettingsCardProps {
  settings: BudgetSettings;
}

const settingsFields = [
  {
    name: "tax_percentage",
    label: "Tax Rate (%)",
    type: "number" as const,
    required: true,
    min: 0,
    step: 0.1,
  },
];

export function SettingsCard({ settings }: SettingsCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const updateMutation = useMutation({
    mutationFn: updateSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["budget"] });
      toast({ title: "Settings updated", type: "success" });
    },
    onError: () => {
      toast({ title: "Failed to update settings", type: "error" });
    },
  });

  const handleSave = (values: Record<string, string | number | boolean>) => {
    const data: SettingsFormData = {
      tax_percentage: values.tax_percentage as number,
    };
    updateMutation.mutate(data);
  };

  return (
    <>
      <div
        onClick={() => setIsEditing(true)}
        className="inline-flex items-center gap-2 px-3 py-1.5 bg-gray-200 dark:bg-gray-800 rounded-full cursor-pointer hover:bg-gray-300 dark:hover:bg-gray-700 transition-colors border border-gray-300 dark:border-gray-700"
      >
        <span className="text-sm text-gray-600 dark:text-gray-400">
          Tax Rate:
        </span>
        <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
          {formatPercentage(settings.tax_percentage)}
        </span>
      </div>

      <EditDialog
        open={isEditing}
        onOpenChange={setIsEditing}
        title="Edit Tax Rate"
        fields={settingsFields}
        initialValues={{
          tax_percentage: settings.tax_percentage,
        }}
        onSave={handleSave}
      />
    </>
  );
}
