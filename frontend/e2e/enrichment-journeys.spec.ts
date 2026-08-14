import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

test.describe.configure({
  mode: "serial",
  timeout: 90_000,
});

test.beforeEach(async ({ page }) => {
  const email = `enrich-${Date.now()}-${Math.random().toString(16).slice(2)}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Nombre").fill("Enrich E2E");
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

async function openConfirmedProfile(page: Page) {
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
}

test("confirmed plant schedules enrichment and profile remains navigable", async ({ page }) => {
  await openConfirmedProfile(page);

  await expect(page.getByRole("status")).toContainText(
    /Evidencia completa|Evidencia parcial|No se pudo ampliar la evidencia/i,
    { timeout: 60000 },
  );

  await expect(page.getByText("Perfil botanico guardado")).toBeVisible();
});

test("the assistant link is keyboard reachable and carries full plant context", async ({ page }) => {
  await openConfirmedProfile(page);

  const assistantLink = page.getByRole("link", {
    name: "Preguntar al asistente",
  });

  const href = await assistantLink.getAttribute("href");
  expect(href).not.toBeNull();

  const assistantUrl = new URL(href!, page.url());
  expect(assistantUrl.searchParams.get("plant")).toBeTruthy();
  expect(assistantUrl.searchParams.get("binomial")).toBeTruthy();
  expect(assistantUrl.searchParams.get("scientific")).toBeTruthy();
  expect(assistantUrl.searchParams.get("candidate")).toBeTruthy();

  await assistantLink.focus();
  await expect(assistantLink).toBeFocused();
  await assistantLink.press("Enter");

  await expect(page).toHaveURL(/\/assistant\?/);
});

test("the active enrichment profile has no serious or critical automated accessibility violations", async ({ page }) => {
  // Deterministically arrange the pending/processing state so the scanned
  // DOM is stable, regardless of how fast the real backend job advances.
  // Terminal states (complete, partial, failed, stalled) are covered by
  // dedicated component tests and are not claimed to be scanned here.
  await page.route(
    "**/api/identifications/candidates/*/enrichment",
    async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          candidate_id: "00000000-0000-4000-8000-000000000001",
          policy_version: 1,
          job: {
            id: "00000000-0000-4000-8000-000000000002",
            job_type: "enrich_confirmed_plant",
            status: "processing",
            attempt_count: 1,
            max_attempts: 3,
            created_at: "2026-08-13T00:00:00Z",
            updated_at: "2026-08-13T00:00:00Z",
            completed_at: null,
            result: null,
            last_error: null,
          },
        }),
      });
    },
  );

  await openConfirmedProfile(page);

  await expect(page.getByRole("status")).toContainText("Buscando evidencia");
  await expect(page.getByText("Perfil botanico guardado")).toBeVisible();

  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();

  const seriousOrCritical = results.violations.filter((violation) =>
    ["serious", "critical"].includes(violation.impact ?? ""),
  );
  expect(seriousOrCritical).toEqual([]);
});
