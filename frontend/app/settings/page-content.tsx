"use client";
import { useEffect, useState } from "react";
import { AppShell } from "../../components/app-shell";
import { PageHeader } from "../../components/page-header";
import { ResourceNotice } from "../../components/resource-notice";
import { Button } from "../../components/ui/button";
import { apiFetch } from "../../lib/api";
import { type StoredSettings, useResource } from "../../lib/resources";

export default function SettingsPage() {
  const resource = useResource<StoredSettings>("settings/me");
  const [form, setForm] = useState<StoredSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");
  useEffect(() => { if (resource.data) setForm(resource.data); }, [resource.data]);
  function sourceChecked(source: string, checked: boolean) {
    if (!form) return;
    setForm({ ...form, enabled_sources: checked ? [...new Set([...form.enabled_sources, source])] : form.enabled_sources.filter(value => value !== source) });
  }
  async function save() {
    if (!form) return;
    setSaving(true); setNotice("");
    try {
      const values = Object.fromEntries(Object.entries(form).filter(([key]) => key !== "user_id"));
      await apiFetch("settings/me", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(values) });
      setNotice("Settings saved. Your preferences and scheduler now use these values.");
      await resource.refresh();
    } catch (error) { setNotice(error instanceof Error ? error.message : "Unable to save settings."); }
    finally { setSaving(false); }
  }
  return <AppShell><PageHeader eyebrow="Workspace" title="Settings" description="Private, persistent controls for your daily search." />
    <p className="mt-4 text-sm text-slate-400">The daily schedule and evaluation allowance apply to background searches. Manual searches have no daily search-count limit and check up to 100 role-relevant listings per run. Daily application preparation and submission limits apply to both.</p>
    <ResourceNotice loading={resource.loading} error={resource.error} />
    {notice ? <p role="status" className="mt-4 text-sm text-slate-300">{notice}</p> : null}
    {form ? <section className="mt-8 rounded-2xl border border-slate-800/80 bg-slate-900/45 p-6"><h2 className="font-semibold">Preferences and application limits</h2>
      <div className="mt-6 grid gap-5 sm:grid-cols-2">
        <label className="text-sm">Search time<input aria-label="Search time" type="time" value={form.search_time} onChange={e => setForm({ ...form, search_time: e.target.value })} className="mt-2 block w-full rounded-xl border border-slate-700 bg-slate-950 p-3" /></label>
        <label className="text-sm">Timezone<input aria-label="Timezone" value={form.timezone} onChange={e => setForm({ ...form, timezone: e.target.value })} className="mt-2 block w-full rounded-xl border border-slate-700 bg-slate-950 p-3" /></label>
        {([["minimum_match_score", "Minimum match score", 100], ["max_daily_applications", "Maximum submitted applications daily", 50], ["maximum_jobs_evaluated_daily", "Maximum jobs evaluated daily (scheduled)", 10000], ["maximum_applications_prepared_daily", "Maximum applications prepared daily", 1000]] as const).map(([key, label, maximum]) => <label key={key} className="text-sm">{label}<input aria-label={label} type="number" min={0} max={maximum} value={form[key]} onChange={e => setForm({ ...form, [key]: Number(e.target.value) })} className="mt-2 block w-full rounded-xl border border-slate-700 bg-slate-950 p-3" /></label>)}
        <label className="text-sm">Application mode<select aria-label="Application mode" value={form.application_mode} onChange={e => setForm({ ...form, application_mode: e.target.value as StoredSettings["application_mode"] })} className="mt-2 block w-full rounded-xl border border-slate-700 bg-slate-950 p-3"><option value="review">Review Every Application</option><option value="batch">Batch Approval</option><option value="authorized-auto">Authorized integrations only</option></select></label>
      </div>
      <div className="mt-6 space-y-4">{([["search_enabled", "Daily search enabled"], ["email_notifications", "Email notification preference"], ["application_notifications", "Application notification preference"]] as const).map(([key, label]) => <label key={key} className="flex items-center gap-3 text-sm"><input type="checkbox" checked={form[key]} onChange={e => setForm({ ...form, [key]: e.target.checked })} />{label}</label>)}</div>
      <div className="mt-7 border-t border-slate-800 pt-5"><h2 className="font-semibold">Job sources</h2><label className="mt-3 flex gap-3 text-sm"><input type="checkbox" checked={form.enabled_sources.includes("catalog")} onChange={e => sourceChecked("catalog", e.target.checked)} />Imported catalogue (manual handoff only)</label><label className="mt-3 flex gap-3 text-sm"><input type="checkbox" checked={form.enabled_sources.includes("greenhouse_public")} onChange={e => sourceChecked("greenhouse_public", e.target.checked)} />Public employer boards (Greenhouse API)</label><p className="mt-3 text-sm text-slate-400">Reads published internships at Cloudflare, Databricks, Figma and Stripe through their public job-board API. No resume or personal information is sent to these sources. Applications remain manual; no submitter or email delivery provider is configured. These settings do not grant platform permissions.</p></div>
      <Button className="mt-7" disabled={saving} onClick={() => void save()}>{saving ? "Saving…" : "Save settings"}</Button><a href="/preferences" className="ml-5 text-sm text-violet-300">Edit internship preferences →</a>
    </section> : null}
    <section className="mt-8 rounded-2xl border border-slate-800 p-5"><h2 className="font-semibold">Account and security</h2><p className="mt-2 text-sm text-slate-400">Sign-in and sessions are managed by Clerk through your account menu. Resume facts cannot be replaced by AI settings.</p></section>
  </AppShell>;
}
