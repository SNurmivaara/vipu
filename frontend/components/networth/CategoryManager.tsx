"use client";

import { useState, useMemo } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import * as Select from "@radix-ui/react-select";
import * as Tabs from "@radix-ui/react-tabs";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { NetWorthCategory, NetWorthGroup, GroupType, CategoryFormData, GroupFormData } from "@/types";
import {
  createCategory,
  updateCategory,
  deleteCategory,
  createGroup,
  updateGroup,
  deleteGroup,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { useToast } from "@/components/ui/Toast";
import { useNetWorthGroups } from "@/hooks/useNetWorth";

interface CategoryManagerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  categories: NetWorthCategory[];
}

const GROUP_TYPES: { value: GroupType; label: string }[] = [
  { value: "asset", label: "Asset" },
  { value: "liability", label: "Liability" },
];

const DEFAULT_COLORS = [
  "#22c55e", // green
  "#3b82f6", // blue
  "#f59e0b", // amber
  "#8b5cf6", // purple
  "#ef4444", // red
  "#f97316", // orange
  "#06b6d4", // cyan
  "#ec4899", // pink
];

interface GroupFormState {
  name: string;
  group_type: GroupType;
  color: string;
  display_order: number;
}

interface CategoryFormState {
  name: string;
  group_id: number;
  is_personal: boolean;
  display_order: number;
}

const defaultGroupFormState: GroupFormState = {
  name: "",
  group_type: "asset",
  color: "#22c55e",
  display_order: 0,
};

const defaultCategoryFormState: CategoryFormState = {
  name: "",
  group_id: 0,
  is_personal: true,
  display_order: 0,
};

