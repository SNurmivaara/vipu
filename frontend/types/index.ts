export interface Account {
  id: number;
  name: string;
  balance: number;
  is_credit: boolean;
  updated_at: string;
  payment_due_day: number | null;
}

export type FrequencyUnit = "days" | "weeks" | "months" | "years";

/**
 * One-off corrections to the "money moves on its due day" assumption, each
 * holding a single occurrence date so only that occurrence shifts:
 * settled = already paid/received ahead of the day, pending = the day passed
 * without the money moving. Later occurrences, and the forecast, are unaffected.
 */
export interface OccurrenceOverrides {
  settled_occurrence: string | null;
  pending_occurrence: string | null;
}

export interface IncomeItem extends OccurrenceOverrides {
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

export interface ExpenseItem extends OccurrenceOverrides {
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

/**
 * A single dated occurrence of an item, as the period lists return it.
 * is_settled is the effective state of that occurrence (default plus any
 * override); can_settle marks the occurrences whose state may still be
 * corrected — the next one up and the last one to have come due this period.
 */
export interface OccurrenceState {
  next_occurrence_date: string | null;
  is_settled: boolean;
  can_settle: boolean;
}

/** ExpenseItem with computed next occurrence date for period display */
export interface ExpenseWithOccurrence extends ExpenseItem, OccurrenceState {}

/** IncomeItem with the one occurrence whose state is currently in question */
export interface IncomeWithOccurrence extends IncomeItem, OccurrenceState {}

export interface BudgetSettings {
  id: number;
  tax_percentage: number;
  updated_at: string;
  payday_day: number;
}

/**
 * One pay period's cash flow, as the backend's single period calculator
 * produces it. Every figure on the page that describes a period comes from
 * here, so the summary card, the section headers and the roadmap cannot
 * disagree about the same days.
 */
export interface PeriodFlow {
  start: string;
  end: string;
  /** Net pay arriving in the period, before payroll deductions */
  income: number;
  /** Payroll deductions, negative, taken out of that pay */
  deductions: number;
  bills: number;
  savings: number;
  card_payments: number;
  /** Pay actually landing in the account: income + deductions */
  money_in: number;
  /** Everything leaving: bills + savings + card payments */
  money_out: number;
  /** What the period leaves over, free to be swept out */
  net: number;
}

/** The lowest the cash gets while the projected periods play out */
export interface CashLowPoint {
  date: string;
  balance: number;
}

export interface BudgetTotals {
  cash_low_point: CashLowPoint;
  /** Today through the next payday, the part-period we are standing in */
  period_current: PeriodFlow;
  /** Payday to the following payday */
  period_next: PeriodFlow;
  gross_income: number;
  net_income: number;
  current_balance: number;
  /** Cash accounts only, before card debt is netted off */
  cash_balance: number;
  /** Sum of credit card balances, negative when money is owed */
  card_debt: number;
  total_expenses: number;
  net_position: number;
  // Frequency-normalized monthly rates (one-time items excluded)
  monthly_expenses: number;
  monthly_net_income: number;
  monthly_surplus: number;
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
  /** Next period's own money less that period's bills and card payments */
  unallocated_next_period: number;
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
  income: IncomeWithOccurrence[];
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

// Occurrence overrides are set by ticking a payment off, never by the edit
// form, so they are not part of the form payloads.
export type AccountFormData = Omit<Account, "id" | "updated_at">;
export type IncomeFormData = Omit<IncomeItem, "id" | keyof OccurrenceOverrides>;
export type DeductionFormData = IncomeFormData;
export type ExpenseFormData = Omit<ExpenseItem, "id" | keyof OccurrenceOverrides>;
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
  change_percent: number;
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
// net_worth lives on the Wealth page; savings_goal and debt_payoff are
// roadmap steps funded sequentially from the monthly budget surplus.
export type GoalType = "net_worth" | "savings_goal" | "debt_payoff";

export interface Goal {
  id: number;
  name: string;
  goal_type: GoalType;
  target_value: number;
  category_id: number | null;
  category?: NetWorthCategory | null;
  target_date: string | null;
  is_active: boolean;
  priority: number | null;
  current_amount: number | null;
  created_at: string;
}

export interface GoalFormData {
  name: string;
  goal_type: GoalType;
  target_value: number;
  category_id: number | null;
  current_amount?: number | null;
  target_date: string | null;
  is_active: boolean;
}

// Roadmap: sequential plan of savings/debt goals funded by the budget surplus
export type RoadmapStepStatus = "completed" | "active" | "upcoming";

export interface RoadmapStep {
  goal: Goal;
  current_value: number;
  remaining: number;
  progress_percentage: number;
  status: RoadmapStepStatus;
  months_to_complete: number | null;
  projected_completion_date: string | null;
}

export interface RoadmapData {
  surplus_monthly: number;
  /**
   * Net cash the plan starts from: all account balances (credit cards assumed
   * paid in full) plus pending one-time items. Clamped at zero — spare cash is
   * never a head start, but a shortfall is paid off before any step progresses.
   */
  starting_position: number;
  /** Pending one-time items, excluded from the monthly rate. Negative = owed. */
  pending_one_time_net: number;
  /** Months of surplus spent clearing the shortfall before step 1 progresses. */
  shortfall_months: number;
  goals: RoadmapStep[];
}

export interface GoalProgress {
  goal: Goal;
  current_value: number;
  target_value: number;
  progress_percentage: number;
  is_achieved: boolean;
  status: "on_track" | "behind" | null;
  status_reason?: string | null;
  required_monthly?: number | null;
  recent_monthly?: number | null;
  projected_value?: number | null;
  months_remaining?: number | null;
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
  /** Asset group monthly savings are paid into; null spreads them across the mix */
  contributionGroup: string | null;
  /** Interest rate and monthly payment per liability group name */
  liabilityTerms: Record<string, { rate_pct: number; monthly_payment: number }>;
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
  contribution_group: string | null;
  liability_terms: Record<string, { rate_pct: number; monthly_payment: number }>;
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
  /** Nominal return implied by the mix at this point; rises as the mix drifts */
  blended_return_pct?: number | null;
  // Age-specific FIRE numbers (present when pension mode is active)
  fire_number_at_age?: number | null;
  coast_fire_number_at_age?: number | null;
  // Pension drawdown projections (present when pension mode is active)
  net_worth_early?: number | null;
  net_worth_normal?: number | null;
  net_worth_late?: number | null;
}

export interface FireResultAPI {
  fire_number: number;
  fire_number_now: number;
  coast_fire_number: number;
  coast_fire_reached: boolean;
  years_to_fire: number | null;
  fire_age: number | null;
  coast_fire_age: number | null;
  on_track: boolean;
  portfolio_depleted_age: number | null;
  projections: FireProjectionPointAPI[];
  pension: FirePensionResultAPI | null;
  /** Conditions the projection cannot model away, e.g. negative amortization */
  warnings?: { code: string; group: string }[];
}

// FIRE inputs derived on the backend from persisted settings + snapshots + budget
export interface ForecastingDerivedAPI {
  current_net_worth: number;
  monthly_savings: number;
  annual_expenses: number;
  weighted_return_pct: number;
  /** Fisher-converted real return at the current mix, as the projection compounds it */
  real_return_pct: number;
  contribution_group: string | null;
  gross_assets: number;
  /** Amounts owed per liability group name, as positive magnitudes */
  liabilities_by_group: Record<string, number>;
  liability_terms: Record<string, { rate_pct: number; monthly_payment: number }>;
  pension_monthly_salary: number;
  pension_active: boolean;
  by_group: Record<string, number>;
  group_return_rates: Record<string, number>;
  monthly_savings_is_override: boolean;
  annual_expenses_is_override: boolean;
  target_retirement_age: number;
}

// Response of GET /api/forecasting/projection: FIRE result + the derived inputs
export interface ForecastingProjectionAPI extends FireResultAPI {
  derived: ForecastingDerivedAPI;
}
