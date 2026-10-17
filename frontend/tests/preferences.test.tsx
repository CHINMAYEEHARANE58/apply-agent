// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import Preferences from "../app/preferences/page-content";
import Jobs from "../app/jobs/page-content";
import { type PreferenceEditor, parseList, preferenceDraft, preferencePayload } from "../lib/preferences";

vi.mock("../components/app-shell", () => ({ AppShell: ({ children }: { children: ReactNode }) => <main>{children}</main> }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const values = { ...preferencePayload({ ...preferenceDraft(null), roles: "Software Engineering Intern" }), minimum_stipend: "20000.00", currency: "INR", preferred_countries: ["India"], preferred_cities: ["Mumbai"], preferred_locations: ["Maharashtra"], min_duration: 8, max_duration: 16, search_enabled: false, preferred_search_time: "17:30", application_mode: "batch" as const, max_daily_applications: 12, minimum_match_score: 83 };
const original: PreferenceEditor = { preferences: { ...values, id: "own-preferences", user_id: "own-user" }, eligibility: { work_authorization: "Explicitly supplied", relocation_allowed: true, visa_sponsorship_required: null } };
function setup(fail = false) {
  let stored = structuredClone(original);
  const request = vi.fn(async (_url: string, options?: RequestInit) => {
    if (options?.method === "PUT") {
      if (fail) return new Response(JSON.stringify({ error: { message: "Could not save" } }), { status: 503 });
      const body = JSON.parse(String(options.body));
      stored = { preferences: { ...body.preferences, id: "own-preferences", user_id: "own-user" }, eligibility: body.eligibility };
    }
    return new Response(JSON.stringify(stored), { headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", request); return request;
}
describe("saved internship preference editor", () => {
  it("prefills saved choices, preserves unknown visa answers and has no resume upload", async () => {
    setup(); const view = render(<Preferences />);
    const city = await screen.findByLabelText("Preferred cities");
    expect((city as HTMLTextAreaElement).value).toBe("Mumbai");
    expect((screen.getByLabelText("Other mandatory location text") as HTMLTextAreaElement).value).toBe("Maharashtra");
    expect((screen.getByLabelText("Minimum stipend") as HTMLInputElement).value).toBe("20000.00");
    expect((screen.getByLabelText("Visa sponsorship required") as HTMLSelectElement).value).toBe("unknown");
    expect((screen.getByRole("button", { name: "Software Engineering Intern" })).getAttribute("aria-pressed")).toBe("true");
    expect(view.container.querySelector('input[type="file"]')).toBeNull();
    expect((screen.getByRole("button", { name: "Save preferences" }) as HTMLButtonElement).disabled).toBe(true);
  });
  it("saves edits, retains hidden scheduling fields and reloads persisted values without owner IDs", async () => {
    const request = setup(); const view = render(<Preferences />);
    await screen.findByLabelText("Preferred cities");
    fireEvent.change(screen.getByLabelText("Preferred cities"), { target: { value: "Pune, Bengaluru" } });
    fireEvent.change(screen.getByLabelText("Minimum stipend"), { target: { value: "15000.25" } });
    await userEvent.click(screen.getByRole("button", { name: "Frontend Developer Intern" }));
    await userEvent.click(screen.getByRole("button", { name: "Save preferences" }));
    await screen.findByText(/Preferences saved/);
    const write = request.mock.calls.find(([, options]) => options?.method === "PUT");
    const body = JSON.parse(String(write?.[1]?.body));
    expect(body.preferences).toMatchObject({ preferred_cities: ["Pune", "Bengaluru"], minimum_stipend: "15000.25", preferred_locations: ["Maharashtra"], search_enabled: false, preferred_search_time: "17:30", application_mode: "batch", max_daily_applications: 12, minimum_match_score: 83 });
    expect(body.preferences.roles).toContain("Frontend Developer Intern");
    expect(body.preferences).not.toHaveProperty("user_id"); expect(body.preferences).not.toHaveProperty("id");
    expect(body.eligibility.visa_sponsorship_required).toBeNull();
    expect(request.mock.calls.every(([url]) => url.endsWith("preferences/editor"))).toBe(true);
    view.unmount(); render(<Preferences />);
    await waitFor(() => expect((screen.getByLabelText("Preferred cities") as HTMLTextAreaElement).value).toBe("Pune, Bengaluru"));
  });
  it("retains unsaved edits on server failure", async () => {
    setup(true); render(<Preferences />); await screen.findByLabelText("Preferred cities");
    fireEvent.change(screen.getByLabelText("Preferred cities"), { target: { value: "Pune" } });
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await screen.findByText("Could not save");
    expect((screen.getByLabelText("Preferred cities") as HTMLTextAreaElement).value).toBe("Pune");
  });
  it("validates duration before sending any write", async () => {
    const request = setup(); const view = render(<Preferences />); await screen.findByLabelText("Minimum duration");
    fireEvent.change(screen.getByLabelText("Minimum duration"), { target: { value: "20" } });
    fireEvent.submit(view.container.querySelector("form")!);
    await screen.findByText("Minimum duration cannot exceed maximum duration.");
    expect(request.mock.calls.some(([, options]) => options?.method === "PUT")).toBe(false);
  });
  it("does not present rejected discoveries as eligible matches by default", async () => {
    const request = vi.fn(async (url: string) => {
      const all = url.includes("eligible_only=false");
      return new Response(JSON.stringify({ items: all ? [{ id: "j", title: "Software Intern", company: "Fixture", description: "Role", job_url: "https://example.com", location: "Wrong city", duration: null, stipend: null, currency: null, source: "manual", posted_at: null, workplace_type: "unknown", saved: false, ignored: false, match_score: 0, hard_filter_passed: false, match_explanation: "Mandatory location did not match.", matched_skills: [], missing_skills: [] }] : [], total: all ? 1 : 0, limit: 20, offset: 0 }));
    });
    vi.stubGlobal("fetch", request); render(<Jobs />);
    await screen.findByText(/No jobs currently meet your mandatory preferences/);
    expect(screen.queryByText("Fixture")).toBeNull();
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Results view" }), "all");
    await screen.findByText("Fixture");
    expect(screen.getByText(/Does not meet mandatory preferences.*Mandatory location did not match/)).toBeTruthy();
  });
});

describe("preference payload validation", () => {
  it("keeps null and exact decimal stipend semantics", () => {
    const draft = preferenceDraft(original.preferences);
    expect(preferencePayload({ ...draft, minimum_stipend: "", min_duration: "", max_duration: "" })).toMatchObject({ minimum_stipend: null, min_duration: null, max_duration: null });
    expect(preferencePayload({ ...draft, minimum_stipend: "10000.01" }).minimum_stipend).toBe("10000.01");
    expect(parseList("React, react\nPython, ")).toEqual(["React", "Python"]);
  });
  it.each([{ roles: "" }, { remote_allowed: false, hybrid_allowed: false, onsite_allowed: false }, { min_duration: "20", max_duration: "8" }, { minimum_stipend: "-1" }, { minimum_stipend: "10.123" }, { minimum_stipend: "100", currency: null }, { max_daily_applications: "51" }, { minimum_match_score: "101" }, { earliest_start_date: "2027-03-01", latest_start_date: "2027-01-01" }])("rejects invalid input %j", changes => {
    expect(() => preferencePayload({ ...preferenceDraft(original.preferences), ...changes })).toThrow();
  });
});
