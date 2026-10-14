import { defineConfig } from "vitest/config";

export default defineConfig({
  oxc: { jsx: { runtime: "automatic" } },
  test: {
    include: ["tests/**/*.test.{ts,tsx}", "lib/**/*.test.ts"],
    coverage: { provider: "v8", reporter: ["text", "json-summary", "html"], include: ["lib/**/*.ts", "components/**/*.tsx", "app/**/page-content.tsx"], exclude: ["lib/mock-data.ts", "lib/types.ts"] },
  },
});
