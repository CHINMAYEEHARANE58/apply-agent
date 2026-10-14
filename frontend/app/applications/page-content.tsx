"use client";
import { useEffect, useRef, useState } from "react";
import { AppShell } from "../../components/app-shell";
import { PageHeader } from "../../components/page-header";
import { ResourceNotice } from "../../components/resource-notice";
import { Button } from "../../components/ui/button";
import { apiFetch } from "../../lib/api";
import { type Page, type StoredApplication, type StoredJob, type StoredResume, downloadResume, useResource } from "../../lib/resources";

export default function ApplicationsPage() {
  const [offset, setOffset] = useState(0);
  const resource = useResource<Page<StoredApplication>>("applications?limit=20&offset=" + offset);
  const [jobs, setJobs] = useState<Record<string, StoredJob>>({});
  const [selected, setSelected] = useState<StoredApplication | null>(null);
  const [resume, setResume] = useState<StoredResume | null>(null);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const reviewRequest = useRef(0);
  useEffect(() => {
    let active = true;
    if (resource.data) void Promise.all(resource.data.items.map(async application => [application.job_id, await apiFetch<StoredJob>("jobs/" + application.job_id)] as const)).then(entries => { if (active) setJobs(Object.fromEntries(entries)); }).catch(error => { if (active) setNotice(error.message); });
    return () => { active = false; };
  }, [resource.data]);
  async function open(application: StoredApplication) {
    const requestId = ++reviewRequest.current;
    setSelected(application); setResume(null); setNotice("");
    if (application.resume_id) {
      try { const loaded = await apiFetch<StoredResume>("resumes/" + application.resume_id); if (requestId === reviewRequest.current && loaded.id === application.resume_id) setResume(loaded); }
      catch (error) { if (requestId === reviewRequest.current) setNotice(error instanceof Error ? error.message : "Unable to load resume."); }
    }
  }
  async function approve() {
    if (!selected || !resume || resume.id !== selected.resume_id) return;
    setBusy(true); setNotice("");
    try {
      await apiFetch("applications/" + selected.id + "/approve", { method: "POST" });
      setSelected(null); setNotice("Application package approved and prepared for manual completion. Nothing was submitted.");
      await resource.refresh();
    } catch (error) { setNotice(error instanceof Error ? error.message : "Approval failed."); }
    finally { setBusy(false); }
  }
  return <AppShell><PageHeader eyebrow="Track" title="Applications" description="Your persisted applications. No automatic submission integration is enabled." />
    <ResourceNotice loading={resource.loading} error={resource.error} empty={!resource.data?.items.length ? "No applications yet. Upload a resume and run your search to prepare strong matches." : undefined} />
    {notice ? <p role="status" className="mt-4 text-sm text-slate-300">{notice}</p> : null}
    <section className="mt-8 divide-y divide-slate-800 overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/45">{resource.data?.items.map(application => <article key={application.id} className="flex flex-wrap items-center gap-4 p-5"><div className="min-w-0 flex-1"><p className="font-medium">{jobs[application.job_id]?.title || "Loading role…"}</p><p className="mt-1 text-sm text-slate-400">{jobs[application.job_id]?.company}</p></div><span className="text-sm text-violet-200">{application.status.replaceAll("_", " ")}</span><Button variant="outline" onClick={() => void open(application)}>Open</Button></article>)}</section>
    <div className="mt-5 flex gap-3"><Button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>Previous</Button><Button disabled={!resource.data || offset + 20 >= resource.data.total} onClick={() => setOffset(offset + 20)}>Next</Button></div>
    {selected ? <section aria-label="Application review" className="mt-8 rounded-2xl border border-violet-500/30 bg-slate-900 p-6"><h2 className="font-semibold">Review application package</h2><p className="mt-3 text-sm text-amber-200">Verify legal, visa, compensation and availability answers yourself. Unknown sensitive answers are never guessed.</p><h3 className="mt-5 font-medium">Cover letter</h3><p className="mt-3 whitespace-pre-wrap text-sm text-slate-300">{selected.cover_letter || "No letter stored."}</p><h3 className="mt-5 font-medium">Suggested recruiter message (not sent)</h3><p className="mt-3 whitespace-pre-wrap text-sm text-slate-300">{selected.application_message || "No message stored."}</p><h3 className="mt-5 font-medium">Resume facts</h3><ul className="mt-3 list-inside list-disc space-y-2 text-sm text-slate-300">{resume?.generated_bullets?.map((bullet, index) => <li key={index}>{bullet.text}</li>)}</ul><div className="mt-6 flex flex-wrap gap-3"><Button disabled={busy || !resume || selected.status !== "awaiting_approval"} onClick={() => void approve()}>Verify and approve package</Button>{resume?.approval_status === "approved" ? <Button variant="outline" onClick={() => void downloadResume(resume.id, "tailored-resume.pdf").catch(error => setNotice(error.message))}>Download resume</Button> : null}{jobs[selected.job_id] ? <a href={jobs[selected.job_id].job_url} target="_blank" rel="noopener noreferrer" className="rounded-xl border border-slate-700 px-4 py-3 text-sm">Open Application</a> : null}<Button variant="ghost" onClick={() => setSelected(null)}>Close</Button></div></section> : null}
  </AppShell>;
}
