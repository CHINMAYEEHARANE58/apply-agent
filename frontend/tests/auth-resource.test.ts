import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ protect: vi.fn(), redirect: vi.fn() }));
vi.mock("@clerk/nextjs/server", () => ({ auth: { protect: mocks.protect } }));
vi.mock("next/navigation", () => ({ redirect: mocks.redirect }));
import { requireSignIn } from "../lib/auth-server";

describe("page resource authentication", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.stubEnv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "pk_test_unit_not_a_real_key");
    mocks.redirect.mockImplementation(() => { throw new Error("redirect-to-login"); });
  });
  afterEach(() => vi.unstubAllEnvs());
  it("requires authentication even without a middleware redirect", async () => {
    await requireSignIn();
    expect(mocks.protect).toHaveBeenCalledOnce();
  });
  it("does not render a page when Clerk rejects the session", async () => {
    mocks.protect.mockRejectedValue(new Error("unauthenticated"));
    await expect(requireSignIn()).rejects.toThrow("unauthenticated");
  });
  it("redirects instead of rendering private content with missing keys", async () => {
    vi.stubEnv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "");
    await expect(requireSignIn()).rejects.toThrow("redirect-to-login");
    expect(mocks.redirect).toHaveBeenCalledWith("/login");
    expect(mocks.protect).not.toHaveBeenCalled();
  });
});
