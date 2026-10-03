import { test as base, expect, APIRequestContext } from "@playwright/test";

const API_URL = process.env.E2E_API_URL ?? "http://localhost:5000";

// Every record the suite creates carries this run's marker so it can be found
// again, and so a leftover from a crashed run never collides with the next one.
export const RUN = `e2e-${Date.now().toString(36)}`;

export interface Api {
  request: APIRequestContext;
  /** POST a synthetic record; it is deleted again when the test ends. */
  seed: <T extends { id: number }>(
    path: string,
    data: Record<string, unknown>
  ) => Promise<T>;
  /** Run this when the test ends, even if it failed (for records the UI creates). */
  defer: (cleanup: () => Promise<void>) => void;
  get: <T>(path: string) => Promise<T>;
  put: (path: string, data: Record<string, unknown>) => Promise<void>;
}

export const test = base.extend<{ api: Api }>({
  // The production frontend image rewrites /api to a backend address fixed at
  // build time, which only resolves under a reverse proxy. Send the browser's
  // API calls straight to the backend so the same suite works in every stack.
  page: async ({ page }, provide) => {
    await page.route("**/api/**", async (route) => {
      const { pathname, search } = new URL(route.request().url());
      const response = await route.fetch({
        url: `${API_URL}${pathname}${search}`,
      });
      await route.fulfill({ response });
    });
    await provide(page);
  },

  api: async ({ playwright }, provide) => {
    const request = await playwright.request.newContext({ baseURL: API_URL });
    const cleanups: (() => Promise<void>)[] = [];
    const api: Api = {
      request,
      seed: async (path, data) => {
        const response = await request.post(path, { data });
        expect(response.status(), `POST ${path}`).toBe(201);
        const item = await response.json();
        cleanups.push(async () => {
          await request.delete(`${path}/${item.id}`);
        });
        return item;
      },
      defer: (cleanup) => {
        cleanups.push(cleanup);
      },
      get: async (path) => {
        const response = await request.get(path);
        expect(response.ok(), `GET ${path}`).toBeTruthy();
        return response.json();
      },
      put: async (path, data) => {
        const response = await request.put(path, { data });
        expect(response.ok(), `PUT ${path}`).toBeTruthy();
      },
    };
    await provide(api);
    // Newest first, so a category goes before the group that owns it. One
    // failed cleanup must not leave the rest of the test data behind.
    const errors: unknown[] = [];
    for (const cleanup of cleanups.reverse()) {
      await cleanup().catch((error) => errors.push(error));
    }
    await request.dispose();
    if (errors.length) throw errors[0];
  },
});

export { expect };

/** Mirrors formatCurrency in lib/utils.ts, which the pages render with. */
export function eur(value: number, decimals = 2): string {
  const formatted = new Intl.NumberFormat("fi-FI", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(decimals === 0 ? Math.round(value) : value);
  return `${formatted} €`.replace(/\s/g, " ");
}
