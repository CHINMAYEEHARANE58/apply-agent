"use client";
import { CalendarDays, FilePenLine, MessageSquare, Send, Sparkles, Target } from "lucide-react";
import { useState } from "react";
import { AppShell } from "../../components/app-shell";
import { JobCard } from "../../components/job-card";
import { PageHeader } from "../../components/page-header";
import { ResourceNotice } from "../../components/resource-notice";
import { Button } from "../../components/ui/button";
import { apiFetch } from "../../lib/api";
import { type Dashboard, type Page, type SearchResult, type StoredJob, displayJob, useResource } from "../../lib/resources";

export default function DashboardPage() {
  const metrics = useResource<Dashboard>("dashboard");
  const jobs = useResource<Page<StoredJob>>("jobs/mine?limit=2");
  const [running, setRunning] = useState(false);
  const [notice, setNotice] = useState("");
  async function search() {
    setRunning(true); setNotice("");
    try {
      const result = await apiFetch<SearchResult>("dashboard/search", { method: "POST" });
      setNotice(result.status.replaceAll("_", " ") + ": " + result.jobs_evaluated + " listings evaluated; " + result.applications_prepared + " applications prepared. No external submission.");
      await Promise.all([metrics.refresh(), jobs.refresh()]);
    } catch (error) { setNotice(error instanceof Error ? error.message : "Search failed."); }
    finally { setRunning(false); }
  }
  const cards = [
    ["Jobs discovered today", metrics.data?.jobs_discovered_today, Sparkles],
    ["Strong matches", metrics.data?.strong_matches, Target],
    ["Applications prepared", metrics.data?.applications_prepared, FilePenLine],
    ["Applications submitted", metrics.data?.applications_submitted, Send],
    ["Interviews", metrics.data?.interviews, CalendarDays],
    ["Responses", metrics.data?.responses, MessageSquare],
  ] as const;
  return <AppShell><PageHeader eyebrow="Overview" title="Your internship search, organized." description="Your saved search activity and applications—not demo numbers." actions={<Button disabled={running} onClick={() => void search()}><Sparkles size={16} />{running ? "Searching…" : "Run job search"}</Button>} />
    {notice ? <p role="status" className="mt-4 text-sm text-slate-300">{notice}</p> : null}
    <ResourceNotice loading={metrics.loading} error={metrics.error} />
    <section className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{cards.map(([label, value, Icon]) => <div key={label} className="rounded-2xl border border-slate-800/80 bg-slate-900/45 p-5"><span className="grid h-10 w-10 place-items-center rounded-xl bg-violet-500/10 text-violet-300"><Icon size={19} /></span><p className="mt-5 text-3xl font-semibold text-white">{value ?? "—"}</p><p className="mt-1 text-sm text-slate-400">{label}</p></div>)}</section>
    <section className="mt-10"><h2 className="font-semibold text-white">Recent matches</h2><ResourceNotice loading={jobs.loading} error={jobs.error} empty={!jobs.data?.items.length ? "No imported listings yet. Complete onboarding, then run your search. No job website automation is enabled." : undefined} /><div className="mt-4 space-y-4">{jobs.data?.items.map(job => <JobCard key={job.id} job={displayJob(job)} onStateChange={async changes => { await apiFetch("jobs/" + job.id + "/state", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(changes) }); await jobs.refresh(); }} />)}</div><a href="/jobs" className="mt-5 inline-block text-sm text-violet-300">View all opportunities →</a></section>
  </AppShell>;
}
