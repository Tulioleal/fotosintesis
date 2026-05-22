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
