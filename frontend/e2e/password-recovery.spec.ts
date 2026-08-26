import { expect, test } from "@playwright/test";

const STUB_PORT = Number(process.env.AUTH_STUB_PORT ?? 8099);
const STUB_URL = `http://127.0.0.1:${STUB_PORT}`;
const SEED_EMAIL = "e2e-auth@example.com";
const OLD_PASSWORD = "password123";
const NEW_PASSWORD = "newpassword456";

test.beforeEach(async ({ request }) => {
  const response = await request.post(`${STUB_URL}/__test__/reset`);
  expect(response.ok()).toBeTruthy();
});

test("request, reset, re-login with new password, and old-password failure", async ({
  page,
  request,
}) => {
  // Request a recovery link for the seeded account.
  await page.goto("/forgot-password");
  await page.getByLabel("Correo").fill(SEED_EMAIL);
  await page.getByRole("button", { name: "Recuperar acceso" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: /Si el correo existe/i }),
  ).toBeVisible();

  // Retrieve the generated token from the stub state.
  const state = await (await request.get(`${STUB_URL}/__test__/state`)).json();
  const recoveryTokens = state.recoveryTokens.filter(
    (entry: { email: string }) => entry.email === SEED_EMAIL,
  );
  expect(recoveryTokens).toHaveLength(1);
  const token = recoveryTokens[0].token as string;
  expect(typeof token).toBe("string");
  expect(token.length).toBeGreaterThan(0);

  // Open the reset route with the token; the token must not be shown in copy.
  await page.goto(`/reset-password?token=${token}`);
  await expect(
    page.getByRole("heading", { name: /Crear una contraseña nueva/i }),
  ).toBeVisible();
  await expect(page.getByText(token)).toHaveCount(0);

  // Set and confirm the new password.
  await page.getByLabel("Nueva contraseña").fill(NEW_PASSWORD);
  await page.getByLabel("Confirmar contraseña").fill(NEW_PASSWORD);
  await page.getByRole("button", { name: "Actualizar contraseña" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: /Si el enlace era válido/i }),
  ).toBeVisible();

  // Log in with the new password succeeds.
  await page.goto("/login");
  await page.getByLabel("Correo").fill(SEED_EMAIL);
  await page.getByLabel("Contraseña").fill(NEW_PASSWORD);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page).toHaveURL(/\/home/);
  await expect(page.getByText(/Hola, E2E User/)).toBeVisible();

  // Log out, then the old password must fail and keep the user on login.
  await page.getByRole("button", { name: "Cerrar sesión" }).click();
  await expect(page).toHaveURL(/\/login/);
  await page.getByLabel("Correo").fill(SEED_EMAIL);
  await page.getByLabel("Contraseña").fill(OLD_PASSWORD);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page).not.toHaveURL(/\/home/);
  await expect(page).toHaveURL(/\/login/);
});
