import { expect, test } from "@playwright/test";
test("user can sign in with demo credentials", async ({ page }) => {
  await page.goto("/login");
  await page.waitForTimeout(750);
  await page.getByLabel("Work email").fill("owner@orionmedia.com");
  await page.getByLabel("Password").fill("Password123!");
  await page.getByRole("button", { name: /sign in to creditflow/i }).click();
  await expect(page).toHaveURL(/dashboard/);
  await expect(page.getByRole("heading", { name: /workspace overview/i })).toBeVisible();
});
