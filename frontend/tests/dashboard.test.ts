import { describe, expect, it } from "vitest";
import { dashboardMetrics, jobs } from "../lib/mock-data";

describe("mocked dashboard data", () => {
  it("provides the six dashboard metrics and explainable job matches", () => {
    expect(dashboardMetrics).toHaveLength(6);
    expect(jobs.every(job => job.match > 0 && job.skills.length > 0 && job.missingSkills.length > 0)).toBe(true);
  });
});
