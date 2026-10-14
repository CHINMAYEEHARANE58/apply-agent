"use client";
import { FileText } from "lucide-react";
import { useState } from "react";
import { AppShell } from "../../components/app-shell";
import { PageHeader } from "../../components/page-header";
import { ResourceNotice } from "../../components/resource-notice";
import { Button } from "../../components/ui/button";
import { apiFetch } from "../../lib/api";
import { type Page, type StoredResume, downloadResume, useResource } from "../../lib/resources";

export default function ResumesPage() {
  const master = useResource<Page<StoredResume>>("resumes?type=master&limit=10");
  const [offset, setOffset] = useState(0);
  const tailored = useResource<Page<StoredResume>>("resumes?type=tailored&limit=20&offset=" + offset);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [review, setReview] = useState<StoredResume | null>(null);
  async function upload(file?: File) {
    if (!file) return;
    setBusy(true); setNotice("");
    try {
      const body = new FormData(); body.append("file", file);
      await apiFetch("resumes/upload", { method: "POST", body });
      setNotice("New master version uploaded and parsed. Historical versions were preserved.");
      await master.refresh();
    } catch (error) { setNotice(error instanceof Error ? error.message : "Upload failed."); }
    finally { setBusy(false); }
  }
  async function approve(resume: StoredResume) {
    setBusy(true); setNotice("");
    try { await apiFetch("resumes/" + resume.id + "/approve", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }); await tailored.refresh(); setReview(null); setNotice("Factual verification passed; this resume version is approved."); }
    catch (error) { setNotice(error instanceof Error ? error.message : "Approval failed."); }
    finally { setBusy(false); }
  }
  return <AppShell><PageHeader eyebrow="Documents" title="Your resumes" description="Immutable master versions and source-backed drafts stored privately." />
    <label className="mt-7 inline-flex cursor-pointer rounded-xl border border-slate-700 px-4 py-3 text-sm">Upload new master version<input aria-label="Upload new master version" disabled={busy} className="sr-only" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={event => { void upload(event.target.files?.[0]); event.target.value = ""; }} /></label>
    {notice ? <p role="status" className="mt-4 text-sm text-slate-300">{notice}</p> : null}
    <section className="mt-8"><h2 className="font-semibold">Master resumes</h2><ResourceNotice loading={master.loading} error={master.error} empty={!master.data?.items.length ? "Upload your PDF or DOCX master resume (maximum 5 MB)." : undefined} />
      <div className="mt-4 space-y-3">{master.data?.items.map(resume => <article key={resume.id} className="flex flex-wrap items-center gap-4 rounded-2xl border border-violet-500/25 bg-slate-900/45 p-5"><FileText className="text-violet-300" /><div className="min-w-0 flex-1"><p className="break-words">{resume.original_filename} · v{resume.version}</p><p className="mt-1 text-xs text-slate-400">{new Date(resume.created_at).toLocaleDateString()} · immutable source of truth</p></div><Button variant="outline" onClick={() => void downloadResume(resume.id, resume.original_filename || "master-resume.pdf").catch(error => setNotice(error.message))}>Download</Button></article>)}</div>
    </section>
    <section className="mt-10"><h2 className="font-semibold">Tailored resumes</h2><ResourceNotice loading={tailored.loading} error={tailored.error} empty={!tailored.data?.items.length ? "Run your job search to prepare strong-match drafts from your master resume." : undefined} />
      <div className="mt-4 grid gap-4 lg:grid-cols-2">{tailored.data?.items.map(resume => <article key={resume.id} className="rounded-2xl border border-slate-800 bg-slate-900/45 p-5"><p className="font-medium">Tailored resume · {resume.approval_status}</p><p className="mt-2 text-xs text-slate-400">{new Date(resume.created_at).toLocaleDateString()} · {resume.generated_bullets?.length || 0} cited statements</p><div className="mt-4 flex gap-3"><Button variant="outline" onClick={() => setReview(resume)}>Review facts</Button><Button disabled={resume.approval_status !== "approved"} onClick={() => void downloadResume(resume.id, "tailored-resume.pdf").catch(error => setNotice(error.message))}>Download PDF</Button></div></article>)}</div>
      <div className="mt-5 flex gap-3"><Button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>Previous</Button><Button disabled={!tailored.data || offset + 20 >= tailored.data.total} onClick={() => setOffset(offset + 20)}>Next</Button></div>
    </section>
    {review ? <section aria-label="Resume factual review" className="mt-8 rounded-2xl border border-violet-500/30 bg-slate-900 p-6"><h2 className="font-semibold">Review source-backed statements</h2><ul className="mt-4 space-y-3">{review.generated_bullets?.map((bullet, index) => <li key={index} className="text-sm text-slate-300">{bullet.text}<p className="mt-1 break-all text-xs text-slate-500">Evidence: {bullet.supporting_fact_ids.join(", ")}</p></li>)}</ul><div className="mt-5 flex gap-3"><Button disabled={busy} onClick={() => void approve(review)}>Verify and approve resume</Button><Button variant="ghost" onClick={() => setReview(null)}>Close</Button></div></section> : null}
  </AppShell>;
}
