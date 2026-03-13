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
}

export interface FireResult {
  fireNumber: number;
  coastFireNumber: number;
  coastFireReached: boolean;
  yearsToFire: number | null; // null if unreachable
  fireAge: number | null;
  coastFireAge: number | null; // age when Coast FIRE was/will be reached
  projections: ProjectionPoint[];
}

export interface ProjectionPoint {
  age: number;
  year: number;
  month: number;
  netWorth: number;
  // Net worth if you stopped saving (coast scenario)
  coastNetWorth: number;
}

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
 * Generate month-by-month projections for net worth growth.
 * Includes both "saving" scenario and "coast" scenario (no further contributions).
 */
export function generateProjections(
  inputs: FireInputs,
  yearsAhead: number = 40
): ProjectionPoint[] {
  const realReturnPct = inputs.annualReturnPct - inputs.inflationPct;
  const monthlyReturn = Math.pow(1 + realReturnPct / 100, 1 / 12) - 1;
  const totalMonths = yearsAhead * 12;
  const currentYear = new Date().getFullYear();
  const currentMonth = new Date().getMonth() + 1;

  const points: ProjectionPoint[] = [];

  let nw = inputs.currentNetWorth;
  let coastNw = inputs.currentNetWorth;

  // Add starting point
  points.push({
    age: inputs.currentAge,
    year: currentYear,
    month: currentMonth,
    netWorth: nw,
    coastNetWorth: coastNw,
  });

  for (let m = 1; m <= totalMonths; m++) {
    nw = nw * (1 + monthlyReturn) + inputs.monthlyContribution;
    coastNw = coastNw * (1 + monthlyReturn); // no contributions

    // Only store yearly points (every 12 months) to keep data manageable
    if (m % 12 === 0) {
      const yearsOut = m / 12;
      let projMonth = currentMonth;
      let projYear = currentYear + yearsOut;

      // Adjust for mid-year start
      if (projMonth > 12) {
        projMonth -= 12;
        projYear += 1;
      }

      points.push({
        age: inputs.currentAge + yearsOut,
        year: projYear,
        month: projMonth,
        netWorth: Math.round(nw),
        coastNetWorth: Math.round(coastNw),
      });
    }
  }

  return points;
}

/**
 * Calculate all FIRE metrics from inputs.
 */
export function calculateFire(inputs: FireInputs): FireResult {
  const realReturnPct = inputs.annualReturnPct - inputs.inflationPct;
  const fireNumber = calcFireNumber(inputs.annualExpenses, inputs.safeWithdrawalRate);
  const yearsToRetirement = Math.max(0, inputs.targetRetirementAge - inputs.currentAge);
  const coastFireNumber = calcCoastFireNumber(fireNumber, realReturnPct, yearsToRetirement);
  const coastFireReached = inputs.currentNetWorth >= coastFireNumber;

  const yearsToFire = calcYearsToFire(
    inputs.currentNetWorth,
    inputs.monthlyContribution,
    fireNumber,
    realReturnPct
  );

  const fireAge = yearsToFire !== null ? Math.round((inputs.currentAge + yearsToFire) * 10) / 10 : null;

  // Calculate Coast FIRE age: when does NW with contributions reach coastFireNumber?
  // (This is the age at which you could stop saving)
  let coastFireAge: number | null = null;
  if (coastFireReached) {
    coastFireAge = inputs.currentAge;
  } else {
    const yearsToCoast = calcYearsToFire(
      inputs.currentNetWorth,
      inputs.monthlyContribution,
      coastFireNumber,
      realReturnPct
    );
    if (yearsToCoast !== null) {
      coastFireAge = Math.round((inputs.currentAge + yearsToCoast) * 10) / 10;
    }
  }

  // Generate projections spanning until FIRE or 40 years, whichever is longer
  const projectionYears = Math.min(
    Math.max(yearsToRetirement + 10, yearsToFire ? Math.ceil(yearsToFire) + 5 : 40),
    60
  );
  const projections = generateProjections(inputs, projectionYears);

  return {
    fireNumber: Math.round(fireNumber),
    coastFireNumber: Math.round(coastFireNumber),
    coastFireReached,
    yearsToFire: yearsToFire !== null ? Math.round(yearsToFire * 10) / 10 : null,
    fireAge,
    coastFireAge,
    projections,
  };
}
