import { Card } from "../components/ui/card";

const foundationItems = [
  ["Candidate profile", "Preferences and encrypted resume boundary"],
  ["Discover", "Permitted source adapters and normalized listings"],
  ["Match", "Explainable filters and score evidence"],
  ["Prepare", "Evidence-bound resume and letter drafting"],
  ["Apply", "Deterministic policy gate and application tracking"]
];

export default function DashboardPage() {
  return (
    <main className="mx-auto min-h-screen max-w-6xl px-6 py-16">
      <p className="mb-3 text-sm font-semibold uppercase tracking-[0.22em] text-cyan-400">InternAgent</p>
      <h1 className="max-w-3xl text-4xl font-semibold tracking-tight sm:text-5xl">Your internship search, with clear control at every step.</h1>
      <p className="mt-5 max-w-2xl text-lg leading-8 text-slate-400">The foundation is active. Set your preferences, add your master resume, then review matches before any permitted application action.</p>
      <section className="mt-12 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {foundationItems.map(([title, detail]) => <Card key={title}><h2 className="font-medium">{title}</h2><p className="mt-2 text-sm leading-6 text-slate-400">{detail}</p></Card>)}
      </section>
      <Card className="mt-4 border-cyan-900/70 bg-cyan-950/20">
        <h2 className="font-medium text-cyan-200">Application safety gate</h2>
        <p className="mt-2 text-sm leading-6 text-slate-300">InternAgent submits only via sources whose authorization and application capability have both been verified. Every other listing stays in an assisted, user-controlled flow.</p>
      </Card>
    </main>
  );
}
