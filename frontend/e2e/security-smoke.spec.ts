import { test, expect } from "@playwright/test";

test.beforeEach(async ({ context }) => {
  // Our app only. Never operate Clerk or external job sites with these tests.
  await context.route("**/*", route => {
    const url = new URL(route.request().url());
    return url.hostname === "127.0.0.1" || url.hostname === "localhost" ? route.continue() : route.abort();
  });
});

for (const route of ["/dashboard", "/onboarding", "/jobs", "/applications", "/resumes", "/settings"]) {
  test(`signed-out users cannot view ${route}`, async ({ page }) => {
    await page.goto(route);
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole("heading", { name: "Sign in to InternAgent" })).toBeVisible();
    await page.reload();
    await expect(page).toHaveURL(/\/login$/);
  });
}

for (const width of [375, 768, 1440]) {
  test(`login remains usable at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: "Sign in to InternAgent" })).toBeVisible();
    await expect(page.getByRole("status")).toContainText("authentication is configured");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
}

test("unconfigured proxy refuses access without leaking a token", async ({ request }) => {
  const response = await request.get("/api/backend/users/me");
  expect(response.status()).toBe(503);
  expect(await response.text()).not.toMatch(/sk_live_|sk_test_|postgresql:\/\//);
});

test("signup has a truthful missing-configuration notice rather than fake signup", async ({ page }) => {
  await page.goto("/sign-up");
  await expect(page.getByText("Account creation is awaiting workspace configuration.")).toBeVisible();
});

test("backend independently requires authentication", async ({ request }) => {
  const response = await request.get("http://127.0.0.1:8100/api/v1/resumes");
  expect(response.status()).toBe(401);
  expect(await response.text()).not.toContain("traceback");
});
