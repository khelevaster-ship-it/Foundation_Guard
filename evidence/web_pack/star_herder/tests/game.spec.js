import { test, expect } from "@playwright/test";

test.describe("in the browser", () => {
  test("game_draws_frames", async ({ page }) => {
    await page.goto("/");
    await expect.poll(() => page.evaluate(() => window.__frames || 0)).toBeGreaterThan(10);
  });
});
