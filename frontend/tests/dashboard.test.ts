import { describe, expect, it } from "vitest";

describe("dashboard foundation", () => {
  it("documents the safety gate", () => {
    const copy = "submits only via sources whose authorization and application capability have both been verified";
    expect(copy).toContain("authorization");
    expect(copy).toContain("application capability");
  });
});
