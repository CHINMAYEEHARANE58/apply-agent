// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { JobCard } from "../components/job-card";
import { Button } from "../components/ui/button";
import Onboarding from "../app/onboarding/page-content";
import type { Job } from "../lib/types";

const navigation = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => navigation, usePathname: () => "/onboarding" }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

const job: Job = { id: "test", role: "Software Intern", company: "Example", location: "Remote", duration: "3 months", stipend: "₹20,000", source: "Manual", match: 85, skills: ["React", "Python"], missingSkills: ["AWS"], postedDate: "Today", status: "Matched", remote: true };

describe("job-card behavior", () => {
  it("shows candidate strengths AND missing skills", () => {
    render(<JobCard job={job} />);
    expect(screen.getByText("85% match")).toBeTruthy();
    expect(screen.getByText("React")).toBeTruthy();
    expect(screen.getByText("AWS")).toBeTruthy();
    expect(screen.getByText("Source: Manual")).toBeTruthy();
  });
  it("escapes attacker-controlled company and role", () => {
    const payload = '<img src=x onerror="window.qaXss=true">';
    const { container } = render(<JobCard job={{ ...job, company: payload, role: "<script>alert(1)</script>" }} />);
    expect(screen.getByText(payload)).toBeTruthy();
    expect(container.querySelector("img,script")).toBeNull();
  });
  it("ignoring a card removes it from the current view", async () => {
    render(<JobCard job={job} />);
    await userEvent.click(screen.getByRole("button", { name: "Ignore" }));
    expect(screen.queryByText("Software Intern")).toBeNull();
  });
  it("save control toggles state without claiming database persistence", async () => {
    render(<JobCard job={job} />);
    const button = screen.getByRole("button", { name: "Save job" });
    await userEvent.click(button);
    expect(button.querySelector("svg")?.classList.contains("fill-current")).toBe(true);
    await userEvent.click(button);
    expect(button.querySelector("svg")?.classList.contains("fill-current")).toBe(false);
  });
});

describe("onboarding controls (UI only, not persistence)", () => {
  it("requires at least one role to continue", async () => {
    render(<Onboarding />);
    const next = screen.getByRole("button", { name: "Continue" }) as HTMLButtonElement;
    expect(next.disabled).toBe(true);
    await userEvent.click(screen.getByRole("button", { name: "Software Engineering Intern" }));
    expect(next.disabled).toBe(false);
    await userEvent.click(next);
    expect(screen.getByText("Which skills should we prioritize?")).toBeTruthy();
  });
  it("adds and removes a custom role safely", async () => {
    render(<Onboarding />);
    await userEvent.type(screen.getByPlaceholderText("Add a custom role"), "Robotics Intern");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(screen.getByText("Robotics Intern")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Remove Robotics Intern" }));
    expect(screen.queryByText("Robotics Intern")).toBeNull();
  });
  it("preserves selections when navigating between steps", async () => {
    render(<Onboarding />);
    await userEvent.click(screen.getByRole("button", { name: "Software Engineering Intern" }));
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    await userEvent.click(screen.getByRole("button", { name: "Python" }));
    await userEvent.click(screen.getByRole("button", { name: "Back" }));
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(screen.getByRole("button", { name: "Python" }).className).toContain("border-violet-400");
  });
  it("rejects oversized resume selections without showing them as valid", async () => {
    const { container } = render(<Onboarding />);
    await userEvent.click(screen.getByRole("button", { name: "Software Engineering Intern" }));
    for (let i = 0; i < 7; i++) await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    const file = new File([new Uint8Array(5 * 1024 * 1024 + 1)], "huge.pdf", { type: "application/pdf" });
    fireEvent.change(container.querySelector('input[type="file"]')!, { target: { files: [file] } });
    expect(screen.getByText("Your resume must be 5 MB or smaller.")).toBeTruthy();
    expect(screen.queryByText("huge.pdf")).toBeNull();
  });
  it("defaults to review-every-application rather than automatic submission", async () => {
    const { container } = render(<Onboarding />);
    await userEvent.click(screen.getByRole("button", { name: "Software Engineering Intern" }));
    for (let i = 0; i < 7; i++) await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    fireEvent.change(container.querySelector('input[type="file"]')!, { target: { files: [new File(["%PDF-1.7"], "resume.pdf", { type: "application/pdf" })] } });
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(screen.getByRole("button", { name: /Review Every Application/ }).className).toContain("border-violet-400");
  });
});

it("blocks inverted duration ranges and explains the error", async () => {
  render(<Onboarding />);
  await userEvent.click(screen.getByRole("button", { name: "Software Engineering Intern" }));
  for (let i = 0; i < 3; i++) await userEvent.click(screen.getByRole("button", { name: "Continue" }));
  fireEvent.change(screen.getByLabelText("Minimum"), { target: { value: "20" } });
  fireEvent.change(screen.getByLabelText("Maximum"), { target: { value: "3" } });
  expect((screen.getByRole("button", { name: "Continue" }) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getByRole("alert").textContent).toContain("valid duration range");
});

it("buttons honor disabled state and never accidentally submit a form", () => {
  render(<Button disabled>Save</Button>);
  const button = screen.getByRole("button", { name: "Save" }) as HTMLButtonElement;
  expect(button.disabled).toBe(true);
  expect(button.type).toBe("button");
});
