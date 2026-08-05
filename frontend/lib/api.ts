import axios from "axios";
import {
  BudgetData,
  BudgetSnapshot,
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
  RoadmapData,
  NetWorthForecast,
  ForecastPeriod,
  ForecastingSettingsAPI,
  FireCalculateInput,
  FireResultAPI,
  ForecastingProjectionAPI,
} from "@/types";

export const api = axios.create({
  baseURL: "/api",
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

// Budget Snapshots
export const createBudgetSnapshot = async (
  notes?: string
): Promise<{ snapshot: BudgetSnapshot; updated: boolean }> => {
  const { data } = await api.post<{ snapshot: BudgetSnapshot; updated: boolean }>(
    "/budget/snapshots",
    notes ? { notes } : {}
  );
  return data;
};

export interface BudgetSnapshotsResponse {
  snapshots: BudgetSnapshot[];
  total: number;
}

export const fetchBudgetSnapshots = async (
  limit = 50,
  offset = 0
): Promise<BudgetSnapshotsResponse> => {
  const { data } = await api.get<BudgetSnapshotsResponse>(
    "/budget/snapshots",
    { params: { limit, offset } }
  );
  return data;
};

export const updateBudgetSnapshot = async (
  id: number,
  input: {
    entries?: Array<{
      account_name: string;
      balance: number;
      is_credit: boolean;
      account_id?: number | null;
    }>;
    notes?: string | null;
  }
): Promise<{ snapshot: BudgetSnapshot }> => {
  const { data } = await api.put<{ snapshot: BudgetSnapshot }>(
    `/budget/snapshots/${id}`,
    input
  );
  return data;
};

export const deleteBudgetSnapshot = async (id: number): Promise<void> => {
  await api.delete(`/budget/snapshots/${id}`);
};

// Reset all budget data
export const resetBudget = async (): Promise<{ message: string }> => {
  const { data } = await api.post<{ message: string }>("/reset");
  return data;
};

// Get budget accounts for snapshot prefill
export interface SnapshotPrefillItem {
  name: string;
  amount: number;
  is_liability: boolean;
}

export const getSnapshotPrefill = async (): Promise<SnapshotPrefillItem[]> => {
  const { data } = await api.get<SnapshotPrefillItem[]>("/budget/snapshot-prefill");
  return data;
};

// Export data type (version 2 includes net worth and goals)
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
    is_deduction?: boolean;
  }[];
  expenses: {
    name: string;
    amount: number;
    is_savings_goal: boolean;
  }[];
  // Net worth data (version 2)
  networth_groups?: {
    name: string;
    group_type: "asset" | "liability";
    color: string;
    display_order: number;
  }[];
  networth_categories?: {
    name: string;
    group_name: string;
    is_personal: boolean;
    display_order: number;
  }[];
  networth_snapshots?: {
    month: number;
    year: number;
    entries: {
      category_name: string;
      amount: number;
    }[];
  }[];
  goals?: {
    name: string;
    goal_type: string;
    target_value: number;
    category_name: string | null;
    target_date: string | null;
    is_active: boolean;
    priority?: number | null;
    current_amount?: number | null;
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

// Get previous month's snapshot entries for prefill
export interface PreviousEntriesResponse {
  previous_month: number;
  previous_year: number;
  entries: Record<number, number>; // category_id -> amount
}

export const getPreviousEntries = async (
  year: number,
  month: number
): Promise<PreviousEntriesResponse> => {
  const { data } = await api.get<PreviousEntriesResponse>(
    `/networth/${year}/${month}/previous-entries`
  );
  return data;
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

// Roadmap
export const fetchRoadmap = async (): Promise<RoadmapData> => {
  const { data } = await api.get<RoadmapData>("/goals/roadmap");
  return data;
};

export const reorderGoals = async (goalIds: number[]): Promise<Goal[]> => {
  const { data } = await api.put<Goal[]>("/goals/reorder", {
    goal_ids: goalIds,
  });
  return data;
};

// Forecasting Settings
export const fetchForecastingSettings = async (): Promise<ForecastingSettingsAPI> => {
  const { data } = await api.get<ForecastingSettingsAPI>("/forecasting/settings");
  return data;
};

export const updateForecastingSettings = async (
  settings: Partial<Omit<ForecastingSettingsAPI, "id" | "updated_at">>
): Promise<ForecastingSettingsAPI> => {
  const { data } = await api.put<ForecastingSettingsAPI>(
    "/forecasting/settings",
    settings
  );
  return data;
};

// Forecast
export interface FetchForecastParams {
  period?: ForecastPeriod;
  months_ahead?: number;
}

export const fetchForecast = async (
  params: FetchForecastParams = {}
): Promise<NetWorthForecast> => {
  const searchParams = new URLSearchParams();
  if (params.period) {
    searchParams.set("period", params.period);
  }
  if (params.months_ahead) {
    searchParams.set("months_ahead", params.months_ahead.toString());
  }
  const queryString = searchParams.toString();
  const url = queryString ? `/networth/forecast?${queryString}` : "/networth/forecast";
  const { data } = await api.get<NetWorthForecast>(url);
  return data;
};

// FIRE calculation
export const calculateFire = async (
  input: FireCalculateInput
): Promise<FireResultAPI> => {
  const { data } = await api.post<FireResultAPI>("/forecasting/calculate", input);
  return data;
};

// FIRE projection derived on the backend from persisted state
export const fetchForecastingProjection =
  async (): Promise<ForecastingProjectionAPI> => {
    const { data } = await api.get<ForecastingProjectionAPI>(
      "/forecasting/projection"
    );
    return data;
  };
