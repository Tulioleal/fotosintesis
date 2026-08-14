import { defineConfig, devices } from "@playwright/test";

const STUB_PORT = Number(process.env.AUTH_STUB_PORT ?? 8099);
const APP_PORT = Number(process.env.AUTH_E2E_APP_PORT ?? 3001);
const STUB_URL = `http://127.0.0.1:${STUB_PORT}`;
const APP_URL = `http://localhost:${APP_PORT}`;

export default defineConfig({
  testDir: "./e2e",
  testMatch: ["auth-home.spec.ts"],
  testIgnore: ["**/*.setup.ts"],
  workers: 1,
  fullyParallel: false,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: APP_URL,
    ...devices["Desktop Chrome"],
    trace: "on-first-retry",
  },
  webServer: [
    {
      command: `node e2e/support/auth-backend-stub.mjs`,
      url: `${STUB_URL}/health`,
      reuseExistingServer: false,
      timeout: 30_000,
      env: { AUTH_STUB_PORT: String(STUB_PORT) },
    },
    {
      command: `pnpm next dev -p ${APP_PORT}`,
      url: `${APP_URL}/login`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        API_BASE_URL: STUB_URL,
        NEXT_PUBLIC_API_BASE_URL: STUB_URL,
        AUTH_SECRET: "e2e-auth-secret-for-playwright",
        AUTH_URL: APP_URL,
        AUTH_TRUST_HOST: "true",
        NEXT_TELEMETRY_DISABLED: "1",
      },
    },
  ],
});
