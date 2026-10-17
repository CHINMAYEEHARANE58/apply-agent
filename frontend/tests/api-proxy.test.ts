import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const identity = vi.hoisted(() => ({ userId: "user_test" as string | null, token: "test-session-token" as string | null }));
vi.mock("@clerk/nextjs/server", () => ({ auth: async () => ({ userId: identity.userId, getToken: async () => identity.token }) }));
import { GET, POST } from "../app/api/backend/[...path]/route";

const context = (path = ["users", "me"]) => ({ params: Promise.resolve({ path }) });
describe("Clerk authenticated backend proxy", () => {
  beforeEach(() => {
    identity.userId = "user_test";
    identity.token = "test-session-token";
    vi.stubEnv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "pk_test_unit_test_not_a_real_key");
    vi.stubEnv("INTERNAGENT_API_URL", "https://api.example/api/v1");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('{}', { headers: { "content-type": "application/json" } })));
  });
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllEnvs(); vi.unstubAllGlobals(); });
  it("fails closed when sign-in configuration is absent", async () => {
    vi.stubEnv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "");
    expect((await GET(new Request("https://app.example/api/backend/users/me"), context())).status).toBe(503);
    expect(fetch).not.toHaveBeenCalled();
  });
  it("does not forward unauthenticated users", async () => {
    identity.userId = null;
    expect((await GET(new Request("https://app.example/api/backend/users/me"), context())).status).toBe(401);
    expect(fetch).not.toHaveBeenCalled();
  });
  it("does not fall back to localhost on Vercel when the backend URL is absent", async () => {
    vi.stubEnv("VERCEL", "1"); vi.stubEnv("INTERNAGENT_API_URL", "");
    expect((await GET(new Request("https://app.example/api/backend/users/me"), context())).status).toBe(503);
    expect(fetch).not.toHaveBeenCalled();
  });
  it("rejects cross-origin and missing-origin mutations", async () => {
    for (const origin of ["https://attacker.example", ""]) {
      const request = new Request("https://app.example/api/backend/preferences/me", { method: "POST", headers: origin ? { origin } : {}, body: '{}' });
      expect((await POST(request, context(["preferences", "me"]))).status).toBe(403);
    }
    expect(fetch).not.toHaveBeenCalled();
  });
  it("blocks arbitrary URLs and traversal outside the allowlist", async () => {
    for (const path of [["https://attacker.example"], ["users", "..", "secrets"], ["audit-events"]]) {
      expect((await GET(new Request("https://app.example/api/backend/users/me"), context(path))).status).toBe(404);
    }
    expect(fetch).not.toHaveBeenCalled();
  });
  it("forwards verified session only, not browser identity or cookies", async () => {
    const request = new Request("https://app.example/api/backend/users/me", { headers: { "X-User-Id": "victim-id", cookie: "secret-cookie", authorization: "Bearer forged" } });
    const response = await GET(request, context());
    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("no-store");
    const [target, options] = vi.mocked(fetch).mock.calls[0];
    expect(String(target)).toBe("https://api.example/api/v1/users/me");
    const headers = new Headers(options?.headers);
    expect(headers.get("authorization")).toBe("Bearer test-session-token");
    expect(headers.has("cookie")).toBe(false);
    expect(headers.has("x-user-id")).toBe(false);
  });
  it("enforces upload limits even with a valid session", async () => {
    const request = new Request("https://app.example/api/backend/resumes/upload", { method: "POST", headers: { origin: "https://app.example", "content-length": "9000000" }, body: 'x' });
    expect((await POST(request, context(["resumes", "upload"]))).status).toBe(413);
    expect(fetch).not.toHaveBeenCalled();
  });
  it("returns a generic error when the backend fails", async () => {
    vi.mocked(fetch).mockRejectedValue(new Error("private database credential"));
    const response = await GET(new Request("https://app.example/api/backend/users/me"), context());
    expect(response.status).toBe(503);
    expect(await response.text()).not.toContain("credential");
  });
  it("gives only the search POST a bounded two-minute deadline", async () => {
    const deadline = vi.spyOn(AbortSignal, "timeout");
    const request = new Request("https://app.example/api/backend/dashboard/search", { method: "POST", headers: { origin: "https://app.example" } });
    expect((await POST(request, context(["dashboard", "search"]))).status).toBe(200);
    expect(deadline).toHaveBeenLastCalledWith(120000);
    await GET(new Request("https://app.example/api/backend/users/me"), context());
    expect(deadline).toHaveBeenLastCalledWith(30000);
  });
  it("explains a search timeout without exposing upstream errors or retrying it", async () => {
    vi.mocked(fetch).mockRejectedValue(new DOMException("private upstream detail", "TimeoutError"));
    const request = new Request("https://app.example/api/backend/dashboard/search", { method: "POST", headers: { origin: "https://app.example" } });
    const response = await POST(request, context(["dashboard", "search"]));
    expect(response.status).toBe(504);
    const text = await response.text();
    expect(text).toContain("refresh the dashboard");
    expect(text).not.toContain("private upstream detail");
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});
