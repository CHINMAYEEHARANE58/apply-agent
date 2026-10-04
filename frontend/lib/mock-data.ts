import type { Application, DashboardMetric, Job, Resume } from "./types";

export const dashboardMetrics: DashboardMetric[] = [
  { label: "Jobs discovered today", value: "28", change: "+12%", icon: "Sparkles" },
  { label: "Strong matches", value: "12", change: "Above 80%", icon: "Target" },
  { label: "Applications prepared", value: "7", change: "3 need review", icon: "FilePenLine" },
  { label: "Applications submitted", value: "16", change: "This month", icon: "Send" },
  { label: "Interviews", value: "3", change: "1 this week", icon: "CalendarDays" },
  { label: "Responses", value: "9", change: "+2 this week", icon: "MessageSquare" }
];

export const jobs: Job[] = [
  { id: "job-1", role: "Software Engineering Intern", company: "Vercel", location: "Remote · United States", duration: "12 weeks", stipend: "$42/hr", source: "Vercel Careers", match: 94, skills: ["TypeScript", "React", "Next.js"], missingSkills: ["GraphQL"], postedDate: "Posted 2h ago", status: "Matched", remote: true },
  { id: "job-2", role: "AI/ML Engineering Intern", company: "Figma", location: "San Francisco, CA", duration: "16 weeks", stipend: "$9,000/mo", source: "Figma Careers", match: 89, skills: ["Python", "PyTorch", "Machine Learning"], missingSkills: ["Kubernetes"], postedDate: "Posted 5h ago", status: "Prepared", remote: false },
  { id: "job-3", role: "Full Stack Developer Intern", company: "Linear", location: "Remote · Global", duration: "12 weeks", stipend: "$35/hr", source: "Linear Careers", match: 86, skills: ["TypeScript", "React", "PostgreSQL"], missingSkills: ["Go"], postedDate: "Posted yesterday", status: "Discovered", remote: true },
  { id: "job-4", role: "Data Science Intern", company: "Notion", location: "New York, NY · Hybrid", duration: "10 weeks", stipend: "$7,500/mo", source: "Notion Careers", match: 81, skills: ["Python", "SQL", "Machine Learning"], missingSkills: ["Snowflake"], postedDate: "Posted yesterday", status: "Awaiting Approval", remote: false }
];

export const applications: Application[] = [
  { id: "app-1", company: "Figma", role: "AI/ML Engineering Intern", status: "Prepared", updatedAt: "Updated 20m ago", match: 89 },
  { id: "app-2", company: "Vercel", role: "Software Engineering Intern", status: "Awaiting Approval", updatedAt: "Updated 1h ago", match: 94 },
  { id: "app-3", company: "Linear", role: "Full Stack Developer Intern", status: "Submitted", updatedAt: "Submitted yesterday", match: 86 },
  { id: "app-4", company: "Stripe", role: "Backend Developer Intern", status: "Interview", updatedAt: "Interview Oct 12", match: 82 },
  { id: "app-5", company: "Notion", role: "Data Science Intern", status: "Assessment", updatedAt: "Due in 3 days", match: 81 }
];

export const resumes: Resume[] = [
  { id: "resume-master", name: "Aarav_Shah_Master_Resume.pdf", kind: "Master", updatedAt: "Updated Oct 2, 2026", targetedRole: "All applications" },
  { id: "resume-1", name: "Aarav_Shah_Vercel_SWE.pdf", kind: "Tailored", updatedAt: "Prepared today", targetedRole: "Software Engineering Intern · Vercel" },
  { id: "resume-2", name: "Aarav_Shah_Figma_ML.pdf", kind: "Tailored", updatedAt: "Prepared today", targetedRole: "AI/ML Engineering Intern · Figma" }
];
