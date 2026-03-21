/**
 * Financial Independence / Retire Early (FIRE) calculation utilities.
 *
 * All monetary values are in the user's currency (EUR).
 * Return rates are annual percentages (e.g., 7 for 7%).
 * Inflation is an annual percentage (e.g., 2 for 2%).
 */

export interface FireInputs {
  currentNetWorth: number;
  monthlyContribution: number; // monthly savings/investment
  annualExpenses: number;
  annualReturnPct: number; // e.g. 7 for 7%
  inflationPct: number; // e.g. 2 for 2%
  currentAge: number;
  targetRetirementAge: number;
  safeWithdrawalRate: number; // e.g. 4 for 4%
  // Optional pension inputs (presence activates pension mode)
  pensionAccruedMonthly?: number;
  pensionMonthlySalary?: number;
  pensionAccrualRate?: number; // default 1.5
  pensionFullAge?: number; // default 68
  pensionGuaranteeEnabled?: boolean;
  pensionGuaranteeAmount?: number; // default 990
  lifeExpectancy?: number; // default 95
}

export interface PensionScenario {
  label: "early" | "normal" | "late";
  pensionStartAge: number;
  monthlyPension: number;
  annualPension: number;
  pensionFireNumber: number;
}

export interface PensionResult {
  projectedMonthlyPension: number; // at FIRE age, before early/late adjustment
  scenarios: [PensionScenario, PensionScenario, PensionScenario];
  pensionCoastFireNumber: number;
  guaranteeActive: boolean; // true when guarantee is enabled AND projected TyEL < guarantee
  guaranteeAmount: number;
  crossoverAge: number | null; // age at which projected TyEL >= guarantee amount
}

export interface FireResult {
  fireNumber: number;
  coastFireNumber: number;
  coastFireReached: boolean;
  yearsToFire: number | null; // null if unreachable
  fireAge: number | null;
  coastFireAge: number | null; // age when Coast FIRE was/will be reached
  onTrack: boolean; // true if yearsToFire <= years to target retirement
  portfolioDepletedAge: number | null; // age when portfolio hits 0 (null if it doesn't)
  projections: ProjectionPoint[];
  pension?: PensionResult;
}

export interface ProjectionPoint {
  age: number;
  year: number;
  month: number;
  netWorth: number;
  coastNetWorth: number;
  // Pension drawdown projections (present when pension is active)
  netWorthEarly?: number;
  netWorthNormal?: number;
  netWorthLate?: number;
}

// ---------------------------------------------------------------------------
// Core calculation functions
// ---------------------------------------------------------------------------

/**
 * Calculate the FIRE number based on annual expenses and safe withdrawal rate.
 * FIRE Number = Annual Expenses / (SWR / 100)
 */
export function calcFireNumber(annualExpenses: number, swrPct: number): number {
  if (swrPct <= 0) return Infinity;
  return annualExpenses / (swrPct / 100);
}

/**
 * Calculate Coast FIRE number.
 * This is how much you need RIGHT NOW so that compound growth alone
 * (no further contributions) reaches your FIRE number by retirement.
 *
 * CoastFIRE = FIRE_Number / (1 + realReturn)^yearsToRetirement
 */
export function calcCoastFireNumber(
  fireNumber: number,
  realAnnualReturnPct: number,
  yearsToRetirement: number
): number {
  if (yearsToRetirement <= 0) return fireNumber;
  const r = realAnnualReturnPct / 100;
  return fireNumber / Math.pow(1 + r, yearsToRetirement);
}

/**
 * Calculate years to reach FIRE using iterative month-by-month simulation
 * with compound growth and monthly contributions.
 *
 * Uses real (inflation-adjusted) returns.
 * Returns null if FIRE is unreachable within 100 years.
 */
export function calcYearsToFire(
  currentNetWorth: number,
  monthlyContribution: number,
  fireNumber: number,
  realAnnualReturnPct: number
): number | null {
  if (currentNetWorth >= fireNumber) return 0;

  const monthlyReturn = Math.pow(1 + realAnnualReturnPct / 100, 1 / 12) - 1;
  let nw = currentNetWorth;
  const maxMonths = 100 * 12;

  for (let m = 1; m <= maxMonths; m++) {
    nw = nw * (1 + monthlyReturn) + monthlyContribution;
    if (nw >= fireNumber) {
      return m / 12;
    }
  }

  return null;
}

