import { defineConfig, devices } from "@playwright/test";
const port = process.env.E2E_PORT ?? "3000";
export default defineConfig({
  testDir: "./tests/e2e",
  workers: 1,
  reporter: "line",
  use: { baseURL: `http://localhost:${port}`, trace: "on-first-retry" },
  webServer: {
    command: "node .next/standalone/server.js",
    url: `http://localhost:${port}`,
    reuseExistingServer: true,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
