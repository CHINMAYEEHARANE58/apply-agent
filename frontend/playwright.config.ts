import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  retries: 0,
  workers: 1,
  timeout: 20000,
  reporter: [["list"], ["json", { outputFile: "test-results/e2e-results.json" }]],
  use: { baseURL: "http://127.0.0.1:3100", browserName: "chromium", trace: "retain-on-failure" },
  webServer: {
    command: "npm run start -- --hostname 127.0.0.1 --port 3100",
    url: "http://127.0.0.1:3100/login", reuseExistingServer: false,
    env: { NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: "", CLERK_SECRET_KEY: "", INTERNAGENT_API_URL: "http://127.0.0.1:8100/api/v1" },
  },
});
