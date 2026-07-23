import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  const email = `enrich-${Date.now()}-${Math.random().toString(16).slice(2)}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Nombre").fill("Enrich E2E");
  await page.getByLabel("Correo").fill(email);
  await page.getByLabel("Contraseña").fill("password123");
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await page.waitForURL(/\/login/);
  await page.getByLabel("Correo").fill(email);
  await page.getByLabel("Contraseña").fill("password123");
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page).toHaveURL(/\/home/);
});

test("confirmed plant schedules enrichment and profile remains navigable", async ({ page }) => {
  await page.goto("/identify");
  await page.setInputFiles('input[accept="image/jpeg,image/png,image/webp"]', {
    name: "plant.jpg",
    mimeType: "image/jpeg",
    buffer: Buffer.from("fake-image"),
  });

  await expect(page.getByRole("heading", { name: "Pata de oso" })).toBeVisible();

  await page.getByRole("button", { name: "Seleccionar esta planta" }).click();

  await expect(page).toHaveURL(/\/profiles\/.*\?candidateId=/);

  await expect(page.getByText("Perfil botanico guardado")).toBeVisible();

  await expect(page.getByText(/Estado de la evidencia/i)).toBeVisible({ timeout: 15000 });

  await expect(page.getByText(/completo|parcial|fallido/i)).toBeVisible({ timeout: 60000 });

  await expect(page.getByText("Perfil botanico guardado")).toBeVisible();
});