/**
 * Calculate the age at which you reach Coast FIRE.
 * At each month, checks: can current NW (with contributions) compound to
 * the FIRE number in the remaining time without further contributions?
 * Returns null if unreachable before target retirement age.
 */
export function calcCoastFireAge(
  currentNetWorth: number,
  monthlyContribution: number,
  fireNumber: number,
  realAnnualReturnPct: number,
  currentAge: number,
  targetRetirementAge: number
): number | null {
  const r = realAnnualReturnPct / 100;
  const monthlyReturn = Math.pow(1 + r, 1 / 12) - 1;
  const totalMonths = Math.round((targetRetirementAge - currentAge) * 12);

  if (totalMonths <= 0) return null;

  // Check starting point
  const coastNeededNow = fireNumber / Math.pow(1 + r, targetRetirementAge - currentAge);
  if (currentNetWorth >= coastNeededNow) return currentAge;

  let nw = currentNetWorth;

  for (let m = 1; m <= totalMonths; m++) {
    nw = nw * (1 + monthlyReturn) + monthlyContribution;
    const age = currentAge + m / 12;
    const yearsRemaining = targetRetirementAge - age;
    if (yearsRemaining <= 0) break;
    const coastNeeded = fireNumber / Math.pow(1 + r, yearsRemaining);
    if (nw >= coastNeeded) {
      return Math.round(age * 10) / 10;
    }
  }

  return null;
}

// ---------------------------------------------------------------------------
// Pension calculation functions
// ---------------------------------------------------------------------------

/** Early/late pension adjustment rate per month (Finnish TyEL). */
const PENSION_ADJUSTMENT_PER_MONTH = 0.004;

/**
 * Project monthly pension at FIRE age based on current accrual and future work.
 * Accrual stops when you FIRE (stop working).
 */
export function calcProjectedMonthlyPension(
  accruedMonthly: number,
  currentAge: number,
  fireAge: number,
  monthlySalary: number,
  accrualRatePct: number
): number {
  const yearsOfAccrual = Math.max(0, fireAge - currentAge);
  // Annual accrual = annual salary * rate. Monthly pension increase per year = monthlySalary * rate.
  const additionalMonthlyPension =
    yearsOfAccrual * monthlySalary * (accrualRatePct / 100);
  return accruedMonthly + additionalMonthlyPension;
}

/**
 * Apply early/late pension adjustment (0.4%/month from full pension age).
 * Early = reduction, late = bonus. Returns adjusted monthly pension.
 */
export function calcPensionAdjustment(
  projectedMonthly: number,
  pensionFullAge: number,
  pensionStartAge: number
): number {
  const monthsDelta = (pensionStartAge - pensionFullAge) * 12;
  const adjustmentFactor = 1 + monthsDelta * PENSION_ADJUSTMENT_PER_MONTH;
  return Math.max(0, projectedMonthly * adjustmentFactor);
}

/**
 * Present value of an annuity: fixed annual payment for N years at real return r.
 * Used for die-with-zero calculations.
 */
export function pvAnnuity(
  annualPayment: number,
  years: number,
  realAnnualReturn: number
): number {
  if (years <= 0 || annualPayment <= 0) return 0;
  if (Math.abs(realAnnualReturn) < 1e-10) return annualPayment * years;
  const r = realAnnualReturn;
  return annualPayment * (1 - Math.pow(1 + r, -years)) / r;
}

/**
 * Pension-adjusted FIRE number using two-phase die-with-zero model.
 *
 * Phase 1 (FIRE age → pension start): portfolio covers ALL expenses.
 * Phase 2 (pension start → life expectancy): portfolio covers (expenses - pension).
 */
export function calcPensionFireNumber(
  annualExpenses: number,
  annualPension: number,
  fireAge: number,
  pensionStartAge: number,
  lifeExpectancy: number,
  realAnnualReturn: number
): number {
  const r = realAnnualReturn;
  const phase1Years = Math.max(0, pensionStartAge - fireAge);
  const phase2Years = Math.max(0, lifeExpectancy - pensionStartAge);
  const phase2Gap = Math.max(0, annualExpenses - annualPension);

  const phase1PV = pvAnnuity(annualExpenses, phase1Years, r);
  const phase2PVatPensionAge = pvAnnuity(phase2Gap, phase2Years, r);

  // Discount phase 2 back to FIRE age
  const discountFactor =
    phase1Years > 0 ? Math.pow(1 + r, -phase1Years) : 1;
  const phase2PV = phase2PVatPensionAge * discountFactor;

  return phase1PV + phase2PV;
}

