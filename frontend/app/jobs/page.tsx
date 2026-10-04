"use client";

import { Filter, Search, SlidersHorizontal } from "lucide-react";
import { useMemo, useState } from "react";
import { AppShell } from "../../components/app-shell";
import { JobCard } from "../../components/job-card";
import { PageHeader } from "../../components/page-header";
import { Button } from "../../components/ui/button";
import { jobs } from "../../lib/mock-data";

const filters = ["Match score", "Role", "Location", "Remote", "Company", "Stipend", "Source", "Date posted", "Application status"];
export default function JobsPage() {
  const [query, setQuery] = useState(""); const [remoteOnly, setRemoteOnly] = useState(false); const [minimumMatch, setMinimumMatch] = useState(0);
  const visibleJobs = useMemo(() => jobs.filter(job => (!remoteOnly || job.remote) && job.match >= minimumMatch && `${job.role} ${job.company}`.toLowerCase().includes(query.toLowerCase())), [minimumMatch, query, remoteOnly]);
  return <AppShell><PageHeader eyebrow="Discover" title="Jobs matched for you" description="Explore mock opportunities from permitted sources. Matches reflect your current profile and preferences." actions={<Button><Search size={16} />Run job search</Button>} />
    <section className="mt-8 rounded-2xl border border-slate-800/80 bg-slate-900/45 p-4"><div className="flex flex-col gap-3 lg:flex-row"><label className="flex h-11 flex-1 items-center gap-2 rounded-xl border border-slate-800 bg-slate-950/40 px-3 text-slate-400"><Search size={17} /><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search role or company" className="w-full bg-transparent text-sm text-white outline-none placeholder:text-slate-600" /></label><select aria-label="Minimum match score" value={minimumMatch} onChange={event => setMinimumMatch(Number(event.target.value))} className="h-11 rounded-xl border border-slate-800 bg-slate-950/40 px-3 text-sm text-slate-300 outline-none"><option value={0}>Any match score</option><option value={80}>80% and above</option><option value={90}>90% and above</option></select><Button variant={remoteOnly ? "secondary" : "outline"} onClick={() => setRemoteOnly(!remoteOnly)}>Remote {remoteOnly ? "on" : "off"}</Button><Button variant="outline"><SlidersHorizontal size={16} />More filters</Button></div><div className="mt-3 flex flex-wrap gap-2">{filters.map(filter => <button key={filter} className="rounded-lg border border-slate-800 px-2.5 py-1 text-xs text-slate-500 transition hover:border-slate-700 hover:text-slate-200">{filter}</button>)}</div></section>
    <div className="mt-6 flex items-center justify-between"><p className="text-sm text-slate-400"><span className="font-medium text-white">{visibleJobs.length}</span> opportunities found</p><Button variant="ghost" size="sm"><Filter size={14} />Most relevant</Button></div><div className="mt-4 space-y-4">{visibleJobs.length ? visibleJobs.map(job => <JobCard key={job.id} job={job} />) : <div className="rounded-2xl border border-dashed border-slate-700 p-12 text-center text-sm text-slate-500">No jobs match these filters yet.</div>}</div>
  </AppShell>;
}
