// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import Dashboard from "../app/dashboard/page-content";
import Settings from "../app/settings/page-content";
import Jobs from "../app/jobs/page-content";
import Applications from "../app/applications/page-content";
import Onboarding from "../app/onboarding/page-content";
import { JobCard } from "../components/job-card";
import type { Job } from "../lib/types";

const navigation = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => navigation, usePathname: () => "/dashboard" }));
vi.mock("../components/app-shell", () => ({ AppShell: ({ children }: { children: ReactNode }) => <main>{children}</main> }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.clearAllMocks(); });

const job = { id: "job-1", title: "Software Intern", company: "Real Fixture", job_url: "https://example.com/apply", description: "Python APIs", location: "Pune", duration: "12 weeks", stipend: "20000", currency: "INR", source: "manual", posted_at: null, workplace_type: "remote", saved: false, ignored: false, match_score: 85, matched_skills: ["Python"], missing_skills: ["AWS"] };
const page = (items: unknown[]) => ({ items, total: items.length, limit: 20, offset: 0 });
const settings = { user_id: "own-user", search_enabled: true, search_time: "09:00", timezone: "UTC", minimum_match_score: 75, max_daily_applications: 10, maximum_jobs_evaluated_daily: 100, maximum_applications_prepared_daily: 20, application_mode: "review", email_notifications: true, application_notifications: true, enabled_sources: ["catalog"] };