/**
 * Calculate the age at which projected TyEL pension >= guarantee amount.
 * Returns null if already exceeded or if it never crosses within a reasonable timeframe.
 */
export function calcGuaranteeCrossoverAge(
  accruedMonthly: number,
  currentAge: number,
  monthlySalary: number,
  accrualRatePct: number,
  guaranteeAmount: number,
  maxAge: number
): number | null {
  if (accruedMonthly >= guaranteeAmount) return currentAge;
  const annualAccrual = monthlySalary * (accrualRatePct / 100);
  if (annualAccrual <= 0) return null;
  const yearsNeeded = (guaranteeAmount - accruedMonthly) / annualAccrual;
  const crossoverAge = currentAge + yearsNeeded;
  return crossoverAge <= maxAge ? Math.round(crossoverAge * 10) / 10 : null;
}

/**
 * Generate the 3 pension scenarios (early / normal / late).
 */
export function generatePensionScenarios(
  projectedMonthlyPension: number,
  pensionFullAge: number,
  fireAge: number,
  annualExpenses: number,
  lifeExpectancy: number,
  realAnnualReturn: number
): [PensionScenario, PensionScenario, PensionScenario] {
  const configs: Array<{ label: "early" | "normal" | "late"; offset: number }> = [
    { label: "early", offset: -3 },
    { label: "normal", offset: 0 },
    { label: "late", offset: 3 },
  ];

  return configs.map(({ label, offset }) => {
    const pensionStartAge = pensionFullAge + offset;
    const monthlyPension = calcPensionAdjustment(
      projectedMonthlyPension,
      pensionFullAge,
      pensionStartAge
    );
    const annualPension = monthlyPension * 12;
    const pensionFireNumber = calcPensionFireNumber(
      annualExpenses,
      annualPension,
      fireAge,
      pensionStartAge,
      lifeExpectancy,
      realAnnualReturn
    );
    return { label, pensionStartAge, monthlyPension, annualPension, pensionFireNumber };
  }) as [PensionScenario, PensionScenario, PensionScenario];
}

// ---------------------------------------------------------------------------
// Projection generation
// ---------------------------------------------------------------------------

/**
 * Generate month-by-month projections for net worth growth.
 * Includes both "saving" scenario and "coast" scenario (no further contributions).
 * When pension inputs are present, extends past FIRE age with drawdown projections.
 */
