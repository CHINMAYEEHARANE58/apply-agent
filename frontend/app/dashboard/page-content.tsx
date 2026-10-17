"use client";
import { CalendarDays, FilePenLine, MessageSquare, Send, Sparkles, Target } from "lucide-react";
import { useState } from "react";
import { AppShell } from "../../components/app-shell";
import { JobCard } from "../../components/job-card";
import { PageHeader } from "../../components/page-header";
import { ResourceNotice } from "../../components/resource-notice";
import { Button } from "../../components/ui/button";
import { apiFetch } from "../../lib/api";
import { type Dashboard, type Page, type SearchResult, type SearchStatus, type StoredJob, displayJob, useResource } from "../../lib/resources";
import { searchMessage } from "../../lib/search-status";

export default function DashboardPage() {
  const metrics = useResource<Dashboard>("dashboard");
  const jobs = useResource<Page<StoredJob>>("jobs/mine?limit=2&eligible_only=true");
  const discovery = useResource<SearchStatus>("dashboard/search-status");
  const [running, setRunning] = useState(false);
  const [notice, setNotice] = useState("");
  const [result, setResult] = useState<SearchResult | null>(null);
  async function search() {
    setRunning(true); setNotice("");
    try {
      const result = await apiFetch<SearchResult>("dashboard/search", { method: "POST" });
      setResult(result.previous_summary ?? result);
      setNotice(searchMessage(result));
      await Promise.all([metrics.refresh(), jobs.refresh(), discovery.refresh()]);
    } catch (error) { setNotice(error instanceof Error ? error.message : "Search failed."); }
    finally { setRunning(false); }
  }
  const cards = [
    ["Role-relevant discoveries today", metrics.data?.jobs_discovered_today, Sparkles],
    ["Strong matches", metrics.data?.strong_matches, Target],
    ["Applications prepared", metrics.data?.applications_prepared, FilePenLine],
    ["Applications submitted", metrics.data?.applications_submitted, Send],
    ["Interviews", metrics.data?.interviews, CalendarDays],
    ["Responses", metrics.data?.responses, MessageSquare],
  ] as const;
  const last = result ?? discovery.data?.last_search;
  return <AppShell><PageHeader eyebrow="Overview" title="Your internship search, organized." description="Your saved search activity and applications—not demo numbers." actions={<Button disabled={running} onClick={() => void search()}><Sparkles size={16} />{running ? "Searching…" : "Run job search"}</Button>} />
    {discovery.data ? <section className="mt-5 rounded-2xl border border-slate-800 bg-slate-900/40 p-4 text-sm text-slate-300"><p>{discovery.data.live_discovery_enabled ? `Live public employer boards: ${discovery.data.boards.join(", ") || "None configured"}. Discovery only; applications remain manual or reviewable drafts.` : "Live discovery is off. Your uploaded resume enables matching, but does not connect job sources."}</p><a href="/settings" className="mt-2 inline-block text-violet-300">Configure job sources →</a></section> : null}
    <section className="mt-4 rounded-xl border border-violet-500/20 bg-violet-500/5 p-4 text-sm text-slate-300"><p>Manual searches have no daily search-count limit. Each run checks up to 100 role-relevant listings. Public boards are cached for up to one hour and provider rate limits still apply.</p><p className="mt-2">Selected roles: {discovery.data ? discovery.data.selected_roles?.join(", ") || "None selected—choose your internship roles first." : "Loading your role preferences…"}</p><a href="/preferences" className="mt-2 inline-block text-violet-300">Review and edit all preferences →</a></section>
    {notice ? <p role="status" className="mt-4 text-sm text-slate-300">{notice}</p> : null}
    {running ? <p role="status" className="mt-4 text-sm text-violet-200">Fetching listings and checking your preferences. This may take up to two minutes; you do not need to click again.</p> : null}
    {!notice && last ? <p className="mt-4 text-sm text-slate-400">Last search: {searchMessage(last)}</p> : null}
    {last?.sources?.length ? <ul className="mt-3 space-y-1 text-xs text-slate-400">{last.sources.flatMap(source => source.boards?.length ? source.boards.map(board => <li key={source.source + board.board}>{board.board}: {board.role_matches != null ? `${board.role_matches} role matches / ` : ""}{board.listings} published internships ({board.status.replaceAll("_", " ")})</li>) : [<li key={source.source}>{source.source}: {source.listings} role-relevant listings ({source.status})</li>])}</ul> : null}
    {last?.rejection_reasons && Object.keys(last.rejection_reasons).length ? <section className="mt-4 rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 text-sm text-amber-100"><h2 className="font-medium">Why some opportunities did not qualify</h2><ul className="mt-2 space-y-1">{Object.entries(last.rejection_reasons).map(([reason, count]) => <li key={reason}>{count}: {reason}</li>)}</ul><p className="mt-2 text-xs">Your strict preferences were not relaxed. Missing salary or eligibility information is not assumed.</p></section> : null}
    <ResourceNotice loading={metrics.loading} error={metrics.error} />
    <section className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{cards.map(([label, value, Icon]) => <div key={label} className="rounded-2xl border border-slate-800/80 bg-slate-900/45 p-5"><span className="grid h-10 w-10 place-items-center rounded-xl bg-violet-500/10 text-violet-300"><Icon size={19} /></span><p className="mt-5 text-3xl font-semibold text-white">{value ?? "—"}</p><p className="mt-1 text-sm text-slate-400">{label}</p></div>)}</section>
    <section className="mt-10"><h2 className="font-semibold text-white">Matches to your mandatory preferences</h2><ResourceNotice loading={jobs.loading} error={jobs.error} empty={!jobs.data?.items.length ? "No jobs currently meet your mandatory preferences. Review your criteria and run a search; rejected or unverified discoveries are available in Jobs." : undefined} /><div className="mt-4 space-y-4">{jobs.data?.items.map(job => <JobCard key={job.id} job={displayJob(job)} onStateChange={async changes => { await apiFetch("jobs/" + job.id + "/state", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(changes) }); await jobs.refresh(); }} />)}</div><a href="/jobs" className="mt-5 inline-block text-sm text-violet-300">View job results and rejection reasons →</a></section>
  </AppShell>;
}
