"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell, BriefcaseBusiness, FileText, LayoutDashboard, LogOut, Menu, Search, Settings, Sparkles, X } from "lucide-react";
import { type ReactNode, useState } from "react";
import { cn } from "../lib/utils";

const navigation = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/jobs", label: "Jobs", icon: Search },
  { href: "/applications", label: "Applications", icon: BriefcaseBusiness },
  { href: "/resumes", label: "Resumes", icon: FileText },
  { href: "/settings", label: "Settings", icon: Settings }
];

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return <nav className="space-y-1">{navigation.map(({ href, label, icon: Icon }) => {
    const active = pathname === href;
    return <Link href={href} key={href} onClick={onNavigate} className={cn("flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition", active ? "bg-violet-500/15 text-violet-200" : "text-slate-400 hover:bg-slate-800/70 hover:text-slate-100")}><Icon size={18} />{label}</Link>;
  })}</nav>;
}

export function AppShell({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return <div className="min-h-screen bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-violet-950/25 via-[#09090b] to-[#09090b]">
    {open ? <button aria-label="Close navigation" className="fixed inset-0 z-40 bg-black/70 lg:hidden" onClick={() => setOpen(false)} /> : null}
    <aside className={cn("fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-slate-800/80 bg-[#0c0c10] p-4 transition-transform lg:translate-x-0", open ? "translate-x-0" : "-translate-x-full")}>
      <div className="mb-8 flex items-center justify-between px-2"><Link href="/dashboard" className="flex items-center gap-2 text-lg font-semibold tracking-tight text-white"><span className="grid h-8 w-8 place-items-center rounded-xl bg-violet-500 shadow-lg shadow-violet-900/40"><Sparkles size={16} /></span>InternAgent</Link><button aria-label="Close navigation" className="text-slate-400 lg:hidden" onClick={() => setOpen(false)}><X size={20} /></button></div>
      <NavItems onNavigate={() => setOpen(false)} />
      <div className="mt-auto rounded-2xl border border-violet-500/15 bg-violet-500/[0.07] p-4"><p className="text-sm font-medium text-violet-100">Daily search is ready</p><p className="mt-1 text-xs leading-5 text-slate-400">Your next scheduled search runs tomorrow at 9:00 AM.</p></div>
      <Link href="/login" className="mt-4 flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-slate-500 hover:bg-slate-800 hover:text-slate-200"><LogOut size={18} />Sign out</Link>
    </aside>
    <div className="lg:pl-72"><header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-slate-800/70 bg-[#09090b]/75 px-5 backdrop-blur lg:px-10"><button aria-label="Open navigation" className="text-slate-300 lg:hidden" onClick={() => setOpen(true)}><Menu size={22} /></button><div className="hidden text-sm text-slate-500 sm:block">Good morning, Aarav <span className="text-slate-300">·</span> Let&apos;s find your next opportunity.</div><div className="ml-auto flex items-center gap-3"><button aria-label="Notifications" className="relative grid h-9 w-9 place-items-center rounded-xl text-slate-400 hover:bg-slate-800"><Bell size={18} /><span className="absolute right-2.5 top-2.5 h-1.5 w-1.5 rounded-full bg-violet-400" /></button><div className="grid h-9 w-9 place-items-center rounded-full bg-gradient-to-br from-violet-400 to-fuchsia-500 text-xs font-bold text-white">AS</div></div></header>
      <main className="mx-auto max-w-7xl px-5 py-8 lg:px-10 lg:py-10">{children}</main>
    </div>
  </div>;
}
