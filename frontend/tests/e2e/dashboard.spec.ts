import { expect, test } from "@playwright/test";
test("dashboard navigation reaches content library", async ({ page }) => {
  await page.goto("/login");
  await page.waitForTimeout(750);
  await page.getByLabel("Work email").fill("owner@orionmedia.com");
  await page.getByLabel("Password").fill("Password123!");
  await page.getByRole("button", { name: /sign in to creditflow/i }).click();
  await page.getByRole("link", { name: "Content" }).click();
  await expect(page).toHaveURL(/content/);
  await expect(page.getByRole("heading", { name: "Content library" })).toBeVisible();
});
