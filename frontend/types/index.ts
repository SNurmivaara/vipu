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
