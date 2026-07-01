import { expect, test } from "@playwright/test";
import { readCareToolsCredentials } from "./care-tools.setup";

const { email, password } = readCareToolsCredentials();

async function login(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.getByLabel("Correo").fill(email);
  await page.getByLabel("Contraseña").fill(password);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await page.waitForURL(/\/home/);
}

test.describe("care tools (deterministic)", () => {
  test.describe.configure({ mode: "serial" });

  test("/reminders loads the seeded plant and reminders", async ({ page }) => {
    await login(page);
    await page.goto("/reminders");

    await expect(page.getByRole("heading", { name: "Recordatorios", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Lista de Recordatorios Actuales" })).toBeVisible();
    await expect(page.getByText("2 activos")).toBeVisible();
    await expect(page.getByLabel("Planta")).toHaveValue(/.+/);
    await expect(
      page.locator('[aria-label="Tarea"]').filter({ hasText: "Riego" }),
    ).toBeVisible();
    await expect(
      page.locator('[aria-label="Tarea"]').filter({ hasText: "Fertilizante" }),
    ).toBeVisible();
  });

  test("/reminders row action trigger is visible by default and opens the menu", async ({ page }) => {
    await login(page);
    await page.goto("/reminders");

    const trigger = page.getByRole("button", { name: "Abrir acciones del recordatorio" }).first();
    await expect(trigger).toBeVisible();
    const opacity = await trigger.evaluate((el) => Number(getComputedStyle(el).opacity));
    expect(opacity).toBeGreaterThan(0.9);

    await trigger.click();
    await expect(page.getByRole("menuitem", { name: "Editar" })).toBeVisible();
    await expect(page.getByRole("menuitem", { name: "Completar" })).toBeVisible();
    await expect(page.getByRole("menuitem", { name: "Eliminar" })).toBeVisible();
  });

  test("/reminders form creates a new reminder and the list updates", async ({ page }) => {
    await login(page);
    await page.goto("/reminders");

    await expect(page.getByLabel("Planta")).toHaveValue(/.+/);
    await page.getByLabel(/^Tipo de Tarea/).selectOption("Fertilizante");
    await page.getByLabel(/^Fecha/).fill("2999-01-20");
    await page.getByLabel(/^Hora/).fill("10:30");
    await page.getByRole("button", { name: "Guardar recordatorio" }).click();

    await expect(page.getByText("Recordatorio guardado.")).toBeVisible();
    await expect(page.getByText("3 activos")).toBeVisible();
  });

  test("/light-meter manual reading is visible and save is enabled", async ({ page }) => {
    await login(page);
    await page.goto("/light-meter");

    await expect(page.getByRole("heading", { name: "Medidor de luz" })).toBeVisible();

    await page.getByLabel("Condicion observada").selectOption("alta");
    await page.getByRole("button", { name: "Usar registro manual" }).click();

    await expect(page.getByRole("heading", { name: "Luz alta" })).toBeVisible();

    const save = page.getByRole("button", { name: "Guardar medicion" });
    await expect(save).toBeEnabled();
    await save.click();

    await expect(page.getByText("Medicion guardada correctamente.")).toBeVisible();
  });
});
