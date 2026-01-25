import axios from "axios";
import {
  BudgetData,
  Account,
  AccountFormData,
  IncomeItem,
  IncomeFormData,
  ExpenseItem,
  ExpenseFormData,
  BudgetSettings,
  SettingsFormData,
  NetWorthGroup,
  NetWorthCategory,
  NetWorthSnapshot,
  CreateSnapshotInput,
  UpdateSnapshotInput,
  GroupFormData,
  CategoryFormData,
  Goal,
  GoalFormData,
  GoalProgress,
} from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

export const api = axios.create({
  baseURL: `${API_URL}/api`,
  headers: {
    "Content-Type": "application/json",
  },
});

// Budget
export const fetchBudget = async (): Promise<BudgetData> => {
  const { data } = await api.get<BudgetData>("/budget/current");
  return data;
};

// Accounts
export const createAccount = async (
  account: AccountFormData
): Promise<Account> => {
  const { data } = await api.post<Account>("/accounts", account);
  return data;
};

export const updateAccount = async (
  id: number,
  account: AccountFormData
): Promise<Account> => {
  const { data } = await api.put<Account>(`/accounts/${id}`, account);
  return data;
};

export const deleteAccount = async (id: number): Promise<void> => {
  await api.delete(`/accounts/${id}`);
};

// Income
export const createIncome = async (
  income: IncomeFormData
): Promise<IncomeItem> => {
  const { data } = await api.post<IncomeItem>("/income", income);
  return data;
};

export const updateIncome = async (
  id: number,
  income: IncomeFormData
): Promise<IncomeItem> => {
  const { data } = await api.put<IncomeItem>(`/income/${id}`, income);
  return data;
};

export const deleteIncome = async (id: number): Promise<void> => {
  await api.delete(`/income/${id}`);
};

// Expenses
export const createExpense = async (
  expense: ExpenseFormData
): Promise<ExpenseItem> => {
  const { data } = await api.post<ExpenseItem>("/expenses", expense);
  return data;
};

export const updateExpense = async (
  id: number,
  expense: ExpenseFormData
): Promise<ExpenseItem> => {
  const { data } = await api.put<ExpenseItem>(`/expenses/${id}`, expense);
  return data;
};

export const deleteExpense = async (id: number): Promise<void> => {
  await api.delete(`/expenses/${id}`);
};

// Settings
export const updateSettings = async (
  settings: SettingsFormData
): Promise<BudgetSettings> => {
  const { data } = await api.put<BudgetSettings>("/settings", settings);
  return data;
};

// Seed (for development)
export const seedData = async (): Promise<{ message: string }> => {
  const { data } = await api.post<{ message: string }>("/seed");
  return data;
};

// Reset all budget data
export const resetBudget = async (): Promise<{ message: string }> => {
  const { data } = await api.post<{ message: string }>("/reset");
  return data;
};

// Export data type
export interface ExportData {
  version: number;
  settings: {
    tax_percentage: number;
  };
  accounts: {
    name: string;
    balance: number;
    is_credit: boolean;
  }[];
  income: {
    name: string;
    gross_amount: number;
    is_taxed: boolean;
    tax_percentage: number | null;
  }[];
  expenses: {
    name: string;
    amount: number;
    is_savings_goal: boolean;
  }[];
}

// Export budget data
export const exportBudget = async (): Promise<ExportData> => {
  const { data } = await api.get<ExportData>("/export");
  return data;
};

// Import budget data
export const importBudget = async (
  importData: ExportData
): Promise<{ message: string }> => {
  const { data } = await api.post<{ message: string }>("/import", importData);
  return data;
};

// Net Worth Categories
export const fetchCategories = async (): Promise<NetWorthCategory[]> => {
  const { data } = await api.get<NetWorthCategory[]>("/networth/categories");
  return data;
};

export const seedCategories = async (): Promise<{ message: string }> => {
  const { data } = await api.post<{ message: string }>("/networth/categories/seed");
  return data;
};

// Net Worth Snapshots
export const fetchSnapshots = async (): Promise<NetWorthSnapshot[]> => {
  const { data } = await api.get<NetWorthSnapshot[]>("/networth");
  return data;
};

export const fetchSnapshot = async (year: number, month: number): Promise<NetWorthSnapshot> => {
  const { data } = await api.get<NetWorthSnapshot>(`/networth/${year}/${month}`);
  return data;
};

export const createSnapshot = async (input: CreateSnapshotInput): Promise<NetWorthSnapshot> => {
  const { data } = await api.post<NetWorthSnapshot>("/networth", input);
  return data;
};

export const updateSnapshot = async (id: number, input: UpdateSnapshotInput): Promise<NetWorthSnapshot> => {
  const { data } = await api.put<NetWorthSnapshot>(`/networth/${id}`, input);
  return data;
};

export const deleteSnapshot = async (id: number): Promise<void> => {
  await api.delete(`/networth/${id}`);
};

export const seedNetWorth = async (): Promise<{ message: string }> => {
  const { data } = await api.post<{ message: string }>("/networth/seed");
  return data;
};

export const resetNetWorth = async (): Promise<{ message: string }> => {
  const { data } = await api.post<{ message: string }>("/networth/reset");
  return data;
};

// Category CRUD
export const createCategory = async (category: CategoryFormData): Promise<NetWorthCategory> => {
  const { data } = await api.post<NetWorthCategory>("/networth/categories", category);
  return data;
};

export const updateCategory = async (id: number, category: Partial<CategoryFormData>): Promise<NetWorthCategory> => {
  const { data } = await api.put<NetWorthCategory>(`/networth/categories/${id}`, category);
  return data;
};

export const deleteCategory = async (id: number): Promise<void> => {
  await api.delete(`/networth/categories/${id}`);
};

// Net Worth Groups
export const fetchGroups = async (): Promise<NetWorthGroup[]> => {
  const { data } = await api.get<NetWorthGroup[]>("/networth/groups");
  return data;
};

export const createGroup = async (group: GroupFormData): Promise<NetWorthGroup> => {
  const { data } = await api.post<NetWorthGroup>("/networth/groups", group);
  return data;
};

export const updateGroup = async (id: number, group: Partial<GroupFormData>): Promise<NetWorthGroup> => {
  const { data } = await api.put<NetWorthGroup>(`/networth/groups/${id}`, group);
  return data;
};

export const deleteGroup = async (id: number): Promise<void> => {
  await api.delete(`/networth/groups/${id}`);
};

// Goals
export const fetchGoals = async (): Promise<Goal[]> => {
  const { data } = await api.get<Goal[]>("/goals");
  return data;
};

export const fetchGoalsProgress = async (): Promise<GoalProgress[]> => {
  const { data } = await api.get<GoalProgress[]>("/goals/progress");
  return data;
};

export const createGoal = async (goal: GoalFormData): Promise<Goal> => {
  const { data } = await api.post<Goal>("/goals", goal);
  return data;
};

export const updateGoal = async (
  id: number,
  goal: Partial<GoalFormData>
): Promise<Goal> => {
  const { data } = await api.put<Goal>(`/goals/${id}`, goal);
  return data;
};

export const deleteGoal = async (id: number): Promise<void> => {
  await api.delete(`/goals/${id}`);
};
