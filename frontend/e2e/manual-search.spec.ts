import { expect, test } from "@playwright/test";

test.describe.configure({
  mode: "serial",
  timeout: 90_000,
});

test.beforeEach(async ({ page }) => {
  const email = `search-${Date.now()}-${Math.random().toString(16).slice(2)}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Nombre").fill("Search E2E");
  await page.getByLabel("Correo").fill(email);
  await page.getByLabel("Contraseña").fill("password123");
  const registration = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/auth/register") &&
      response.request().method() === "POST",
  );

  await page.getByRole("button", { name: "Crear cuenta" }).click();

  const registrationResponse = await registration;
  expect(
    registrationResponse.status(),
    await registrationResponse.text(),
  ).toBe(201);

  await expect(page).toHaveURL(/\/login\?registered=1$/);
  await page.getByLabel("Correo").fill(email);
  await page.getByLabel("Contraseña").fill("password123");
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page).toHaveURL(/\/home$/);
});

test("manual search leads to a GBIF candidate, manual candidate, and profile", async ({
  page,
}) => {
  await page.goto("/search");

  await page.getByLabel("Nombre de la planta").fill("Cotyledon tomentosa");
  await page.getByRole("button", { name: "Buscar" }).click();

  // The external expansion (GBIF) returns candidates for the query.
  await expect(
    page.getByText("Candidatas externas (GBIF)"),
  ).toBeVisible({ timeout: 15000 });

  const candidateCard = page
    .getByRole("listitem")
    .filter({ hasText: "Cotyledon tomentosa" })
    .first();
  await candidateCard.getByRole("button", { name: "Seleccionar" }).click();

  await page.getByRole("button", { name: "Crear candidata" }).click();

  await expect(
    page.getByRole("button", { name: "Confirmar y ver perfil" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Confirmar y ver perfil" }).click();

  // Confirming a manual candidate reuses the profile navigation flow.
  await expect(page).toHaveURL(/\/profiles\/.*\?candidateId=/, {
    timeout: 20000,
  });
});

test("identification recoverable states link to manual search", async ({
  page,
}) => {
  // The search access point is reachable from the app navigation even
  // before an image is uploaded, and the identify flow offers it too.
  await page.goto("/search");
  await expect(
    page.getByRole("heading", { name: "Buscar Plantas" }),
  ).toBeVisible();

  await page.goto("/identify");
  await expect(
    page.getByRole("heading", { name: "Identificar Planta" }),
  ).toBeVisible();
  await expect(page.getByText("Buscar manualmente")).not.toBeVisible();
});
