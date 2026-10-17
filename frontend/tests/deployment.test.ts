import { spawnSync } from "node:child_process";
import { describe, expect, it } from "vitest";

const valid = { NODE_ENV: "test" as const, NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: "pk_test_fixture", CLERK_SECRET_KEY: "sk_test_fixture", INTERNAGENT_API_URL: "https://api.example.com/api/v1", VERCEL_ENV: "preview" };
function check(changes: Record<string, string>) {
  return spawnSync(process.execPath, ["scripts/check-deployment.mjs"], { env: { ...valid, ...changes }, encoding: "utf8" });
}
describe("Vercel deployment fails closed on missing configuration", () => {
  it("accepts an explicitly configured preview without claiming service health", () => {
    const result = check({}); expect(result.status).toBe(0);
    expect(result.stdout).toContain("must still be verified");
    expect(result.stdout + result.stderr).not.toContain("sk_test_fixture");
  });
  it.each(["NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "CLERK_SECRET_KEY", "INTERNAGENT_API_URL"])("blocks missing %s", name => {
    expect(check({ [name]: "" }).status).toBe(1);
  });
  it.each(["http://localhost:8000/api/v1", "https://127.0.0.1/api/v1", "not-a-url-with-private-detail", "https://user:private-password@api.example.com/api/v1", "https://api.example.com/api/v1?token=private-token"])("rejects unsafe/invalid backend configuration without printing its value", url => {
    const result = check({ INTERNAGENT_API_URL: url }); expect(result.status).toBe(1);
    expect(result.stderr).not.toContain(url); expect(result.stderr).not.toContain("private-password"); expect(result.stderr).not.toContain("private-token");
  });
  it("blocks test keys in production and mismatched Clerk key environments", () => {
    expect(check({ VERCEL_ENV: "production" }).status).toBe(1);
    expect(check({ CLERK_SECRET_KEY: "sk_live_fixture" }).status).toBe(1);
    expect(check({ VERCEL_ENV: "production", NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: "pk_live_fixture", CLERK_SECRET_KEY: "sk_live_fixture" }).status).toBe(0);
  });
});