export function CategoryManager({ open, onOpenChange, categories }: CategoryManagerProps) {
  const { data: groups = [] } = useNetWorthGroups();
  const [activeTab, setActiveTab] = useState<"groups" | "categories">("groups");

  // Group state
  const [editingGroup, setEditingGroup] = useState<NetWorthGroup | null>(null);
  const [groupFormState, setGroupFormState] = useState<GroupFormState>(defaultGroupFormState);
  const [showGroupForm, setShowGroupForm] = useState(false);
  const [deletingGroup, setDeletingGroup] = useState<NetWorthGroup | null>(null);

  // Category state
  const [editingCategory, setEditingCategory] = useState<NetWorthCategory | null>(null);
  const [categoryFormState, setCategoryFormState] = useState<CategoryFormState>(defaultCategoryFormState);
  const [showCategoryForm, setShowCategoryForm] = useState(false);
  const [deletingCategory, setDeletingCategory] = useState<NetWorthCategory | null>(null);

  const queryClient = useQueryClient();
  const { toast } = useToast();

  // Group mutations
  const createGroupMutation = useMutation({
    mutationFn: createGroup,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["networth-groups"] });
      toast({ title: "Group created", type: "success" });
      resetGroupForm();
    },
    onError: () => {
      toast({ title: "Failed to create group", type: "error" });
    },
  });

  const updateGroupMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<GroupFormData> }) =>
      updateGroup(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["networth-groups"] });
      queryClient.invalidateQueries({ queryKey: ["networth-categories"] });
      toast({ title: "Group updated", type: "success" });
      resetGroupForm();
    },
    onError: () => {
      toast({ title: "Failed to update group", type: "error" });
    },
  });

  const deleteGroupMutation = useMutation({
    mutationFn: deleteGroup,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["networth-groups"] });
      toast({ title: "Group deleted", type: "success" });
      setDeletingGroup(null);
    },
    onError: () => {
      toast({ title: "Cannot delete: group has categories", type: "error" });
      setDeletingGroup(null);
    },
  });

  // Category mutations
  const createCategoryMutation = useMutation({
    mutationFn: createCategory,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["networth-categories"] });
      toast({ title: "Category created", type: "success" });
      resetCategoryForm();
    },
    onError: () => {
      toast({ title: "Failed to create category", type: "error" });
    },
  });

  const updateCategoryMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<CategoryFormData> }) =>
      updateCategory(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["networth-categories"] });
      toast({ title: "Category updated", type: "success" });
      resetCategoryForm();
    },
    onError: () => {
      toast({ title: "Failed to update category", type: "error" });
    },
  });

  const deleteCategoryMutation = useMutation({
    mutationFn: deleteCategory,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["networth-categories"] });
      toast({ title: "Category deleted", type: "success" });
      setDeletingCategory(null);
    },
    onError: () => {
      toast({ title: "Cannot delete: category is in use", type: "error" });
      setDeletingCategory(null);
    },
  });

  const resetGroupForm = () => {
    setGroupFormState(defaultGroupFormState);
    setEditingGroup(null);
    setShowGroupForm(false);
  };

  const resetCategoryForm = () => {
    setCategoryFormState(defaultCategoryFormState);
    setEditingCategory(null);
    setShowCategoryForm(false);
  };

  const handleEditGroup = (group: NetWorthGroup) => {
    setEditingGroup(group);
    setGroupFormState({
      name: group.name,
      group_type: group.group_type,
      color: group.color,
      display_order: group.display_order,
    });
    setShowGroupForm(true);
  };

  const handleEditCategory = (category: NetWorthCategory) => {
    setEditingCategory(category);
    setCategoryFormState({
      name: category.name,
      group_id: category.group_id,
      is_personal: category.is_personal,
      display_order: category.display_order,
    });
    setShowCategoryForm(true);
  };

  const handleGroupSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (editingGroup) {
      updateGroupMutation.mutate({ id: editingGroup.id, data: groupFormState });
    } else {
      createGroupMutation.mutate(groupFormState);
    }
  };

  const handleCategorySubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (editingCategory) {
      updateCategoryMutation.mutate({ id: editingCategory.id, data: categoryFormState });
    } else {
      createCategoryMutation.mutate(categoryFormState);
    }
  };

  const isGroupPending = createGroupMutation.isPending || updateGroupMutation.isPending;
  const isCategoryPending = createCategoryMutation.isPending || updateCategoryMutation.isPending;

  // Group categories by group for display
  const categoriesByGroup = useMemo(() => {
    const result: Record<number, NetWorthCategory[]> = {};
    for (const group of groups) {
      result[group.id] = categories.filter((c) => c.group_id === group.id);
    }
    return result;
  }, [categories, groups]);

  const assetGroups = groups.filter((g) => g.group_type === "asset");
  const liabilityGroups = groups.filter((g) => g.group_type === "liability");

  return (
    <>
      <Dialog.Root open={open} onOpenChange={onOpenChange}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50" />
          <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-lg max-h-[85vh] overflow-y-auto bg-white dark:bg-gray-900 rounded-lg shadow-xl p-6">
            <Dialog.Title className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">
              Manage Groups & Categories
            </Dialog.Title>

            <Tabs.Root value={activeTab} onValueChange={(v) => setActiveTab(v as "groups" | "categories")}>
              <Tabs.List className="flex gap-1 mb-4 border-b border-gray-200 dark:border-gray-700">
                <Tabs.Trigger
                  value="groups"
                  className={cn(
                    "px-4 py-2 text-sm font-medium -mb-px border-b-2 transition-colors",
                    activeTab === "groups"
                      ? "border-blue-500 text-blue-600 dark:text-blue-400"
                      : "border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300"
                  )}
                >
                  Groups
                </Tabs.Trigger>
                <Tabs.Trigger
                  value="categories"
                  className={cn(
                    "px-4 py-2 text-sm font-medium -mb-px border-b-2 transition-colors",
                    activeTab === "categories"
                      ? "border-blue-500 text-blue-600 dark:text-blue-400"
                      : "border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300"
                  )}
                >
                  Categories
                </Tabs.Trigger>
              </Tabs.List>

              {/* Groups Tab */}
              <Tabs.Content value="groups">
                {showGroupForm ? (
                  <form onSubmit={handleGroupSubmit} className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Name
                      </label>
                      <input
                        type="text"
                        value={groupFormState.name}
                        onChange={(e) => setGroupFormState((s) => ({ ...s, name: e.target.value }))}
                        required
                        maxLength={100}
                        className={cn(
                          "w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md",
                          "bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100",
                          "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        )}
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                          Type
                        </label>
                        <Select.Root
                          value={groupFormState.group_type}
                          onValueChange={(val) =>
                            setGroupFormState((s) => ({ ...s, group_type: val as GroupType }))
                          }
                        >
                          <Select.Trigger className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-left flex justify-between items-center">
                            <Select.Value />
                            <Select.Icon className="text-gray-500">
                              <ChevronDownIcon />
                            </Select.Icon>
                          </Select.Trigger>
                          <Select.Portal>
                            <Select.Content className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md shadow-lg z-[100] overflow-hidden">
                              <Select.Viewport className="p-1">
                                {GROUP_TYPES.map((t) => (
                                  <Select.Item
                                    key={t.value}
                                    value={t.value}
                                    className="px-3 py-2 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 rounded text-gray-900 dark:text-gray-100 outline-none"
                                  >
                                    <Select.ItemText>{t.label}</Select.ItemText>
                                  </Select.Item>
                                ))}
                              </Select.Viewport>
                            </Select.Content>
                          </Select.Portal>
                        </Select.Root>
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                          Color
                        </label>
                        <div className="flex items-center gap-2">
                          <input
                            type="color"
                            value={groupFormState.color}
                            onChange={(e) =>
                              setGroupFormState((s) => ({ ...s, color: e.target.value }))
                            }
                            className="w-10 h-10 rounded border border-gray-300 dark:border-gray-700 cursor-pointer"
                          />
                          <div className="flex gap-1 flex-wrap">
                            {DEFAULT_COLORS.map((color) => (
                              <button
                                key={color}
                                type="button"
                                onClick={() => setGroupFormState((s) => ({ ...s, color }))}
                                className={cn(
                                  "w-6 h-6 rounded border-2 transition-all",
                                  groupFormState.color === color
                                    ? "border-gray-800 dark:border-white scale-110"
                                    : "border-transparent"
                                )}
                                style={{ backgroundColor: color }}
                              />
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <label className="text-sm text-gray-700 dark:text-gray-300">Display Order:</label>
                      <input
                        type="number"
                        value={groupFormState.display_order}
                        onChange={(e) =>
                          setGroupFormState((s) => ({ ...s, display_order: parseInt(e.target.value) || 0 }))
                        }
                        className={cn(
                          "w-20 px-2 py-1 border border-gray-300 dark:border-gray-700 rounded-md",
                          "bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-sm",
                          "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        )}
                      />
                    </div>

                    <div className="flex justify-end gap-3 pt-2">
                      <button
                        type="button"
                        onClick={resetGroupForm}
                        className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={isGroupPending}
                        className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
                      >
                        {isGroupPending ? "Saving..." : editingGroup ? "Update" : "Create"}
                      </button>
                    </div>
                  </form>
                ) : (
                  <div className="space-y-4">
                    <button
                      onClick={() => setShowGroupForm(true)}
                      className="w-full px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700"
                    >
                      + Add Group
                    </button>

                    {groups.length === 0 ? (
                      <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                        No groups yet
                      </div>
                    ) : (
                      <div className="space-y-4">
                        {assetGroups.length > 0 && (
                          <div>
                            <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                              Asset Groups
                            </h4>
                            <div className="space-y-1">
                              {assetGroups.map((group) => (
                                <GroupRow
                                  key={group.id}
                                  group={group}
                                  categoryCount={categoriesByGroup[group.id]?.length || 0}
                                  onEdit={handleEditGroup}
                                  onDelete={setDeletingGroup}
                                />
                              ))}
                            </div>
                          </div>
                        )}

                        {liabilityGroups.length > 0 && (
                          <div>
                            <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                              Liability Groups
                            </h4>
                            <div className="space-y-1">
                              {liabilityGroups.map((group) => (
                                <GroupRow
                                  key={group.id}
                                  group={group}
                                  categoryCount={categoriesByGroup[group.id]?.length || 0}
                                  onEdit={handleEditGroup}
                                  onDelete={setDeletingGroup}
                                />
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    <div className="flex justify-end pt-4">
                      <Dialog.Close asChild>
                        <button className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200">
                          Close
                        </button>
                      </Dialog.Close>
                    </div>
                  </div>
                )}
              </Tabs.Content>

              {/* Categories Tab */}
              <Tabs.Content value="categories">
                {showCategoryForm ? (
                  <form onSubmit={handleCategorySubmit} className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Name
                      </label>
                      <input
                        type="text"
                        value={categoryFormState.name}
                        onChange={(e) => setCategoryFormState((s) => ({ ...s, name: e.target.value }))}
                        required
                        maxLength={100}
                        className={cn(
                          "w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md",
                          "bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100",
                          "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        )}
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        Group
                      </label>
                      <Select.Root
                        value={categoryFormState.group_id ? String(categoryFormState.group_id) : ""}
                        onValueChange={(val) =>
                          setCategoryFormState((s) => ({ ...s, group_id: Number(val) }))
                        }
                      >
                        <Select.Trigger className="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-left flex justify-between items-center">
                          <Select.Value placeholder="Select a group" />
                          <Select.Icon className="text-gray-500">
                            <ChevronDownIcon />
                          </Select.Icon>
                        </Select.Trigger>
                        <Select.Portal>
                          <Select.Content className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md shadow-lg z-[100] overflow-hidden">
                            <Select.Viewport className="p-1">
                              {groups.map((g) => (
                                <Select.Item
                                  key={g.id}
                                  value={String(g.id)}
                                  className="px-3 py-2 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 rounded text-gray-900 dark:text-gray-100 outline-none flex items-center gap-2"
                                >
                                  <span
                                    className="w-3 h-3 rounded-full"
                                    style={{ backgroundColor: g.color }}
                                  />
                                  <Select.ItemText>{g.name}</Select.ItemText>
                                  <span className="text-sm text-gray-500 ml-1">
                                    ({g.group_type})
                                  </span>
                                </Select.Item>
                              ))}
                            </Select.Viewport>
                          </Select.Content>
                        </Select.Portal>
                      </Select.Root>
                    </div>

                    <div className="flex items-center gap-4">
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={categoryFormState.is_personal}
                          onChange={(e) =>
                            setCategoryFormState((s) => ({ ...s, is_personal: e.target.checked }))
                          }
                          className="h-4 w-4 rounded border-gray-300"
                        />
                        <span className="text-sm text-gray-700 dark:text-gray-300">Personal</span>
                      </label>
                      <div className="flex items-center gap-2">
                        <label className="text-sm text-gray-700 dark:text-gray-300">Order:</label>
                        <input
                          type="number"
                          value={categoryFormState.display_order}
                          onChange={(e) =>
                            setCategoryFormState((s) => ({ ...s, display_order: parseInt(e.target.value) || 0 }))
                          }
                          className={cn(
                            "w-20 px-2 py-1 border border-gray-300 dark:border-gray-700 rounded-md",
                            "bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-sm",
                            "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                          )}
                        />
                      </div>
                    </div>

                    <div className="flex justify-end gap-3 pt-2">
                      <button
                        type="button"
                        onClick={resetCategoryForm}
                        className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={isCategoryPending || !categoryFormState.group_id}
                        className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
                      >
                        {isCategoryPending ? "Saving..." : editingCategory ? "Update" : "Create"}
                      </button>
                    </div>
                  </form>
                ) : (
                  <div className="space-y-4">
                    <button
                      onClick={() => setShowCategoryForm(true)}
                      disabled={groups.length === 0}
                      className="w-full px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
                    >
                      + Add Category
                    </button>

                    {groups.length === 0 ? (
                      <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                        Create groups first before adding categories
                      </div>
                    ) : categories.length === 0 ? (
                      <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                        No categories yet
                      </div>
                    ) : (
                      <div className="space-y-4">
                        {groups.map((group) => {
                          const groupCategories = categoriesByGroup[group.id] || [];
                          if (groupCategories.length === 0) return null;
                          return (
                            <div key={group.id}>
                              <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 flex items-center gap-2">
                                <span
                                  className="w-3 h-3 rounded-full"
                                  style={{ backgroundColor: group.color }}
                                />
                                {group.name}
                              </h4>
                              <div className="space-y-1">
                                {groupCategories.map((cat) => (
                                  <CategoryRow
                                    key={cat.id}
                                    category={cat}
                                    onEdit={handleEditCategory}
                                    onDelete={setDeletingCategory}
                                  />
                                ))}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}

                    <div className="flex justify-end pt-4">
                      <Dialog.Close asChild>
                        <button className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200">
                          Close
                        </button>
                      </Dialog.Close>
                    </div>
                  </div>
                )}
              </Tabs.Content>
            </Tabs.Root>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      {/* Delete Group Confirmation Dialog */}
      <Dialog.Root
        open={!!deletingGroup}
        onOpenChange={(open) => !open && setDeletingGroup(null)}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/50 z-[60]" />
          <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-[60] w-full max-w-sm bg-white dark:bg-gray-900 rounded-lg shadow-xl p-6">
            <Dialog.Title className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              Delete Group
            </Dialog.Title>
            <Dialog.Description className="mt-2 text-sm text-gray-600 dark:text-gray-400">
              Are you sure you want to delete &quot;{deletingGroup?.name}&quot;? This action cannot
              be undone. Groups with categories cannot be deleted.
            </Dialog.Description>
            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setDeletingGroup(null)}
                className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
              >
                Cancel
              </button>
              <button
                onClick={() => deletingGroup && deleteGroupMutation.mutate(deletingGroup.id)}
                disabled={deleteGroupMutation.isPending}
                className="px-4 py-2 text-sm bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50"
              >
                {deleteGroupMutation.isPending ? "Deleting..." : "Delete"}
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      {/* Delete Category Confirmation Dialog */}
      <Dialog.Root
        open={!!deletingCategory}
        onOpenChange={(open) => !open && setDeletingCategory(null)}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/50 z-[60]" />
          <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-[60] w-full max-w-sm bg-white dark:bg-gray-900 rounded-lg shadow-xl p-6">
            <Dialog.Title className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              Delete Category
            </Dialog.Title>
            <Dialog.Description className="mt-2 text-sm text-gray-600 dark:text-gray-400">
              Are you sure you want to delete &quot;{deletingCategory?.name}&quot;? This action cannot
              be undone. Categories that are in use cannot be deleted.
            </Dialog.Description>
            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setDeletingCategory(null)}
                className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
              >
                Cancel
              </button>
              <button
                onClick={() => deletingCategory && deleteCategoryMutation.mutate(deletingCategory.id)}
                disabled={deleteCategoryMutation.isPending}
                className="px-4 py-2 text-sm bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50"
              >
                {deleteCategoryMutation.isPending ? "Deleting..." : "Delete"}
              </button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  );
}

function GroupRow({
  group,
  categoryCount,
  onEdit,
  onDelete,
}: {
  group: NetWorthGroup;
  categoryCount: number;
  onEdit: (group: NetWorthGroup) => void;
  onDelete: (group: NetWorthGroup) => void;
}) {
  return (
    <div className="flex items-center justify-between py-2 px-3 rounded-md hover:bg-gray-50 dark:hover:bg-gray-800/50">
      <div className="flex items-center gap-2">
        <span
          className="w-3 h-3 rounded-full"
          style={{ backgroundColor: group.color }}
        />
        <span className="text-sm text-gray-900 dark:text-gray-100">{group.name}</span>
        <span className="text-sm text-gray-500 dark:text-gray-400">
          ({categoryCount} {categoryCount === 1 ? "category" : "categories"})
        </span>
      </div>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onEdit(group)}
          className="p-1 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
          title="Edit"
        >
          <EditIcon />
        </button>
        <button
          onClick={() => onDelete(group)}
          className="p-1 text-gray-500 hover:text-red-600 dark:text-gray-400 dark:hover:text-red-400"
          title="Delete"
        >
          <DeleteIcon />
        </button>
      </div>
    </div>
  );
}

function CategoryRow({
  category,
  onEdit,
  onDelete,
}: {
  category: NetWorthCategory;
  onEdit: (cat: NetWorthCategory) => void;
  onDelete: (cat: NetWorthCategory) => void;
}) {
  return (
    <div className="flex items-center justify-between py-2 px-3 rounded-md hover:bg-gray-50 dark:hover:bg-gray-800/50">
      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-900 dark:text-gray-100">{category.name}</span>
        {!category.is_personal && (
          <span className="text-sm text-gray-400 dark:text-gray-500">(company)</span>
        )}
      </div>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onEdit(category)}
          className="p-1 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
          title="Edit"
        >
          <EditIcon />
        </button>
        <button
          onClick={() => onDelete(category)}
          className="p-1 text-gray-500 hover:text-red-600 dark:text-gray-400 dark:hover:text-red-400"
          title="Delete"
        >
          <DeleteIcon />
        </button>
      </div>
    </div>
  );
}

function ChevronDownIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
      <path
        d="M3 4.5L6 7.5L9 4.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function EditIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="14"
      height="14"
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
  );
}

function DeleteIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="14"
      height="14"
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
  );
}
