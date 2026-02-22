export interface Account {
  id: number;
  name: string;
  balance: number;
  is_credit: boolean;
  updated_at: string;
}

export interface IncomeItem {
  id: number;
  name: string;
  gross_amount: number;
  is_taxed: boolean;
  tax_percentage?: number;
  is_deduction: boolean;
}

export interface ExpenseItem {
  id: number;
  name: string;
  amount: number;
  is_savings_goal: boolean;
}

export interface BudgetSettings {
  id: number;
  tax_percentage: number;
  updated_at: string;
}

export interface BudgetTotals {
  gross_income: number;
  net_income: number;
  current_balance: number;
  total_expenses: number;
  net_position: number;
}

export interface BudgetData {
  settings: BudgetSettings;
  income: IncomeItem[];
  accounts: Account[];
  expenses: ExpenseItem[];
  totals: BudgetTotals;
}

export type AccountFormData = Omit<Account, "id" | "updated_at">;
export type IncomeFormData = Omit<IncomeItem, "id">;
export type DeductionFormData = Omit<IncomeItem, "id">;
export type ExpenseFormData = Omit<ExpenseItem, "id">;
export type SavingsGoalFormData = Omit<ExpenseItem, "id">;
export type SettingsFormData = Pick<BudgetSettings, "tax_percentage">;

// Net Worth types
export type GroupType = "asset" | "liability";

export interface NetWorthGroup {
  id: number;
  name: string;
  group_type: GroupType;
  color: string;
  display_order: number;
  created_at: string;
}

export interface NetWorthCategory {
  id: number;
  name: string;
  group_id: number;
  group: NetWorthGroup;
  is_personal: boolean;
  display_order: number;
  created_at: string;
}

export interface NetWorthEntry {
  id: number;
  category_id: number;
  category: NetWorthCategory;
  amount: number;
}

export interface NetWorthSnapshot {
  id: number;
  month: number;
  year: number;
  timestamp: string;
  total_assets: number;
  total_liabilities: number;
  net_worth: number;
  change_from_previous: number;
  personal_wealth: number;
  company_wealth: number;
  entries: NetWorthEntry[];
  by_group: Record<string, number>;
  percentages: Record<string, number>;
}

export interface NetWorthEntryInput {
  category_id: number;
  amount: number;
}

export interface CreateSnapshotInput {
  month: number;
  year: number;
  entries: NetWorthEntryInput[];
}

export interface UpdateSnapshotInput {
  entries: NetWorthEntryInput[];
}

export interface CategoryFormData {
  name: string;
  group_id: number;
  is_personal: boolean;
  display_order: number;
}

export interface GroupFormData {
  name: string;
  group_type: GroupType;
  color: string;
  display_order: number;
}

// Goal types
export type GoalType = "net_worth" | "savings_rate" | "savings_goal";

export interface Goal {
  id: number;
  name: string;
  goal_type: GoalType;
  target_value: number;
  category_id: number | null;
  category?: NetWorthCategory | null;
  target_date: string | null;
  is_active: boolean;
  created_at: string;
}

export interface GoalFormData {
  name: string;
  goal_type: GoalType;
  target_value: number;
  category_id: number | null;
  target_date: string | null;
  is_active: boolean;
}

export interface GoalProgress {
  goal: Goal;
  current_value: number;
  target_value: number;
  progress_percentage: number;
  is_achieved: boolean;
  status: "on_track" | "behind" | null;
  data_months: number;
  category_name?: string | null;
}

// Forecast types
export type ForecastPeriod = "month" | "quarter" | "half_year" | "year";

export interface ForecastPoint {
  month: number;
  year: number;
  projected_net_worth: number;
}

export interface NetWorthForecast {
  period: ForecastPeriod;
  months_ahead: number;
  monthly_change_rate: number;
  data_points_used: number;
  projections: ForecastPoint[];
}
