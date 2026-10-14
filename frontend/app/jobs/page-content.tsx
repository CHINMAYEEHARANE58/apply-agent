"use client";
import { Search } from "lucide-react";
import { useMemo, useState } from "react";
import { AppShell } from "../../components/app-shell";
import { JobCard } from "../../components/job-card";
import { PageHeader } from "../../components/page-header";
import { ResourceNotice } from "../../components/resource-notice";
import { Button } from "../../components/ui/button";
import { apiFetch } from "../../lib/api";
import { type Page, type SearchResult, type StoredJob, displayJob, useResource } from "../../lib/resources";

export default function JobsPage() {
  const [offset, setOffset] = useState(0);
  const [includeIgnored, setIncludeIgnored] = useState(false);
  const resource = useResource<Page<StoredJob>>("jobs/mine?limit=20&offset=" + offset + "&include_ignored=" + includeIgnored);
  const [query, setQuery] = useState("");
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [minimumMatch, setMinimumMatch] = useState(0);
  const [notice, setNotice] = useState("");
  const [running, setRunning] = useState(false);
  const visible = useMemo(() => (resource.data?.items || []).filter(job => (!remoteOnly || job.workplace_type === "remote") && (job.match_score || 0) >= minimumMatch && (job.title + " " + job.company + " " + job.location).toLowerCase().includes(query.toLowerCase())), [resource.data, query, remoteOnly, minimumMatch]);
  async function search() {
    setRunning(true); setNotice("");
    try {
      const result = await apiFetch<SearchResult>("dashboard/search", { method: "POST" });
      setNotice(result.status.replaceAll("_", " ") + ": " + result.jobs_evaluated + " evaluated, " + result.applications_prepared + " prepared for review.");
      await resource.refresh();
    } catch (error) { setNotice(error instanceof Error ? error.message : "Search failed."); }
    finally { setRunning(false); }
  }
  return <AppShell><PageHeader eyebrow="Discover" title="Jobs matched for you" description="Stored opportunities and your private saved/ignored state. Search uses the imported catalogue, not restricted-site automation." actions={<Button disabled={running} onClick={() => void search()}><Search size={16} />{running ? "Searching…" : "Run job search"}</Button>} />
    {notice ? <p role="status" className="mt-4 text-sm text-slate-300">{notice}</p> : null}
    <section className="mt-8 flex flex-wrap gap-3 rounded-2xl border border-slate-800/80 bg-slate-900/45 p-4"><input aria-label="Search current page" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search this page by role, company or location" className="h-11 min-w-0 flex-1 rounded-xl border border-slate-800 bg-slate-950/40 px-3 text-sm" /><select aria-label="Minimum match score" value={minimumMatch} onChange={event => setMinimumMatch(Number(event.target.value))} className="rounded-xl bg-slate-900 px-3"><option value={0}>Any match score</option><option value={75}>75% and above</option><option value={90}>90% and above</option></select><Button variant={remoteOnly ? "secondary" : "outline"} onClick={() => setRemoteOnly(!remoteOnly)}>Remote {remoteOnly ? "on" : "off"}</Button><Button variant="outline" onClick={() => { setOffset(0); setIncludeIgnored(!includeIgnored); }}>{includeIgnored ? "Hide ignored" : "Show ignored"}</Button></section>
    <ResourceNotice loading={resource.loading} error={resource.error} empty={!visible.length ? "No opportunities on this page match your filters." : undefined} />
    <p className="mt-6 text-sm text-slate-400">{resource.data?.total ?? "—"} stored opportunities</p>
    <div className="mt-4 space-y-4">{visible.map(job => job.ignored ? <article key={job.id} className="rounded-xl border border-slate-800 p-5"><p>{job.title} · {job.company} — ignored</p><Button className="mt-3" onClick={() => { void apiFetch("jobs/" + job.id + "/state", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ignored: false }) }).then(resource.refresh).catch(error => setNotice(error.message)); }}>Restore</Button></article> : <JobCard key={job.id} job={displayJob(job)} onStateChange={async changes => { await apiFetch("jobs/" + job.id + "/state", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(changes) }); await resource.refresh(); }} />)}</div>
    <div className="mt-5 flex gap-3"><Button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>Previous</Button><Button disabled={!resource.data || offset + 20 >= resource.data.total} onClick={() => setOffset(offset + 20)}>Next</Button></div>
  </AppShell>;
}
