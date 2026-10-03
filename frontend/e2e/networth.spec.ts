import { test, expect, eur, RUN } from "./fixtures";

test("net worth page loads with a recorded snapshot", async ({ page, api }) => {
  const group = await api.seed<{ id: number }>("/api/networth/groups", {
    name: `${RUN} cash`,
    group_type: "asset",
  });
  const category = await api.seed<{ id: number }>("/api/networth/categories", {
    name: `${RUN} savings`,
    group_id: group.id,
  });
  // A year no real snapshot uses, so the seed cannot collide with user data.
  await api.seed("/api/networth", {
    year: 1999,
    month: 1,
    entries: [{ category_id: category.id, amount: 5432.1 }],
  });

  await page.goto("/networth");

  await expect(page.getByRole("heading", { name: "Wealth" })).toBeVisible();
  await expect(
    page.getByText("Net Worth", { exact: true }).first()
  ).toBeVisible();
  const row = page.getByText("January 1999").locator("xpath=ancestor::div[2]");
  await expect(row).toContainText(eur(5432.1, 0));
});
