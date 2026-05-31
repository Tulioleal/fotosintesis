import { expect, test } from "@playwright/test";

test("unauthenticated private route redirects to login", async ({ page }) => {
  await page.goto("/home");
  await expect(page).toHaveURL(/\/login/);
});

test("welcome links to auth routes", async ({ page }) => {
  await page.goto("/welcome");
  await expect(page.getByRole("link", { name: "Crear cuenta" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Ingresar" })).toBeVisible();
});

test("auth flow reaches Home navigation on the local stack", async ({ page }) => {
  const email = `e2e-${Date.now()}@example.com`;

  await page.goto("/register");
  await page.getByLabel("Nombre").fill("E2E User");
  await page.getByLabel("Correo").fill(email);
  await page.getByLabel("Contraseña").fill("password123");
  await page.getByRole("button", { name: "Crear cuenta" }).click();

  await expect(page).toHaveURL(/\/login\?registered=1/);
  await page.getByLabel("Correo").fill(email);
  await page.getByLabel("Contraseña").fill("password123");
  await page.getByRole("button", { name: "Ingresar" }).click();

  await expect(page).toHaveURL(/\/home/);
  await expect(page.getByRole("link", { name: "Identificar planta" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Mi Jardín" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Asistente" })).toBeVisible();
});
