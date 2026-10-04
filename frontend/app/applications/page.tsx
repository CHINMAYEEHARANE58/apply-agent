"use client";

import { CheckCircle2, Clock3, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { AppShell } from "../../components/app-shell";
import { PageHeader } from "../../components/page-header";
import { StatusBadge } from "../../components/status-badge";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { applications } from "../../lib/mock-data";
import type { ApplicationStatus } from "../../lib/types";

const statuses: ApplicationStatus[] = ["Discovered", "Matched", "Prepared", "Awaiting Approval", "Submitted", "Assessment", "Interview", "Rejected", "Offer", "Withdrawn"];
export default function ApplicationsPage() {
  const [selected, setSelected] = useState<ApplicationStatus | "All">("All");
  const filtered = useMemo(() => selected === "All" ? applications : applications.filter(application => application.status === selected), [selected]);
  return <AppShell><PageHeader eyebrow="Track" title="Applications" description="Every opportunity, from discovery through offer—kept in one calm workspace." actions={<Button variant="outline"><CheckCircle2 size={16} />Review approvals</Button>} />
    <div className="mt-8 flex gap-2 overflow-x-auto pb-2"><button onClick={() => setSelected("All")} className={`whitespace-nowrap rounded-full px-3 py-1.5 text-xs font-medium ${selected === "All" ? "bg-violet-500 text-white" : "bg-slate-800 text-slate-400"}`}>All</button>{statuses.map(status => <button key={status} onClick={() => setSelected(status)} className={`whitespace-nowrap rounded-full px-3 py-1.5 text-xs font-medium ${selected === status ? "bg-violet-500 text-white" : "bg-slate-800 text-slate-400"}`}>{status}</button>)}</div>
    <section className="mt-5 overflow-hidden rounded-2xl border border-slate-800/80 bg-slate-900/45"><div className="flex items-center justify-between border-b border-slate-800 px-5 py-4"><p className="text-sm text-slate-400"><span className="font-medium text-white">{filtered.length}</span> applications</p><Button size="sm" variant="ghost"><Search size={14} />Search</Button></div><div className="divide-y divide-slate-800/80">{filtered.map(application => <div key={application.id} className="flex flex-col gap-4 p-5 transition hover:bg-slate-800/30 sm:flex-row sm:items-center"><div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-slate-800 text-sm font-semibold text-slate-300">{application.company.slice(0, 1)}</div><div className="min-w-0 flex-1"><p className="font-medium text-white">{application.role}</p><p className="mt-1 text-sm text-slate-500">{application.company} <span className="px-1">·</span>{application.updatedAt}</p></div><div className="flex items-center gap-3"><Badge className="border-emerald-500/20 bg-emerald-500/10 text-emerald-300">{application.match}% match</Badge><StatusBadge status={application.status} /><Button variant="ghost" size="sm">Open</Button></div></div>)}</div></section>
    <div className="mt-6 flex items-center gap-3 rounded-2xl border border-amber-500/20 bg-amber-500/[0.06] p-4 text-sm text-amber-100"><Clock3 size={18} className="shrink-0 text-amber-300" />3 prepared applications are waiting for your approval. InternAgent never submits an application outside your selected mode and an authorized integration.</div>
  </AppShell>;
}
