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
