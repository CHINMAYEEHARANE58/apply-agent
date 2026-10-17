"use client";

import Link from "next/link";
import { Check, Save } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import { AppShell } from "../../components/app-shell";
import { PageHeader } from "../../components/page-header";
import { PreferenceInput, PreferenceList, PreferenceSection, PreferenceToggle, preferenceInputClass } from "../../components/preference-fields";
import { ResourceNotice } from "../../components/resource-notice";
import { Button } from "../../components/ui/button";
import { apiFetch } from "../../lib/api";
import { type EligibilityPreferences, type PreferenceDraft, type PreferenceEditor, ROLE_OPTIONS, parseList, preferenceDraft, preferencePayload } from "../../lib/preferences";
import { useResource } from "../../lib/resources";

export default function PreferencesPage() {
  const resource = useResource<PreferenceEditor>("preferences/editor");
  const [form, setForm] = useState<PreferenceDraft | null>(null);
  const [eligibility, setEligibility] = useState<EligibilityPreferences | null>(null);
  const [baseline, setBaseline] = useState("");
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    if (resource.data) {
      const draft = preferenceDraft(resource.data.preferences);
      setForm(draft); setEligibility(resource.data.eligibility);
      setBaseline(JSON.stringify([draft, resource.data.eligibility]));
    }
  }, [resource.data]);
  const dirty = form !== null && JSON.stringify([form, eligibility]) !== baseline;
  function field<K extends keyof PreferenceDraft>(key: K, value: PreferenceDraft[K]) { setForm(previous => previous ? { ...previous, [key]: value } : previous); setNotice(""); }
  async function save(event: FormEvent) {
    event.preventDefault();
    if (!form || saving) return;
    setError(""); setNotice("");
    let preferences;
    try { preferences = preferencePayload(form); } catch (problem) { setError(problem instanceof Error ? problem.message : "Check your preferences."); return; }
    setSaving(true);
    try {
      const saved = await apiFetch<PreferenceEditor>("preferences/editor", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ preferences, eligibility }) });
      const next = preferenceDraft(saved.preferences);
      setForm(next); setEligibility(saved.eligibility); setBaseline(JSON.stringify([next, saved.eligibility]));
      setNotice("Preferences saved. Your existing resume is unchanged. Run a new search to recalculate matches with these requirements.");
    } catch (problem) { setError(problem instanceof Error ? problem.message : "Unable to save your preferences. Your edits are still here."); }
    finally { setSaving(false); }
  }
  return <AppShell><PageHeader eyebrow="Your search criteria" title="Internship preferences" description="Review and edit the requirements you supplied during onboarding. You do not need to upload your resume again." actions={<Button type="submit" form="internship-preferences" disabled={!dirty || saving}><Save size={16} />{saving ? "Saving…" : "Save preferences"}</Button>} />
    <ResourceNotice loading={resource.loading} error={resource.error} />
    {resource.error ? <Button className="mt-3" variant="outline" onClick={() => void resource.refresh()}>Retry loading preferences</Button> : null}
    {notice ? <p role="status" className="mt-5 rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-4 text-sm text-emerald-200">{notice} <Link href="/dashboard" className="underline">Go to search →</Link></p> : null}
    {error ? <p role="alert" className="mt-5 rounded-xl border border-rose-500/20 bg-rose-500/10 p-4 text-sm text-rose-200">{error}</p> : null}
    {form ? <form id="internship-preferences" onSubmit={event => void save(event)} className="mt-7 space-y-6">
      <nav aria-label="Preference sections" className="flex flex-wrap gap-2">{[["roles", "Roles"], ["location", "Location"], ["duration", "Duration & dates"], ["compensation", "Compensation"], ["companies", "Companies"], ["eligibility", "Eligibility"], ["applications", "Applications"]].map(([id, label]) => <a key={id} href={`#${id}`} className="rounded-lg border border-slate-800 px-3 py-2 text-xs text-slate-300 hover:border-violet-400">{label}</a>)}</nav>
      <div className="rounded-xl border border-violet-500/20 bg-violet-500/5 p-4 text-sm leading-6 text-slate-300"><p>Your saved choices are shown below. Blank optional fields mean no preference—not zero. Changing requirements invalidates old match scores until your next search.</p><p className="mt-2">Missing stipend/currency data cannot satisfy a strict minimum. Countries, states and cities are separate mandatory checks for non-remote roles. Preferred industries, companies and start dates are saved, but the current public-board integration does not yet use these as matching criteria. Desired skills never become verified resume facts.</p></div>
      <PreferenceSection id="roles" title="Roles and technologies" description="Select the internships you actually want. Add custom roles or technologies below.">
        <div className="sm:col-span-2 flex flex-wrap gap-2">{ROLE_OPTIONS.map(role => <button type="button" aria-pressed={parseList(form.roles).includes(role)} key={role} onClick={() => { const roles = parseList(form.roles); field("roles", (roles.includes(role) ? roles.filter(value => value !== role) : [...roles, role]).join(", ")); }} className={`rounded-xl border px-3 py-2 text-sm ${parseList(form.roles).includes(role) ? "border-violet-400 bg-violet-500/15 text-violet-100" : "border-slate-700 text-slate-400"}`}>{parseList(form.roles).includes(role) ? <Check className="mr-1 inline" size={14} /> : null}{role}</button>)}</div>
        <PreferenceList label="Selected and custom roles" value={form.roles} onChange={value => field("roles", value)} hint="At least one role is required. Remove roles you no longer want." />
        <PreferenceList label="Preferred technologies and skills" value={form.skills} onChange={value => field("skills", value)} placeholder="Python, React, SQL" />
      </PreferenceSection>
      <PreferenceSection id="location" title="Location and work arrangement" description="These are internship destinations, not your current address. Multiple cities are alternatives; country, state and city groups are combined.">
        <PreferenceList label="Preferred countries" value={form.preferred_countries} onChange={value => field("preferred_countries", value)} placeholder="India" />
        <PreferenceList label="Preferred states or regions" value={form.preferred_states} onChange={value => field("preferred_states", value)} />
        <PreferenceList label="Preferred cities" value={form.preferred_cities} onChange={value => field("preferred_cities", value)} placeholder="Mumbai, Bengaluru" />
        <PreferenceList label="Other mandatory location text" value={form.preferred_locations} onChange={value => field("preferred_locations", value)} hint="Legacy/general location entries from earlier setup. Clear these if they duplicate or conflict with your chosen cities." />
        <PreferenceToggle label="Allow remote internships" checked={form.remote_allowed} onChange={value => field("remote_allowed", value)} />
        <PreferenceToggle label="Allow hybrid internships" checked={form.hybrid_allowed} onChange={value => field("hybrid_allowed", value)} />
        <PreferenceToggle label="Allow onsite internships" checked={form.onsite_allowed} onChange={value => field("onsite_allowed", value)} />
        {eligibility ? <PreferenceToggle label="Willing to relocate" checked={eligibility.relocation_allowed} onChange={value => { setEligibility({ ...eligibility, relocation_allowed: value }); setNotice(""); }} /> : null}
      </PreferenceSection>
      <PreferenceSection id="duration" title="Duration and availability" description="Known durations must fit your range. Start dates are saved for future integrations; current boards do not provide a reliable structured start window.">
        <PreferenceInput label="Minimum duration" type="number" min={1} max={104} value={form.min_duration} onChange={event => field("min_duration", event.target.value)} hint="Leave blank for no minimum." />
        <PreferenceInput label="Maximum duration" type="number" min={1} max={104} value={form.max_duration} onChange={event => field("max_duration", event.target.value)} hint="Leave blank for no maximum." />
        <label className="text-sm text-slate-300">Duration unit<select value={form.duration_unit} onChange={event => field("duration_unit", event.target.value as "weeks" | "months")} className={preferenceInputClass}><option value="weeks">Weeks</option><option value="months">Months</option></select></label>
        <div className="hidden sm:block" />
        <PreferenceInput label="Earliest start date" type="date" value={form.earliest_start_date || ""} onChange={event => field("earliest_start_date", event.target.value || null)} />
        <PreferenceInput label="Latest start date" type="date" value={form.latest_start_date || ""} onChange={event => field("latest_start_date", event.target.value || null)} />
      </PreferenceSection>
      <PreferenceSection id="compensation" title="Compensation" description="The minimum is strict. Unknown pay or a different currency will not be treated as meeting it. No exchange rate or hourly/monthly conversion is guessed.">
        <PreferenceInput label="Minimum stipend" type="number" min="0" step="0.01" value={form.minimum_stipend} onChange={event => field("minimum_stipend", event.target.value)} hint="Leave blank to remove the strict pay minimum." />
        <label className="text-sm text-slate-300">Currency<select value={form.currency || ""} onChange={event => field("currency", event.target.value || null)} className={preferenceInputClass}><option value="">Not specified</option>{[...new Set(["INR", "USD", "EUR", "GBP", "CAD", "AUD", "SGD", ...(form.currency ? [form.currency] : [])])].map(currency => <option key={currency}>{currency}</option>)}</select></label>
        <label className="text-sm text-slate-300">Compensation period<select value={form.compensation_period || ""} onChange={event => field("compensation_period", (event.target.value || null) as "monthly" | "hourly" | null)} className={preferenceInputClass}><option value="">Not specified</option><option value="monthly">Monthly</option><option value="hourly">Hourly</option></select></label>
        <PreferenceToggle label="Allow unpaid internships" checked={form.allow_unpaid} onChange={value => field("allow_unpaid", value)} />
        {form.allow_unpaid && Number(form.minimum_stipend) > 0 ? <p className="text-sm text-amber-200 sm:col-span-2">Your positive minimum still excludes unpaid internships. Clear or lower it if you want unpaid roles considered.</p> : null}
      </PreferenceSection>
      <PreferenceSection id="companies" title="Industries, companies and exclusions" description="Exclusions are enforced during matching. Preferred industries and companies are stored preferences, not yet enforced by the current public-board adapter.">
        <PreferenceList label="Preferred industries" value={form.preferred_industries} onChange={value => field("preferred_industries", value)} />
        <PreferenceList label="Preferred companies" value={form.preferred_companies} onChange={value => field("preferred_companies", value)} />
        <PreferenceList label="Excluded companies" value={form.excluded_companies} onChange={value => field("excluded_companies", value)} />
        <PreferenceList label="Excluded keywords" value={form.excluded_keywords} onChange={value => field("excluded_keywords", value)} />
      </PreferenceSection>
      {eligibility ? <PreferenceSection id="eligibility" title="Eligibility answers" description="Only provide answers you know to be accurate. Unknown legal or visa information is never guessed; your full profile and resume are not overwritten.">
        <PreferenceInput label="Work authorization" maxLength={200} value={eligibility.work_authorization || ""} onChange={event => { setEligibility({ ...eligibility, work_authorization: event.target.value || null }); setNotice(""); }} hint="Leave blank if not supplied or uncertain." />
        <label className="text-sm text-slate-300">Visa sponsorship required<select value={eligibility.visa_sponsorship_required === null ? "unknown" : String(eligibility.visa_sponsorship_required)} onChange={event => { setEligibility({ ...eligibility, visa_sponsorship_required: event.target.value === "unknown" ? null : event.target.value === "true" }); setNotice(""); }} className={preferenceInputClass}><option value="unknown">Not supplied / uncertain</option><option value="true">Yes</option><option value="false">No</option></select></label>
      </PreferenceSection> : <p className="text-sm text-slate-400">Eligibility answers require a candidate profile. <Link href="/onboarding" className="text-violet-300">Complete onboarding →</Link></p>}
      <PreferenceSection id="applications" title="Application preferences" description="These limits govern preparation and submission, not how often you can run a manual search. Submission still requires deterministic policy approval and an authorized integration.">
        <PreferenceInput label="Maximum applications per day" type="number" min={0} max={50} value={form.max_daily_applications} onChange={event => field("max_daily_applications", event.target.value)} />
        <PreferenceInput label="Minimum match score" type="number" min={0} max={100} value={form.minimum_match_score} onChange={event => field("minimum_match_score", event.target.value)} />
        <label className="text-sm text-slate-300">Application mode<select value={form.application_mode} onChange={event => field("application_mode", event.target.value as PreferenceDraft["application_mode"])} className={preferenceInputClass}><option value="review">Review Every Application</option><option value="batch">Batch Approval</option><option value="authorized-auto">Authorized integrations only</option></select></label>
      </PreferenceSection>
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-slate-800 bg-slate-900/50 p-5"><p className="text-sm text-slate-400">{dirty ? "You have unsaved changes." : "Your saved preferences are up to date."}</p><Button type="submit" disabled={!dirty || saving}><Save size={16} />{saving ? "Saving…" : "Save changes"}</Button></div>
    </form> : null}
  </AppShell>;
}
