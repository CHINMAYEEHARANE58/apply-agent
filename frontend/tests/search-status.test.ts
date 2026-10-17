import { describe, expect, it } from "vitest";
import { searchMessage } from "../lib/search-status";
import { displayJob } from "../lib/resources";

const empty = { status: "completed", jobs_evaluated: 0, applications_prepared: 0 };
describe("job discovery explains real outcomes", () => {
  it("distinguishes an empty catalogue from a live web search", () => {
    expect(searchMessage({ ...empty, catalog_only: true })).toContain("No role-relevant internships were found");
    expect(searchMessage({ ...empty, catalog_only: false })).toContain("No internships for your selected roles");
  });
  it("labels historical empty summaries as catalogue-only", () => {
    expect(searchMessage(empty)).toContain("No role-relevant internships were found");
  });
  it("shows earlier counts instead of pretending a replay evaluated zero", () => {
    const text = searchMessage({ ...empty, status: "already_completed", previous_summary: { ...empty, jobs_evaluated: 38, strong_matches: 2 } });
    expect(text).toContain("already ran");
    expect(text).toContain("38 listings evaluated");
    expect(text).toContain("2 strong matches");
  });
  it.each(["disabled", "needs_preferences", "needs_roles", "already_running", "needs_resume", "no_sources_enabled", "daily_evaluation_limit", "retry_limit_reached", "source_unavailable", "failed"])("does not claim success for %s", status => {
    expect(searchMessage({ ...empty, status })).not.toContain("Search completed");
  });
  it("explains repeatable manual searches without claiming fresh network results", () => {
    const text = searchMessage({ ...empty, jobs_evaluated: 7, trigger: "manual" });
    expect(text).toContain("7 role-relevant listings evaluated");
    expect(text).toContain("run another search whenever you like");
    expect(text).not.toContain("already ran");
  });
  it("does not label a hard-filter rejection as matched", () => {
    const job = displayJob({ id: "j", title: "Intern", company: "Fixture", description: "Role", job_url: "https://example.com", location: null, duration: null, stipend: null, currency: null, source: "greenhouse_public", posted_at: null, workplace_type: "unknown", saved: false, ignored: false, match_score: 0, matched_skills: [], missing_skills: [], hard_filter_passed: false });
    expect(job.status).toBe("Discovered");
    expect(job.source).toBe("Greenhouse public API");
  });
});
