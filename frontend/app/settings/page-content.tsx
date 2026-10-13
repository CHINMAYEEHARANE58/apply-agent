"use client";

import { ChevronRight, CircleAlert, KeyRound, Landmark, LockKeyhole, SlidersHorizontal, UserRound } from "lucide-react";
import { AppShell } from "../../components/app-shell";
import { PageHeader } from "../../components/page-header";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";

const groups = [
  { title: "Preferences", description: "Roles, skills, locations, compensation, and availability.", icon: SlidersHorizontal },
  { title: "Account", description: "Name, email, profile, and notification preferences.", icon: UserRound },
  { title: "Security", description: "Sessions, sign-in options, and connected accounts.", icon: LockKeyhole },
  { title: "AI settings", description: "Control how drafts, tailoring, and question review work.", icon: KeyRound },
  { title: "Application limits", description: "Review mode, daily limit, and batch approval settings.", icon: Landmark },
  { title: "Job sources", description: "View permitted sources and their application capabilities.", icon: CircleAlert }
];
export default function SettingsPage() {
  return <AppShell><PageHeader eyebrow="Workspace" title="Settings" description="Manage the preferences and controls that shape your search." />
    <section className="mt-8 grid gap-3">{groups.map(group => { const Icon = group.icon; return <button key={group.title} className="flex items-center gap-4 rounded-2xl border border-slate-800/80 bg-slate-900/45 p-5 text-left transition hover:border-slate-700 hover:bg-slate-900/70"><span className="grid h-10 w-10 place-items-center rounded-xl bg-slate-800 text-violet-300"><Icon size={19} /></span><span className="min-w-0 flex-1"><span className="block font-medium text-white">{group.title}</span><span className="mt-1 block text-sm text-slate-500">{group.description}</span></span><ChevronRight size={18} className="text-slate-600" /></button>; })}</section>
    <section className="mt-10 rounded-2xl border border-rose-500/20 bg-rose-500/[0.04] p-5"><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center"><div><div className="flex items-center gap-2"><h2 className="font-medium text-rose-100">Data deletion</h2><Badge className="border-rose-500/25 bg-rose-500/10 text-rose-200">Irreversible</Badge></div><p className="mt-2 text-sm leading-6 text-slate-400">Request deletion of your profile, preferences, resume documents, and application history.</p></div><Button variant="danger">Manage data</Button></div></section>
  </AppShell>;
}
