import type { Page } from "@playwright/test";
import { test, expect, eur, RUN, type Api } from "./fixtures";

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

async function seedSnapshot(api: Api) {
  const assets = await api.seed<{ id: number }>("/api/networth/groups", {
    name: `${RUN} zero cash`,
    group_type: "asset",
  });
  const liabilities = await api.seed<{ id: number }>("/api/networth/groups", {
    name: `${RUN} zero credit`,
    group_type: "liability",
  });
  const checking = await api.seed<{ id: number }>("/api/networth/categories", {
    name: `${RUN} zero checking`,
    group_id: assets.id,
  });
  const card = await api.seed<{ id: number }>("/api/networth/categories", {
    name: `${RUN} zero card`,
    group_id: liabilities.id,
  });
  await api.seed("/api/networth", {
    year: 1999,
    month: 2,
    entries: [
      { category_id: checking.id, amount: 1000 },
      { category_id: card.id, amount: -100 },
    ],
  });
  return { checking, card };
}

async function openEdit(page: Page) {
  await page.goto("/networth");
  // The third ancestor is the history row, which holds the label and the buttons.
  const row = page.getByText("February 1999").locator("xpath=ancestor::div[3]");
  await row.getByTitle("Edit").click();
  return page.getByRole("dialog");
}

interface SnapshotDetail {
  entries: { category_id: number; amount: number }[];
}

test("net worth form saves a zero balance", async ({ page, api }) => {
  const { checking, card } = await seedSnapshot(api);

  let dialog = await openEdit(page);
  await dialog.getByLabel(`${RUN} zero card`).fill("0");
  await dialog.getByRole("button", { name: "Update" }).click();
  await expect(dialog).toBeHidden();

  const snapshot = await api.get<SnapshotDetail>("/api/networth/1999/2");
  expect(snapshot.entries).toHaveLength(2);
  expect(snapshot.entries.find((e) => e.category_id === card.id)?.amount).toBe(0);
  expect(snapshot.entries.find((e) => e.category_id === checking.id)?.amount).toBe(
    1000
  );

  dialog = await openEdit(page);
  await expect(dialog.getByLabel(`${RUN} zero card`)).toHaveValue("0");
});

test("net worth form drops a cleared field", async ({ page, api }) => {
  const { checking } = await seedSnapshot(api);

  const dialog = await openEdit(page);
  await dialog.getByLabel(`${RUN} zero card`).fill("");
  await dialog.getByRole("button", { name: "Update" }).click();
  await expect(dialog).toBeHidden();

  const snapshot = await api.get<SnapshotDetail>("/api/networth/1999/2");
  expect(snapshot.entries.map((e) => e.category_id)).toEqual([checking.id]);
});
