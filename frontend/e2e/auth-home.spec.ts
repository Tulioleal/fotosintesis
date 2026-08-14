import { expect, test } from "@playwright/test";

const STUB_PORT = Number(process.env.AUTH_STUB_PORT ?? 8099);
const STUB_URL = `http://127.0.0.1:${STUB_PORT}`;
const SEED_EMAIL = "e2e-auth@example.com";
const SEED_PASSWORD = "password123";

test.beforeEach(async ({ request }) => {
  const response = await request.post(`${STUB_URL}/__test__/reset`);
  expect(response.ok()).toBeTruthy();
});

test("unauthenticated private route redirects to login with callback URL", async ({ page }) => {
  await page.goto("/home?tab=garden");
  await expect(page).toHaveURL(/\/login\?callbackUrl=%2Fhome%3Ftab%3Dgarden/);
});

test("landing page presents the Fotosíntesis entry CTAs", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /Tu asistente personal para el cuidado de plantas/i }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Iniciar sesión" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Registrarse" }),
  ).toBeVisible();
});

test("welcome links to auth routes", async ({ page }) => {
  await page.goto("/welcome");
  await expect(page.getByRole("link", { name: "Crear cuenta" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Ingresar" })).toBeVisible();
});

test("login page keeps the social login action disabled as a visual placeholder", async ({ page }) => {
  await page.goto("/login");
  const social = page.getByRole("button", {
    name: /Continuar con Google próximamente/i,
  });
  await expect(social).toBeDisabled();
});

test("registration to login success notice flow works against the deterministic stack", async ({ page }) => {
  const email = `e2e-registered-${Date.now()}@example.com`;

  await page.goto("/register");
  await page.getByLabel("Nombre").fill("Public User");
  await page.getByLabel("Correo").fill(email);
  await page.getByLabel("Contraseña").fill("password123");
  await page.getByRole("button", { name: "Crear cuenta" }).click();

  await expect(page).toHaveURL(/\/login\?registered=1/);
  await expect(
    page.getByText("Cuenta creada. Ya podés iniciar sesión."),
  ).toBeVisible();
  await page.getByLabel("Correo").fill(email);
  await page.getByLabel("Contraseña").fill("password123");
  await page.getByRole("button", { name: "Ingresar" }).click();

  await expect(page).toHaveURL(/\/home/);
  await expect(page.getByText(/Hola, Public User/)).toBeVisible();
});

test("recovery form shows the neutral confirmation after submission", async ({ page }) => {
  await page.goto("/forgot-password");
  await page.getByLabel("Correo").fill("recovery@example.com");
  await page.getByRole("button", { name: "Recuperar acceso" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: /Si el correo existe/i }),
  ).toBeVisible();
});

test("private callback login, safe browser session, logout, and denial journey", async ({ page, request }) => {
  await page.goto("/home?tab=garden");
  await expect(page).toHaveURL(/\/login\?callbackUrl=%2Fhome%3Ftab%3Dgarden/);

  await page.getByLabel("Correo").fill(SEED_EMAIL);
  await page.getByLabel("Contraseña").fill(SEED_PASSWORD);
  await page.getByRole("button", { name: "Ingresar" }).click();

  await expect(page).toHaveURL(/\/home\?tab=garden/);

  await expect(page.getByText(/Hola, E2E User/)).toBeVisible();

  const stateBefore = await (await request.get(`${STUB_URL}/__test__/state`)).json();
  expect(stateBefore.activeSessions).toHaveLength(1);
  const backendToken = stateBefore.activeSessions[0].token;
  expect(typeof backendToken).toBe("string");
  expect(backendToken.length).toBeGreaterThan(0);

  const sessionResponse = await page.request.get("/api/auth/session");
  expect(sessionResponse.ok()).toBeTruthy();
  const session = await sessionResponse.json();
  expect(session.user.id).toBeTruthy();
  expect(session.user.name).toBe("E2E User");
  expect(session.user.email).toBe(SEED_EMAIL);
  expect(session.user.email_verified).toBe(true);
  const serializedSession = JSON.stringify(session);
  expect(serializedSession).not.toContain(backendToken);
  expect(serializedSession).not.toContain("backendCredential");
  expect(serializedSession).not.toContain("backend_session_token");
  expect(serializedSession).not.toContain("sessionExpiresAt");
  expect(serializedSession).not.toContain("session_expires_at");

  await page.getByRole("button", { name: "Cerrar sesión" }).click();
  await expect(page).toHaveURL(/\/login/);

  await expect
    .poll(
      async () => {
        const stateResponse = await request.get(`${STUB_URL}/__test__/state`);
        const state = await stateResponse.json();
        const exactLogoutEvent = state.logoutEvents.some((event: { token: string }) => event.token === backendToken);
        const stillActive = state.activeSessions.some((sessionEntry: { token: string }) => sessionEntry.token === backendToken);
        return exactLogoutEvent && !stillActive;
      },
      { timeout: 15_000 },
    )
    .toBe(true);

  const afterLogout = await page.request.get("/api/auth/session");
  const afterBody = await afterLogout.text();
  const afterSession = afterBody ? JSON.parse(afterBody) : null;
  expect(afterSession?.user).toBeUndefined();

  await page.goto("/garden");
  await expect(page).toHaveURL(/\/login\?callbackUrl=%2Fgarden/);
});
