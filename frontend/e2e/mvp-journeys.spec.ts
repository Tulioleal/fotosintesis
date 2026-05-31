import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  const email = `journey-${Date.now()}-${Math.random().toString(16).slice(2)}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Nombre").fill("Journey User");
  await page.getByLabel("Correo").fill(email);
  await page.getByLabel("Contraseña").fill("password123");
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await page.getByLabel("Correo").fill(email);
  await page.getByLabel("Contraseña").fill("password123");
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page).toHaveURL(/\/home/);
});

test("identification candidate can lead to a profile", async ({ page }) => {
  await page.goto("/identify");
  await page.setInputFiles('input[accept="image/jpeg,image/png,image/webp"]', {
    name: "plant.jpg",
    mimeType: "image/jpeg",
    buffer: Buffer.from("fake-image"),
  });

  await expect(page.getByRole("heading", { name: "Pata de oso" })).toBeVisible();
  await page.getByRole("button", { name: "Confirmar candidata validada" }).click();
  await page.getByRole("link", { name: "Ver perfil y agregar a Mi Jardin" }).click();

  await expect(page.getByText("Perfil botanico trazable")).toBeVisible();
});

test("garden save and reminder creation are available from a confirmed profile", async ({ page }) => {
  await page.goto("/identify");
  await page.setInputFiles('input[accept="image/jpeg,image/png,image/webp"]', {
    name: "plant.jpg",
    mimeType: "image/jpeg",
    buffer: Buffer.from("fake-image"),
  });
  await page.getByRole("button", { name: "Confirmar candidata validada" }).click();
  await page.getByRole("link", { name: "Ver perfil y agregar a Mi Jardin" }).click();

  await page.getByPlaceholder("Nombre personalizado").fill("Pata living");
  await page.getByRole("button", { name: "Guardar planta confirmada" }).click();
  await expect(page.getByText(/Guardada en Mi Jardin/)).toBeVisible();

  await page.goto("/reminders");
  await page.getByLabel("Accion").fill("Regar");
  await page.getByLabel("Fecha").fill("2999-01-10");
  await page.getByLabel("Hora").fill("09:00");
  await page.getByRole("button", { name: "Crear recordatorio" }).click();
  await expect(page.getByText("Recordatorio guardado.")).toBeVisible();
});

test("assistant RAG and light fallback flows render", async ({ page }) => {
  await page.goto("/assistant");
  await page.getByPlaceholder("Ej: Como ajusto el riego de mi Monstera?").fill("Como debo regar mi Pata?");
  await page.getByRole("button", { name: "Enviar" }).click();
  await expect(page.getByText(/evidencia recuperada/i)).toBeVisible();

  await page.goto("/light-meter");
  await page.getByRole("button", { name: "Medir luz" }).click();
  await expect(page.getByText(/Usa registro manual|registro manual/i)).toBeVisible();
});
