import { Page } from "@playwright/test";
import { test, expect, eur, RUN } from "./fixtures";

interface Budget {
  totals: { cash_balance: number; current_balance: number };
  expenses: { id: number; name: string }[];
  archived_expenses: { id: number; name: string }[];
}

async function expandExpenses(page: Page) {
  const expenses = page.locator("section", {
    has: page.getByRole("button", { name: "Expenses", exact: true }),
  });
  await expenses.getByRole("button", { name: "Expenses", exact: true }).click();
  // A monthly expense lands in this month or the next, depending on the date.
  for (const title of ["This month", "Next month"]) {
    await expenses.getByRole("button", { name: title }).click();
  }
}

test("budget page shows totals from seeded data", async ({ page, api }) => {
  await api.seed("/api/accounts", {
    name: `${RUN} checking`,
    balance: 1234.56,
    is_credit: false,
  });
  // Figures come from the API so the check also holds on a non-empty database;
  // what is under test is that the page renders them.
  const { totals } = await api.get<Budget>("/api/budget/current");

  await page.goto("/");

  const summary = page.locator("section", {
    has: page.getByRole("button", { name: "You have now" }),
  });
  // Check the header total and the Cash row separately: with no card debt the
  // two figures are equal, and one must not be able to vouch for the other.
  await expect(summary.locator(":scope > div").first()).toContainText(
    eur(totals.current_balance)
  );
  const cashRow = summary.getByText("Cash", { exact: true }).locator("..");
  await expect(cashRow).toContainText(eur(totals.cash_balance));
});

test("adds a budget line in the UI and archives it", async ({ page, api }) => {
  const name = `${RUN} rent`;
  await page.goto("/");

  await page.getByRole("button", { name: "Add Expense" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Name").fill(name);
  await dialog.getByLabel("Amount (€)").fill("42.50");
  await dialog.getByLabel("Due Day (of month)").fill("15");
  await dialog.getByRole("button", { name: "Create" }).click();
  await expect(page.getByText("Expense created", { exact: true })).toBeVisible();

  const created = (await api.get<Budget>("/api/budget/current")).expenses.find(
    (e) => e.name === name
  );
  expect(created).toBeDefined();
  const path = `/api/expenses/${created!.id}`;
  api.track(path);

  await expandExpenses(page);
  // It recurs, so it is listed under both months.
  await expect(page.getByText(name).first()).toBeVisible();

  await api.put(path, { archived_at: new Date().toISOString() });
  await page.reload();
  await expandExpenses(page);
  await expect(page.getByText(name)).toHaveCount(0);

  const budget = await api.get<Budget>("/api/budget/current");
  expect(budget.archived_expenses.map((e) => e.name)).toContain(name);
});
