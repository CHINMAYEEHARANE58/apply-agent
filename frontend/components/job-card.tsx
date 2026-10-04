"use client";

import { Bookmark, Building2, MapPin, MoreHorizontal, Sparkles } from "lucide-react";
import { useState } from "react";
import type { Job } from "../lib/types";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";

export function JobCard({ job }: { job: Job }) {
  const [saved, setSaved] = useState(false);
  const [ignored, setIgnored] = useState(false);
  if (ignored) return null;
  return <article className="rounded-2xl border border-slate-800/80 bg-slate-900/45 p-5 transition hover:border-slate-700 hover:bg-slate-900/70">
    <div className="flex gap-4"><div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-slate-700 to-slate-800 text-slate-200"><Building2 size={20} /></div><div className="min-w-0 flex-1"><div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-semibold text-white">{job.role}</h2><p className="mt-0.5 text-sm text-slate-400">{job.company}</p></div><div className="flex items-center gap-2"><div className="rounded-lg bg-emerald-500/10 px-2.5 py-1 text-sm font-semibold text-emerald-300">{job.match}% match</div><button aria-label="More options" className="text-slate-500 hover:text-white"><MoreHorizontal size={19} /></button></div></div><div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs text-slate-400"><span className="flex items-center gap-1.5"><MapPin size={14} />{job.location}</span><span>{job.duration}</span><span>{job.stipend}</span><span>{job.postedDate}</span></div></div></div>
    <div className="mt-4 grid gap-3 border-t border-slate-800 pt-4 md:grid-cols-[1fr_auto]"><div className="space-y-2"><div className="flex flex-wrap items-center gap-2"><span className="text-xs text-slate-500">Matches</span>{job.skills.map(skill => <Badge key={skill} className="border-violet-500/25 bg-violet-500/10 text-violet-200">{skill}</Badge>)}</div><div className="flex flex-wrap items-center gap-2"><span className="text-xs text-slate-500">Missing</span>{job.missingSkills.map(skill => <Badge key={skill} className="border-slate-700 text-slate-400">{skill}</Badge>)}</div></div><div className="flex flex-wrap items-end gap-2"><Button variant="outline" size="sm">View details</Button><Button size="sm"><Sparkles size={14} />Prepare</Button><Button aria-label="Save job" variant={saved ? "secondary" : "ghost"} size="icon" onClick={() => setSaved(!saved)}><Bookmark size={16} className={saved ? "fill-current" : ""} /></Button><Button variant="ghost" size="sm" onClick={() => setIgnored(true)}>Ignore</Button></div></div>
    <p className="mt-4 text-xs text-slate-500">Source: {job.source}</p>
  </article>;
}
