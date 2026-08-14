import { defineConfig, devices } from "@playwright/test";

const externalServer = process.env.PLAYWRIGHT_EXTERNAL_SERVER === "1";

export default defineConfig({
  testDir: "./e2e",
  testIgnore: ["**/seed_*.py", "**/*.setup.ts", "**/auth-home.spec.ts"],
  workers: process.env.CI ? 1 : undefined,
  use: {
    baseURL: "http://localhost:3000",
    ...devices["Desktop Chrome"],
    trace: "on-first-retry",
  },
  webServer: externalServer
    ? undefined
    : {
        command: "pnpm dev",
        url: "http://localhost:3000",
        reuseExistingServer: false,
        timeout: 120_000,
      },
});
