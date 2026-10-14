import { expect, test, type Page } from "@playwright/test";
import { clerk } from "@clerk/testing/playwright";

const emails = [process.env.QA_CLERK_USER_A, process.env.QA_CLERK_USER_B];
if (emails.some(email => !email?.includes("+clerk_test@")) || emails[0] === emails[1]) {
  throw new Error("Supply two distinct, verified +clerk_test fixture users in .env.qa.");
}

async function identity(page: Page): Promise<string> {
  return page.evaluate(async () => {
    const response = await fetch("/api/backend/users/me");
    if (response.status !== 200) throw new Error(`Identity request status ${response.status}`);
    return (await response.json() as { id: string }).id;
  });
}

test("real Clerk sessions survive reload, isolate users and end on logout", async ({ page, browser }) => {
  // Ticket-based official test helper: this does NOT test password UI or signup.
  await page.goto("/login");
  await clerk.signIn({ page, emailAddress: emails[0]! });
  await page.goto("/dashboard");
  const first = await identity(page);
  await page.reload();
  expect(await identity(page)).toBe(first);
  const context = await browser.newContext();
  try {
    const secondPage = await context.newPage();
    await secondPage.goto("http://127.0.0.1:3100/login");
    await clerk.signIn({ page: secondPage, emailAddress: emails[1]! });
    await secondPage.goto("http://127.0.0.1:3100/dashboard");
    expect(await identity(secondPage)).not.toBe(first);
    await page.evaluate(async () => {
      const response = await fetch("/api/backend/profile/me", {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ full_name: "Isolated QA Candidate" }),
      });
      if (response.status !== 200) throw new Error(`Profile request status ${response.status}`);
    });
    const otherStatus = await secondPage.evaluate(async () =>
      (await fetch("/api/backend/profile/me")).status);
    // Fixtures must be new users, with no pre-existing profile.
    expect(otherStatus).toBe(404);
    await clerk.signOut({ page });
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/);
    await clerk.signIn({ page, emailAddress: emails[0]! });
    expect(await identity(page)).toBe(first);
    const persisted = await page.evaluate(async () =>
      (await fetch("/api/backend/profile/me")).status);
    expect(persisted).toBe(200);
  } finally {
    // Remove only the local application fixture record, not the Clerk account.
    await page.evaluate(async () => { await fetch("/api/backend/users/me", { method: "DELETE" }); });
    await context.close();
  }
});
