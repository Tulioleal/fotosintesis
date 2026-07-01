import { expect, test } from "@playwright/test";

test("unauthenticated private route redirects to login with callback URL", async ({ page }) => {
  await page.goto("/home?tab=garden");
  await expect(page).toHaveURL(/\/login\?callbackUrl=%2Fhome%3Ftab%3Dgarden/);
});

test("landing page presents the Fotosíntesis entry CTAs", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /Asistente botánico/i }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Crear cuenta gratis" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Ya tengo cuenta" }),
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

test("registration to login success notice flow works on the local stack", async ({ page }) => {
  const email = `e2e-public-${Date.now()}@example.com`;

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
  await expect(
    page.getByRole("link", { name: "Identificar planta" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Mi Jardín" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Asistente" })).toBeVisible();
});

test("recovery form shows the neutral confirmation after submission", async ({ page }) => {
  await page.goto("/forgot-password");
  await page.getByLabel("Correo").fill("recovery@example.com");
  await page.getByRole("button", { name: "Recuperar acceso" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: /Si el correo existe/i }),
  ).toBeVisible();
});