export function generateProjections(
  inputs: FireInputs,
  yearsAhead: number = 40,
  pensionResult?: PensionResult
): ProjectionPoint[] {
  const realReturnPct = inputs.annualReturnPct - inputs.inflationPct;
  const monthlyReturn = Math.pow(1 + realReturnPct / 100, 1 / 12) - 1;
  const totalMonths = yearsAhead * 12;
  const currentYear = new Date().getFullYear();
  const currentMonth = new Date().getMonth() + 1;

  const points: ProjectionPoint[] = [];
  const hasPension = !!pensionResult;

  // Fire age for drawdown transition — when pension is active, use target retirement age
  const fireAge = hasPension ? inputs.targetRetirementAge : Infinity;

  const monthlyExpenses = inputs.annualExpenses / 12;
  const earlyPensionMonthly = hasPension ? pensionResult!.scenarios[0].monthlyPension : 0;
  const normalPensionMonthly = hasPension ? pensionResult!.scenarios[1].monthlyPension : 0;
  const latePensionMonthly = hasPension ? pensionResult!.scenarios[2].monthlyPension : 0;
  const earlyStartAge = hasPension ? pensionResult!.scenarios[0].pensionStartAge : Infinity;
  const normalStartAge = hasPension ? pensionResult!.scenarios[1].pensionStartAge : Infinity;
  const lateStartAge = hasPension ? pensionResult!.scenarios[2].pensionStartAge : Infinity;

  let nw = inputs.currentNetWorth;
  let coastNw = inputs.currentNetWorth;
  // Three drawdown tracks (diverge once pension scenarios differ)
  let nwEarly = inputs.currentNetWorth;
  let nwNormal = inputs.currentNetWorth;
  let nwLate = inputs.currentNetWorth;
  let depletedAge: number | null = null;

  // Add starting point
  const startPoint: ProjectionPoint = {
    age: inputs.currentAge,
    year: currentYear,
    month: currentMonth,
    netWorth: nw,
    coastNetWorth: coastNw,
  };
  if (hasPension) {
    startPoint.netWorthEarly = nw;
    startPoint.netWorthNormal = nw;
    startPoint.netWorthLate = nw;
  }
  points.push(startPoint);

  for (let m = 1; m <= totalMonths; m++) {
    const age = inputs.currentAge + m / 12;
    const inDrawdown = hasPension && age >= fireAge;

    if (inDrawdown) {
      // Drawdown phase: grow by returns, subtract expenses, add pension if eligible
      const applyDrawdown = (
        currentNw: number,
        pensionMonthly: number,
        pensionStartAge: number
      ) => {
        if (currentNw <= 0) return 0; // portfolio depleted
        let val = currentNw * (1 + monthlyReturn) - monthlyExpenses;
        if (age >= pensionStartAge) val += pensionMonthly;
        return Math.max(0, val);
      };

      nwEarly = applyDrawdown(nwEarly, earlyPensionMonthly, earlyStartAge);
      nwNormal = applyDrawdown(nwNormal, normalPensionMonthly, normalStartAge);
      nwLate = applyDrawdown(nwLate, latePensionMonthly, lateStartAge);
      nw = nwNormal; // main line follows normal scenario
      if (nwNormal <= 0 && depletedAge === null) {
        depletedAge = Math.round(age * 10) / 10;
      }
    } else {
      // Accumulation phase
      nw = nw * (1 + monthlyReturn) + inputs.monthlyContribution;
      nwEarly = nw;
      nwNormal = nw;
      nwLate = nw;
    }

    coastNw = coastNw * (1 + monthlyReturn);

    if (m % 12 === 0) {
      const yearsOut = m / 12;
      let projMonth = currentMonth;
      let projYear = currentYear + yearsOut;
      if (projMonth > 12) {
        projMonth -= 12;
        projYear += 1;
      }

      const point: ProjectionPoint = {
        age: inputs.currentAge + yearsOut,
        year: projYear,
        month: projMonth,
        netWorth: Math.round(nw),
        coastNetWorth: Math.round(coastNw),
      };
      if (hasPension) {
        point.netWorthEarly = Math.round(nwEarly);
        point.netWorthNormal = Math.round(nwNormal);
        point.netWorthLate = Math.round(nwLate);
      }
      points.push(point);
    }
  }

  return points;
}

// ---------------------------------------------------------------------------
// Main calculation
// ---------------------------------------------------------------------------

/**
 * Calculate all FIRE metrics from inputs.
 */
