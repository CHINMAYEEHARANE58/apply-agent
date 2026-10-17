import type { InputHTMLAttributes, ReactNode } from "react";

export const preferenceInputClass = "mt-2 block w-full rounded-xl border border-slate-700 bg-slate-950/70 px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-violet-400 focus:ring-2 focus:ring-violet-500/20";

export function PreferenceSection({ id, title, description, children }: { id: string; title: string; description: string; children: ReactNode }) {
  return <section id={id} className="scroll-mt-24 rounded-2xl border border-slate-800 bg-slate-900/45 p-5 sm:p-6"><h2 className="text-lg font-semibold text-white">{title}</h2><p className="mt-1 text-sm leading-6 text-slate-400">{description}</p><div className="mt-5 grid gap-5 sm:grid-cols-2">{children}</div></section>;
}

export function PreferenceInput({ label, hint, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string }) {
  return <label className="block text-sm text-slate-300">{label}<input {...props} aria-label={label} className={preferenceInputClass} />{hint ? <span className="mt-1.5 block text-xs leading-5 text-slate-500">{hint}</span> : null}</label>;
}

export function PreferenceList({ label, value, onChange, hint, placeholder }: { label: string; value: string; onChange: (value: string) => void; hint?: string; placeholder?: string }) {
  return <label className="block text-sm text-slate-300">{label}<textarea aria-label={label} value={value} onChange={event => onChange(event.target.value)} placeholder={placeholder} rows={2} className={preferenceInputClass} /><span className="mt-1.5 block text-xs leading-5 text-slate-500">{hint || "Separate entries with commas or new lines. Leave blank for no preference."}</span></label>;
}

export function PreferenceToggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return <label className="flex items-center gap-3 rounded-xl border border-slate-800 px-4 py-3 text-sm text-slate-300"><input type="checkbox" checked={checked} onChange={event => onChange(event.target.checked)} className="h-4 w-4 accent-violet-500" />{label}</label>;
}
