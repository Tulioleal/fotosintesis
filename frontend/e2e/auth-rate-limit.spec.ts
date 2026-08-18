import { expect, test } from "@playwright/test";

const STUB_PORT = Number(process.env.AUTH_STUB_PORT ?? 8099);
const STUB_URL = `http://127.0.0.1:${STUB_PORT}`;

type Target = "authjsAdmission" | "credentialsVerification" | "registration" | "recovery";

test.beforeEach(async ({ request }) => {
  await request.post(`${STUB_URL}/__test__/reset`);
});

async function setTarget(
  request: import("@playwright/test").APIRequestContext,
  target: Target,
  status: number,
  retryAfterSeconds: number,
) {
  const response = await request.post(`${STUB_URL}/__test__/ratelimit`, {
    data: { target, status, retryAfterSeconds },
  });
  expect(response.ok()).toBeTruthy();
}

const RATE_LIMITED_TEXT = /Demasiados intentos desde esta conexión/;
const UNAVAILABLE_TEXT = /temporalmente no disponible/;
const INVALID_CREDENTIALS_TEXT =
  "No pudimos iniciar sesión con esos datos. Revisalos e intentá otra vez.";

async function login(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.getByLabel("Correo").fill("e2e-auth@example.com");
  await page.getByLabel("Contraseña").fill("password123");
  await page.getByRole("button", { name: "Ingresar" }).click();
}

test("registration 429 journey: header propagation, countdown, and disabled resubmission", async ({ page, request }) => {
  await setTarget(request, "registration", 429, 2);

  await page.goto("/register");
  await page.getByLabel("Nombre").fill("Public User");
  await page.getByLabel("Correo").fill("e2e-limited@example.com");
  await page.getByLabel("Contraseña").fill("password123");
  await page.getByRole("button", { name: "Crear cuenta" }).click();

  // Generic retry guidance is shown and the form is disabled for the server
  // duration (2 seconds).
  await expect(page.getByText(RATE_LIMITED_TEXT)).toBeVisible();
  await expect(page.getByRole("button", { name: "Crear cuenta" })).toBeDisabled();

  // After the clamped server interval elapses the form re-enables.
  await expect(page.getByRole("button", { name: "Crear cuenta" })).toBeEnabled({
    timeout: 5_000,
  });
});

test("Auth.js wrapper 429 blocks before the credentials provider", async ({ page, request }) => {
  await setTarget(request, "authjsAdmission", 429, 2);

  await login(page);

  await expect(page.getByText(RATE_LIMITED_TEXT)).toBeVisible();
  await expect(page.getByRole("button", { name: "Ingresar" })).toBeDisabled();

  await expect(page.getByRole("button", { name: "Ingresar" })).toBeEnabled({
    timeout: 5_000,
  });
});

test("Auth.js wrapper 503 displays unavailable feedback", async ({ page, request }) => {
  await setTarget(request, "authjsAdmission", 503, 2);

  await login(page);

  await expect(page.getByText(UNAVAILABLE_TEXT)).toBeVisible();
  await expect(page.getByText(RATE_LIMITED_TEXT)).not.toBeVisible();
  await expect(page.getByRole("button", { name: "Ingresar" })).toBeDisabled();

  await expect(page.getByRole("button", { name: "Ingresar" })).toBeEnabled({
    timeout: 5_000,
  });
});

test("Auth.js admission succeeds but the credentials backend 429 reaches the real error path", async ({ page, request }) => {
  await setTarget(request, "authjsAdmission", 200, 2);
  await setTarget(request, "credentialsVerification", 429, 2);

  await login(page);

  // The outer wrapper admitted the Auth.js POST; the inner credential
  // verification was rate limited and the real custom CredentialsRateLimited
  // error carried the bounded code through to the form.
  await expect(page.getByText(RATE_LIMITED_TEXT)).toBeVisible();
  await expect(page.getByRole("button", { name: "Ingresar" })).toBeDisabled();

  await expect(page.getByRole("button", { name: "Ingresar" })).toBeEnabled({
    timeout: 5_000,
  });
});

test("credentials backend 503 reaches unavailable feedback through the real path", async ({ page, request }) => {
  await setTarget(request, "authjsAdmission", 200, 2);
  await setTarget(request, "credentialsVerification", 503, 2);

  await login(page);

  await expect(page.getByText(UNAVAILABLE_TEXT)).toBeVisible();
  await expect(page.getByText(RATE_LIMITED_TEXT)).not.toBeVisible();
  await expect(page.getByRole("button", { name: "Ingresar" })).toBeDisabled();

  await expect(page.getByRole("button", { name: "Ingresar" })).toBeEnabled({
    timeout: 5_000,
  });
});

test("invalid credentials retain the neutral existing error", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Correo").fill("e2e-auth@example.com");
  await page.getByLabel("Contraseña").fill("wrong-password");
  await page.getByRole("button", { name: "Ingresar" }).click();

  // Wrong password against the seeded user returns 401; the form shows the
  // neutral invalid-credentials copy and never starts a countdown.
  await expect(page.getByText(INVALID_CREDENTIALS_TEXT)).toBeVisible();
  await expect(page.getByText(RATE_LIMITED_TEXT)).not.toBeVisible();
  await expect(page.getByRole("button", { name: "Ingresar" })).toBeEnabled();
});

test("recovery 429 journey: neutral message and disabled resubmission", async ({ page, request }) => {
  await setTarget(request, "recovery", 429, 2);

  await page.goto("/forgot-password");
  await page.getByLabel("Correo").fill("recovery@example.com");
  await page.getByRole("button", { name: "Recuperar acceso" }).click();

  // The neutral recovery message is preserved even when rate limited.
  await expect(
    page.getByRole("status").filter({ hasText: /Si el correo existe/i }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Recuperar acceso" })).toBeDisabled();

  await expect(page.getByRole("button", { name: "Recuperar acceso" })).toBeEnabled({
    timeout: 5_000,
  });
});