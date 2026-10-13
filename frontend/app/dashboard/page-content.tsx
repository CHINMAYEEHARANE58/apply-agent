"use client";

import { ArrowUpRight, CalendarDays, FilePenLine, MessageSquare, Send, Sparkles, Target } from "lucide-react";
import { AppShell } from "../../components/app-shell";
import { JobCard } from "../../components/job-card";
import { PageHeader } from "../../components/page-header";
import { Button } from "../../components/ui/button";
import { dashboardMetrics, jobs } from "../../lib/mock-data";

const icons = { Sparkles, Target, FilePenLine, Send, CalendarDays, MessageSquare };

export default function DashboardPage() {
  return <AppShell><PageHeader eyebrow="Overview" title="Your internship search, organized." description="A focused view of new opportunities and the applications that need your attention." actions={<Button><Sparkles size={16} />Run job search</Button>} />
    <section className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{dashboardMetrics.map(metric => { const Icon = icons[metric.icon as keyof typeof icons]; return <div key={metric.label} className="rounded-2xl border border-slate-800/80 bg-slate-900/45 p-5"><div className="flex items-start justify-between"><span className="grid h-10 w-10 place-items-center rounded-xl bg-violet-500/10 text-violet-300"><Icon size={19} /></span><span className="text-xs text-emerald-400">{metric.change}</span></div><p className="mt-5 text-3xl font-semibold text-white">{metric.value}</p><p className="mt-1 text-sm text-slate-400">{metric.label}</p></div>; })}</section>
    <section className="mt-10 grid gap-6 xl:grid-cols-[1.45fr_0.8fr]"><div><div className="mb-4 flex items-center justify-between"><div><h2 className="font-semibold text-white">Top matches</h2><p className="mt-1 text-sm text-slate-500">Fresh opportunities matched to your preferences.</p></div><Button variant="ghost" size="sm">View all <ArrowUpRight size={14} /></Button></div><div className="space-y-4">{jobs.slice(0, 2).map(job => <JobCard key={job.id} job={job} />)}</div></div><div className="rounded-2xl border border-slate-800/80 bg-slate-900/45 p-5"><div className="flex items-center justify-between"><div><h2 className="font-semibold">Your weekly activity</h2><p className="mt-1 text-sm text-slate-500">A steady search is paying off.</p></div><span className="text-sm font-medium text-emerald-400">+24%</span></div><div className="mt-8 flex h-36 items-end justify-between gap-2">{[40, 58, 34, 76, 62, 88, 70].map((height, index) => <div key={index} className="flex flex-1 flex-col items-center gap-2"><div className="w-full rounded-t-md bg-gradient-to-t from-violet-600 to-violet-400/70" style={{ height: `${height}%` }} /><span className="text-[10px] text-slate-600">{["M", "T", "W", "T", "F", "S", "S"][index]}</span></div>)}</div><div className="mt-8 border-t border-slate-800 pt-5"><p className="text-sm font-medium text-slate-200">Next up</p><p className="mt-2 text-sm leading-6 text-slate-400">Review the prepared Figma application before it moves into your approval queue.</p><Button className="mt-4 w-full" variant="secondary">Review application</Button></div></div></section>
  </AppShell>;
}
