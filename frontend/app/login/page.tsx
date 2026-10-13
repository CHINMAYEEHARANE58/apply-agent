import Link from "next/link";
import { SignIn } from "@clerk/nextjs";
import { Check, Sparkles } from "lucide-react";
import { clerkIsConfigured } from "../../lib/auth-config";

export default function LoginPage() {
  return <main className="grid min-h-screen bg-[#09090b] lg:grid-cols-2">
    <section className="hidden flex-col justify-between border-r border-slate-800 bg-gradient-to-br from-violet-900/45 via-[#11111a] to-[#09090b] p-12 lg:flex">
      <div className="flex items-center gap-2 text-lg font-semibold"><span className="grid h-8 w-8 place-items-center rounded-xl bg-violet-500"><Sparkles size={16} /></span>InternAgent</div>
      <div><p className="text-sm font-semibold uppercase tracking-[0.22em] text-violet-300">Opportunity, thoughtfully managed</p><h1 className="mt-5 max-w-xl text-5xl font-semibold leading-[1.08] tracking-tight text-white">A calmer way to find the internship that fits.</h1>
        <ul className="mt-10 space-y-4 text-sm text-slate-300">{["Discover roles matched to your preferences", "Prepare tailored materials from real experience", "Stay in control of every application"].map(item => <li key={item} className="flex items-center gap-3"><Check size={16} className="text-violet-300" />{item}</li>)}</ul>
      </div><p className="text-xs text-slate-600">Built around your decisions, not automation shortcuts.</p>
    </section>
    <section className="mx-auto flex w-full max-w-md flex-col justify-center px-6 py-12">
      <Link href="/" className="mb-10 text-lg font-semibold lg:hidden">InternAgent</Link>
      <p className="text-sm font-medium text-violet-300">Welcome back</p><h2 className="mt-3 text-3xl font-semibold tracking-tight text-white">Sign in to InternAgent</h2>
      <p className="mb-8 mt-3 text-sm leading-6 text-slate-400">Continue to your personal internship workspace.</p>
      {clerkIsConfigured() ? <SignIn routing="hash" signUpUrl="/sign-up" fallbackRedirectUrl="/dashboard" appearance={{ variables: { colorPrimary: "#8b5cf6", colorBackground: "#101016", colorForeground: "#f1f5f9", colorInputForeground: "#f1f5f9" }, elements: { rootBox: "w-full", cardBox: "w-full", card: "border border-slate-800 shadow-none", footerActionLink: "text-violet-300" } }} /> : <div role="status" className="rounded-2xl border border-slate-800 bg-slate-900/50 p-5 text-sm leading-6 text-slate-300">Sign-in will be available once this workspace&apos;s authentication is configured.</div>}
      <p className="mt-8 text-center text-xs leading-5 text-slate-600">Your account, preferences, and resume stay private to your workspace.</p>
    </section>
  </main>;
}
