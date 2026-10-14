import { defineConfig } from "@playwright/test";

// Explicitly opt-in. Never inherit production keys or retain auth traces.
if (!process.env.CLERK_SECRET_KEY?.startsWith("sk_test_") ||
    !process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY?.startsWith("pk_test_")) {
  throw new Error("Configure a dedicated Clerk test application in .env.qa first.");
}

export default defineConfig({
  testDir: "./clerk-qa",
  retries: 0, workers: 1, timeout: 60000,
  reporter: [["list"], ["json", { outputFile: "test-results/clerk-results.json" }]],
  projects: [
    { name: "setup", testMatch: /auth\.setup\.ts/ },
    { name: "sessions", testMatch: /sessions\.spec\.ts/, dependencies: ["setup"] },
  ],
  use: {
    baseURL: "http://127.0.0.1:3100", browserName: "chromium",
    trace: "off", screenshot: "off", video: "off",
  },
  webServer: {
    command: "npm run start -- --hostname 127.0.0.1 --port 3100",
    url: "http://127.0.0.1:3100/login", reuseExistingServer: false,
  },
});