function mockApi(responses: Record<string, unknown>) {
  const request = vi.fn(async (url: string | URL | Request, options?: RequestInit) => {
    void options;
    const path = String(url).replace("/api/backend/", "");
    if (!(path in responses)) return new Response(JSON.stringify({ error: { message: "Not found" } }), { status: 404 });
    return new Response(JSON.stringify(responses[path]), { headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", request);
  return request;
}

describe("persistent screens use authenticated API data, never production mocks", () => {
  it("dashboard displays zero counts and runs the backend search", async () => {
    const request = mockApi({ dashboard: { jobs_discovered_today: 0, strong_matches: 0, applications_prepared: 0, applications_submitted: 0, interviews: 0, responses: 0 }, "jobs/mine?limit=2&eligible_only=true": page([]), "dashboard/search": { status: "completed", jobs_evaluated: 0, applications_prepared: 0 } });
    render(<Dashboard />);
    await screen.findByText(/No jobs currently meet your mandatory preferences/);
    expect(screen.getAllByText("0")).toHaveLength(6);
    await userEvent.click(screen.getByRole("button", { name: "Run job search" }));
    await screen.findByText(/No external submission/);
    expect(request.mock.calls.some(([url, options]) => String(url).endsWith("dashboard/search") && (options as RequestInit).method === "POST")).toBe(true);
  });
  it("dashboard exposes API failures without inventing fallback counts", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ error: { message: "Database unavailable" } }), { status: 503 })));
    render(<Dashboard />);
    await screen.findAllByRole("alert");
    expect(screen.queryByText("24")).toBeNull();
  });
  it("dashboard permits two consecutive manual searches and explains caching", async () => {
    const request = mockApi({ dashboard: { jobs_discovered_today: 1, strong_matches: 0, applications_prepared: 0, applications_submitted: 0, interviews: 0, responses: 0 }, "jobs/mine?limit=2&eligible_only=true": page([]), "dashboard/search-status": { live_discovery_enabled: true, boards: ["Stripe"], selected_roles: ["Software Engineering Intern"], manual_search_limit: 100, public_cache_seconds: 3600, last_search: null }, "dashboard/search": { status: "completed", trigger: "manual", jobs_evaluated: 7, applications_prepared: 0 } });
    render(<Dashboard />);
    await screen.findByText(/Selected roles: Software Engineering Intern/);
    expect(screen.getByText(/Public boards are cached for up to one hour/)).toBeTruthy();
    for (let i = 0; i < 2; i++) {
      await userEvent.click(screen.getByRole("button", { name: "Run job search" }));
      await screen.findByText(/7 role-relevant listings evaluated.*run another search whenever you like/);
      await waitFor(() => expect((screen.getByRole("button", { name: "Run job search" }) as HTMLButtonElement).disabled).toBe(false));
    }
    expect(request.mock.calls.filter(([url, options]) => String(url).endsWith("dashboard/search") && options?.method === "POST")).toHaveLength(2);
  });
  it("settings read existing values and persist edits without sending user_id", async () => {
    const request = mockApi({ "settings/me": settings });
    render(<Settings />);
    await screen.findByLabelText("Search time");
    fireEvent.change(screen.getByLabelText("Maximum submitted applications daily"), { target: { value: "3" } });
    await userEvent.click(screen.getByRole("button", { name: "Save settings" }));
    await screen.findByText(/Settings saved/);
    const write = request.mock.calls.find(([, options]) => (options as RequestInit)?.method === "PUT");
    const payload = JSON.parse((write?.[1] as RequestInit).body as string);
    expect(payload.max_daily_applications).toBe(3);
    expect(payload).not.toHaveProperty("user_id");
    expect(payload).not.toHaveProperty("authorization_verified");
  });
  it("jobs persist save state to the owner-scoped endpoint", async () => {
    const request = mockApi({ "jobs/mine?limit=20&offset=0&include_ignored=false&eligible_only=true": page([job]), "jobs/job-1/state": { saved: true, ignored: false } });
    render(<Jobs />);
    await screen.findByText("Real Fixture");
    await userEvent.click(screen.getByRole("button", { name: "Save job" }));
    await waitFor(() => expect(request.mock.calls.some(([url, options]) => String(url).endsWith("job-1/state") && (options as RequestInit).method === "PATCH")).toBe(true));
  });
  it("jobs search replays saved counts rather than reporting zero", async () => {
    mockApi({ "jobs/mine?limit=20&offset=0&include_ignored=false&eligible_only=true": page([job]), "dashboard/search": { status: "already_completed", jobs_evaluated: 0, applications_prepared: 0, previous_summary: { status: "completed", jobs_evaluated: 37, strong_matches: 0, applications_prepared: 0 } } });
    render(<Jobs />);
    await screen.findByText("Real Fixture");
    await userEvent.click(screen.getByRole("button", { name: "Run job search" }));
    await screen.findByText(/already ran.*37 listings evaluated/);
    expect(screen.getByRole("heading", { name: "Internship opportunities" })).toBeTruthy();
  });
  it("public source opt-in preserves limits, mode and independent catalogue selection", async () => {
    const request = mockApi({ "settings/me": settings });
    render(<Settings />);
    await screen.findByLabelText("Search time");
    await userEvent.click(screen.getByRole("checkbox", { name: "Public employer boards (Greenhouse API)" }));
    await userEvent.click(screen.getByRole("checkbox", { name: "Imported catalogue (manual handoff only)" }));
    await userEvent.click(screen.getByRole("button", { name: "Save settings" }));
    await screen.findByText(/Settings saved/);
    const write = request.mock.calls.find(([, options]) => (options as RequestInit)?.method === "PUT");
    expect(JSON.parse((write?.[1] as RequestInit).body as string)).toMatchObject({ enabled_sources: ["greenhouse_public"], application_mode: "review", minimum_match_score: 75, max_daily_applications: 10 });
  });
  it("failed save keeps the old card state and shows the error", async () => {
    const failed = vi.fn(async () => { throw new Error("Save rejected"); });
    const view: Job = { id: "1", role: "Intern", company: "Example", location: "Remote", duration: "12 weeks", stipend: "INR 20000", source: "manual", match: 80, skills: [], missingSkills: [], postedDate: "Today", status: "Matched", remote: true };
    render(<JobCard job={view} onStateChange={failed} />);
    await userEvent.click(screen.getByRole("button", { name: "Save job" }));
    await screen.findByText("Save rejected");
    expect(screen.getByRole("button", { name: "Save job" }).querySelector("svg")?.classList.contains("fill-current")).toBe(false);
  });
  it("application approval uses the server's stored application/resume reference", async () => {
    const application = { id: "app-1", job_id: job.id, resume_id: "resume-1", status: "awaiting_approval", cover_letter: "Source-backed cover letter", application_message: "Suggested message", submitted_at: null };
    const request = mockApi({ "applications?limit=20&offset=0": page([application]), "jobs/job-1": job, "resumes/resume-1": { id: "resume-1", approval_status: "draft", generated_bullets: [{ text: "Built a Python API", supporting_fact_ids: ["fact-1"] }] }, "applications/app-1/approve": { ...application, status: "prepared" } });
    render(<Applications />);
    await screen.findByText("Software Intern");
    await userEvent.click(screen.getByRole("button", { name: "Open" }));
    await screen.findByText("Built a Python API");
    await userEvent.click(screen.getByRole("button", { name: "Verify and approve package" }));
    await screen.findByText(/Nothing was submitted/);
    expect(request.mock.calls.some(([url]) => String(url).endsWith("applications/app-1/approve"))).toBe(true);
    expect(request.mock.calls.some(([url]) => String(url).includes("/submit"))).toBe(false);
  });
  it("onboarding persists profile/preferences and uploads the file before navigation", async () => {
    const request = mockApi({ "profile/me": { full_name: "Existing", location: "Pune" }, "preferences/me": {}, "resumes/upload": { id: "stored-resume" } });
    const { container } = render(<Onboarding />);
    await userEvent.click(screen.getByRole("button", { name: "Software Engineering Intern" }));
    for (let index = 0; index < 7; index++) await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    fireEvent.change(container.querySelector('input[type="file"]')!, { target: { files: [new File(["controlled fixture"], "resume.docx", { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" })] } });
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    await userEvent.type(screen.getByLabelText("Your full name"), "QA Candidate");
    await userEvent.click(screen.getByRole("button", { name: "Finish setup" }));
    await waitFor(() => expect(navigation.push).toHaveBeenCalledWith("/dashboard"));
    const upload = request.mock.calls.find(([url]) => String(url).endsWith("resumes/upload"));
    expect((upload?.[1] as RequestInit).body).toBeInstanceOf(FormData);
    const profile = request.mock.calls.find(([url, options]) => String(url).endsWith("profile/me") && (options as RequestInit)?.method === "PUT");
    expect(JSON.parse((profile?.[1] as RequestInit).body as string)).toMatchObject({ full_name: "QA Candidate", location: "Pune" });
  });
});
