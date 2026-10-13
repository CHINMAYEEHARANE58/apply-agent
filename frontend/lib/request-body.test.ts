import { describe, expect, it } from "vitest";
import { readLimitedBody } from "./request-body";

describe("authenticated proxy body limits", () => {
  it("preserves JSON bytes", async () => {
    const body = await readLimitedBody(new Request("https://test.example", { method: "POST", body: '{"roles":[]}' }));
    expect(new TextDecoder().decode(body)).toBe('{"roles":[]}');
  });
  it("rejects declared oversized uploads before reading", async () => {
    const request = new Request("https://test.example", { method: "POST", headers: { "content-length": "9000000", "content-type": "multipart/form-data; boundary=test" }, body: "x" });
    await expect(readLimitedBody(request)).rejects.toThrow(RangeError);
  });
  it("rejects oversized bodies without trusting content length", async () => {
    const request = new Request("https://test.example", { method: "POST", body: new Uint8Array(1024 * 1024 + 1) });
    await expect(readLimitedBody(request)).rejects.toThrow(RangeError);
  });
  it("handles bodyless mutations", async () => {
    expect((await readLimitedBody(new Request("https://test.example", { method: "DELETE" }))).byteLength).toBe(0);
  });
});
