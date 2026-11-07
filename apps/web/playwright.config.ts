import { defineConfig, devices } from "@playwright/test";

const PORT = 3100;

// Serves the production build, so it needs `pnpm build` first.
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  // A real case runs through search and the model, so give it time.
  timeout: process.env.E2E_REAL ? 240_000 : 30_000,
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `pnpm exec next start --port ${PORT}`,
    port: PORT,
    reuseExistingServer: !process.env.CI,
  },
});
