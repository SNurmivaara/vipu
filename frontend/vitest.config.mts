import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL(".", import.meta.url)) },
  },
  test: {
    environment: "jsdom",
    include: ["**/*.test.{ts,tsx}"],
    exclude: ["e2e/**", "node_modules/**", ".next/**"],
    setupFiles: ["./vitest.setup.ts"],
    // Date helpers read local time; pin it so results match on every machine.
    env: { TZ: "UTC" },
    coverage: {
      include: ["app/**", "components/**", "hooks/**", "lib/**"],
    },
  },
});
