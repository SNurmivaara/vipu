export interface Account {
  id: number;
  name: string;
  balance: number;
  is_credit: boolean;
  updated_at: string;
  payment_due_day: number | null;
}

export type FrequencyUnit = "days" | "weeks" | "months" | "years";

export interface IncomeItem {
  id: number;
  name: string;
  gross_amount: number;
  is_taxed: boolean;
  tax_percentage?: number;
  is_deduction: boolean;
  due_day: number;
  frequency_value: number;
  frequency_unit: FrequencyUnit;
  start_date: string | null;
  end_date: string | null;
  is_ephemeral: boolean;
  archived_at: string | null;
}

export interface ExpenseItem {
  id: number;
  name: string;
  amount: number;
  is_savings_goal: boolean;
  due_day: number;
  frequency_value: number;
  frequency_unit: FrequencyUnit;
  start_date: string | null;
  end_date: string | null;
  is_ephemeral: boolean;
  archived_at: string | null;
}

/** ExpenseItem with computed next occurrence date for period display */
export interface ExpenseWithOccurrence extends ExpenseItem {
  next_occurrence_date: string | null;
}

export interface BudgetSettings {
  id: number;
  tax_percentage: number;
  updated_at: string;
  payday_day: number;
}

export interface BudgetTotals {
  gross_income: number;
  net_income: number;
  current_balance: number;
  total_expenses: number;
  net_position: number;
  // Deadline-aware totals
  next_payday: string;
  expenses_before_payday: number;
  income_before_payday: number;
  savings_before_payday: number;
  cc_payments_before_payday: number;
  // Next period totals (payday to following payday)
  next_period_end: string;
  expenses_next_period: number;
  savings_next_period: number;
  cc_payments_next_period: number;
  income_next_period: number;
  // Expense IDs for each period (for frontend filtering) - backward compat
  expenses_before_payday_ids: number[];
  expenses_next_period_ids: number[];
  expenses_future_ids: number[];
  // Expenses with occurrence dates for each period
  expenses_before_payday_list: ExpenseWithOccurrence[];
  expenses_next_period_list: ExpenseWithOccurrence[];
  expenses_future_list: ExpenseWithOccurrence[];
}

export interface BudgetData {
  settings: BudgetSettings;
  income: IncomeItem[];
  accounts: Account[];
  expenses: ExpenseItem[];
  totals: BudgetTotals;
  archived_income: IncomeItem[];
  archived_expenses: ExpenseItem[];
}

// Budget Snapshot types
export interface BudgetBalanceEntry {
  id: number;
  account_id: number | null;
  account_name: string;
  balance: number;
  is_credit: boolean;
}

export interface BudgetSnapshot {
  id: number;
  date: string;
  timestamp: string;
  current_balance: number;
  change_from_previous: number;
  pay_period_change: number;
  pay_period_start: string;
  notes: string | null;
  entries: BudgetBalanceEntry[];
}

export type AccountFormData = Omit<Account, "id" | "updated_at">;
export type IncomeFormData = Omit<IncomeItem, "id">;
export type DeductionFormData = Omit<IncomeItem, "id">;
export type ExpenseFormData = Omit<ExpenseItem, "id">;
export type SavingsGoalFormData = Omit<ExpenseItem, "id">;
export type SettingsFormData = Pick<BudgetSettings, "tax_percentage" | "payday_day">;

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
// New types: net_worth, savings_rate, savings_goal
// Old types kept for backward compatibility: net_worth_target, category_target, category_rate
export type GoalType =
  | "net_worth"
  | "savings_rate"
  | "savings_goal"
  | "net_worth_target"
  | "category_target"
  | "category_rate";

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

// FIRE / Forecasting settings (frontend camelCase)
export interface ForecastingSettings {
  inflationPct: number;
  safeWithdrawalRate: number;
  currentAge: number;
  targetRetirementAge: number;
  monthlySavingsOverride: number | null;
  annualExpensesOverride: number | null;
  // Pension (TyEL) — null values = pension features disabled
  pensionAccruedMonthly: number | null;
  pensionMonthlySalaryOverride: number | null;
  pensionAccrualRate: number;
  pensionFullAge: number;
  pensionGuaranteeEnabled: boolean;
  pensionGuaranteeAmount: number;
  lifeExpectancy: number;
  /** Expected annual return % per net worth group name */
  groupReturnRates: Record<string, number>;
}

// API response shape (snake_case from backend)
export interface ForecastingSettingsAPI {
  id: number;
  inflation_pct: number;
  safe_withdrawal_rate: number;
  current_age: number;
  target_retirement_age: number;
  monthly_savings_override: number | null;
  annual_expenses_override: number | null;
  pension_accrued_monthly: number | null;
  pension_monthly_salary_override: number | null;
  pension_accrual_rate: number;
  pension_full_age: number;
  pension_guarantee_enabled: boolean;
  pension_guarantee_amount: number;
  life_expectancy: number;
  group_return_rates: Record<string, number>;
  updated_at: string;
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

// FIRE calculation API types (snake_case from backend)
export interface FireCalculateInput {
  current_net_worth: number;
  monthly_contribution: number;
  annual_expenses: number;
  annual_return_pct: number;
  inflation_pct: number;
  current_age: number;
  target_retirement_age: number;
  safe_withdrawal_rate: number;
  pension_accrued_monthly?: number | null;
  pension_monthly_salary?: number | null;
  pension_accrual_rate?: number;
  pension_full_age?: number;
  pension_guarantee_enabled?: boolean;
  pension_guarantee_amount?: number;
  life_expectancy?: number;
}

export interface FirePensionScenarioAPI {
  label: "early" | "normal" | "late";
  pension_start_age: number;
  monthly_pension: number;
  annual_pension: number;
  pension_fire_number: number;
}

export interface FirePensionResultAPI {
  projected_monthly_pension: number;
  scenarios: FirePensionScenarioAPI[];
  pension_coast_fire_number: number;
  guarantee_active: boolean;
  guarantee_amount: number;
  crossover_age: number | null;
}

export interface FireProjectionPointAPI {
  age: number;
  year: number;
  month: number;
  net_worth: number;
  coast_net_worth: number;
  net_worth_early?: number | null;
  net_worth_normal?: number | null;
  net_worth_late?: number | null;
}

export interface FireResultAPI {
  fire_number: number;
  coast_fire_number: number;
  coast_fire_reached: boolean;
  years_to_fire: number | null;
  fire_age: number | null;
  coast_fire_age: number | null;
  on_track: boolean;
  portfolio_depleted_age: number | null;
  projections: FireProjectionPointAPI[];
  pension: FirePensionResultAPI | null;
}
