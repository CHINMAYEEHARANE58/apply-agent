import { test } from "@playwright/test";
import { clerkSetup } from "@clerk/testing/playwright";

test("initialize dedicated Clerk test application", async () => {
  await clerkSetup({ debug: false });
});