export function calculateFire(inputs: FireInputs): FireResult {
  const realReturnPct = inputs.annualReturnPct - inputs.inflationPct;
  const realReturn = realReturnPct / 100;

  // Check if pension mode is active
  const hasPension = inputs.pensionAccruedMonthly !== undefined;

  let fireNumber: number;
  let pensionResult: PensionResult | undefined;

  if (hasPension) {
    const accrualRate = inputs.pensionAccrualRate ?? 1.5;
    const pensionFullAge = inputs.pensionFullAge ?? 68;
    const lifeExpectancy = inputs.lifeExpectancy ?? 95;
    const monthlySalary = inputs.pensionMonthlySalary ?? 0;

    // Use target retirement age directly as the FIRE age.
    // This eliminates the circular dependency (FIRE number ↔ FIRE age)
    // and lets the user explore scenarios by adjusting retirement age.
    const retirementAge = inputs.targetRetirementAge;

    const projectedMonthly = calcProjectedMonthlyPension(
      inputs.pensionAccruedMonthly!,
      inputs.currentAge,
      retirementAge,
      monthlySalary,
      accrualRate
    );

    // Guarantee pension (takuueläke) floor
    const guaranteeEnabled = inputs.pensionGuaranteeEnabled ?? false;
    const guaranteeAmount = inputs.pensionGuaranteeAmount ?? 990;

    const scenarios = generatePensionScenarios(
      projectedMonthly,
      pensionFullAge,
      retirementAge,
      inputs.annualExpenses,
      lifeExpectancy,
      realReturn
    );

    // Apply guarantee floor to each scenario's pension
    if (guaranteeEnabled) {
      for (const scenario of scenarios) {
        if (scenario.monthlyPension < guaranteeAmount) {
          scenario.monthlyPension = guaranteeAmount;
          scenario.annualPension = guaranteeAmount * 12;
          scenario.pensionFireNumber = calcPensionFireNumber(
            inputs.annualExpenses,
            scenario.annualPension,
            retirementAge,
            scenario.pensionStartAge,
            lifeExpectancy,
            realReturn
          );
        }
      }
    }

    fireNumber = Math.round(scenarios[1].pensionFireNumber);

    const pensionCoastFireNumber = calcCoastFireNumber(
      fireNumber,
      realReturnPct,
      Math.max(0, retirementAge - inputs.currentAge)
    );

    const crossoverAge = guaranteeEnabled
      ? calcGuaranteeCrossoverAge(
          inputs.pensionAccruedMonthly!,
          inputs.currentAge,
          monthlySalary,
          accrualRate,
          guaranteeAmount,
          pensionFullAge + 3
        )
      : null;

    pensionResult = {
      projectedMonthlyPension: projectedMonthly,
      scenarios,
      pensionCoastFireNumber: Math.round(pensionCoastFireNumber),
      guaranteeActive: guaranteeEnabled && projectedMonthly < guaranteeAmount,
      guaranteeAmount,
      crossoverAge,
    };
  } else {
    fireNumber = Math.round(calcFireNumber(inputs.annualExpenses, inputs.safeWithdrawalRate));
  }

  const yearsToRetirement = Math.max(0, inputs.targetRetirementAge - inputs.currentAge);
  const coastFireNumber = hasPension
    ? pensionResult!.pensionCoastFireNumber
    : Math.round(calcCoastFireNumber(fireNumber, realReturnPct, yearsToRetirement));
  const coastFireReached = inputs.currentNetWorth >= coastFireNumber;

  const yearsToFire = calcYearsToFire(
    inputs.currentNetWorth,
    inputs.monthlyContribution,
    fireNumber,
    realReturnPct
  );

  const fireAge = yearsToFire !== null ? Math.round((inputs.currentAge + yearsToFire) * 10) / 10 : null;

  // Calculate Coast FIRE age: the age at which your NW (with contributions)
  // can compound to the FIRE number without further savings by retirement.
  const coastFireAge = coastFireReached
    ? inputs.currentAge
    : calcCoastFireAge(
        inputs.currentNetWorth,
        inputs.monthlyContribution,
        fireNumber,
        realReturnPct,
        inputs.currentAge,
        inputs.targetRetirementAge
      );

  // Generate projections — extend to life expectancy when pension is active
  const lifeExpectancy = inputs.lifeExpectancy ?? 95;
  const defaultProjectionYears = Math.min(
    Math.max(yearsToRetirement + 10, yearsToFire ? Math.ceil(yearsToFire) + 5 : 40),
    60
  );
  const projectionYears = hasPension
    ? Math.max(lifeExpectancy - inputs.currentAge + 2, defaultProjectionYears)
    : defaultProjectionYears;
  const projections = generateProjections(inputs, projectionYears, pensionResult);

  // Find when portfolio depletes (normal scenario hits 0)
  const depletedPoint = hasPension
    ? projections.find(
        (p) =>
          p.age > inputs.targetRetirementAge &&
          p.netWorthNormal !== undefined &&
          p.netWorthNormal <= 0
      )
    : null;
  const portfolioDepletedAge = depletedPoint?.age ?? null;

  return {
    fireNumber,
    coastFireNumber,
    coastFireReached,
    yearsToFire: yearsToFire !== null ? Math.round(yearsToFire * 10) / 10 : null,
    fireAge,
    coastFireAge,
    onTrack: yearsToFire !== null && yearsToFire <= yearsToRetirement,
    portfolioDepletedAge,
    projections,
    pension: pensionResult,
  };
}
