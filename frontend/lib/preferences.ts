import type { ApplicationMode } from "./types";

export const ROLE_OPTIONS = ["Software Engineering Intern", "Frontend Developer Intern", "Backend Developer Intern", "Full Stack Developer Intern", "AI/ML Intern", "Data Science Intern", "Data Analyst Intern", "Product Management Intern", "Cybersecurity Intern", "UI/UX Intern"];
export const LIST_FIELDS = ["roles", "skills", "preferred_locations", "preferred_countries", "preferred_states", "preferred_cities", "preferred_industries", "preferred_companies", "excluded_companies", "excluded_keywords"] as const;
type ListField = typeof LIST_FIELDS[number];
export interface InternshipPreferences {
  roles: string[]; skills: string[]; preferred_locations: string[]; preferred_countries: string[]; preferred_states: string[]; preferred_cities: string[];
  remote_allowed: boolean; hybrid_allowed: boolean; onsite_allowed: boolean;
  min_duration: number | null; max_duration: number | null; duration_unit: "weeks" | "months";
  minimum_stipend: string | null; currency: string | null; allow_unpaid: boolean; compensation_period: "monthly" | "hourly" | null;
  earliest_start_date: string | null; latest_start_date: string | null;
  preferred_industries: string[]; preferred_companies: string[]; excluded_companies: string[]; excluded_keywords: string[];
  max_daily_applications: number; application_mode: ApplicationMode; minimum_match_score: number; search_enabled: boolean; preferred_search_time: string | null;
}
export interface EligibilityPreferences { work_authorization: string | null; relocation_allowed: boolean; visa_sponsorship_required: boolean | null; }
export interface PreferenceEditor { preferences: (InternshipPreferences & { id: string; user_id: string }) | null; eligibility: EligibilityPreferences | null; }
export type PreferenceDraft = Omit<InternshipPreferences, ListField | "min_duration" | "max_duration" | "minimum_stipend" | "max_daily_applications" | "minimum_match_score"> & Record<ListField, string> & { min_duration: string; max_duration: string; minimum_stipend: string; max_daily_applications: string; minimum_match_score: string };

const DEFAULTS: InternshipPreferences = { roles: [], skills: [], preferred_locations: [], preferred_countries: [], preferred_states: [], preferred_cities: [], remote_allowed: true, hybrid_allowed: true, onsite_allowed: false, min_duration: null, max_duration: null, duration_unit: "weeks", minimum_stipend: null, currency: null, allow_unpaid: false, compensation_period: null, earliest_start_date: null, latest_start_date: null, preferred_industries: [], preferred_companies: [], excluded_companies: [], excluded_keywords: [], max_daily_applications: 10, application_mode: "review", minimum_match_score: 75, search_enabled: true, preferred_search_time: null };

export function parseList(value: string): string[] {
  const seen = new Set<string>();
  return value.split(/[,\n]/).map(item => item.trim()).filter(item => {
    if (!item || seen.has(item.toLowerCase())) return false;
    seen.add(item.toLowerCase()); return true;
  });
}

export function preferenceDraft(source: PreferenceEditor["preferences"]): PreferenceDraft {
  // Copy only schema fields, never owner IDs or unknown response properties.
  const fields = Object.fromEntries(Object.entries(DEFAULTS).map(([key, value]) => [key, source && key in source ? source[key as keyof InternshipPreferences] : value])) as unknown as InternshipPreferences;
  const lists = Object.fromEntries(LIST_FIELDS.map(key => [key, fields[key].join(", ")])) as Record<ListField, string>;
  return { ...fields, ...lists, min_duration: fields.min_duration?.toString() ?? "", max_duration: fields.max_duration?.toString() ?? "", minimum_stipend: fields.minimum_stipend ?? "", max_daily_applications: String(fields.max_daily_applications), minimum_match_score: String(fields.minimum_match_score) };
}

export function preferencePayload(draft: PreferenceDraft): InternshipPreferences {
  const duration = (value: string) => value.trim() === "" ? null : Number(value);
  const lists = Object.fromEntries(LIST_FIELDS.map(key => [key, parseList(draft[key])])) as Record<ListField, string[]>;
  const result: InternshipPreferences = { ...draft, ...lists, min_duration: duration(draft.min_duration), max_duration: duration(draft.max_duration), minimum_stipend: draft.minimum_stipend.trim() || null, max_daily_applications: Number(draft.max_daily_applications), minimum_match_score: Number(draft.minimum_match_score) };
  if (!result.roles.length) throw new Error("Select or add at least one internship role.");
  for (const key of LIST_FIELDS) if (result[key].some(item => item.length > 200)) throw new Error("Keep each list item within 200 characters.");
  if (!result.remote_allowed && !result.hybrid_allowed && !result.onsite_allowed) throw new Error("Choose at least one work arrangement.");
  if ([result.min_duration, result.max_duration].some(value => value !== null && (!Number.isInteger(value) || value < 1 || value > 104))) throw new Error("Duration must be a whole number between 1 and 104, or blank.");
  if (result.min_duration !== null && result.max_duration !== null && result.min_duration > result.max_duration) throw new Error("Minimum duration cannot exceed maximum duration.");
  if (result.minimum_stipend !== null && (!/^\d+(\.\d{1,2})?$/.test(result.minimum_stipend) || Number(result.minimum_stipend) > 9999999999.99)) throw new Error("Enter a valid non-negative stipend with up to two decimal places, or leave it blank.");
  if (result.minimum_stipend !== null && !result.currency) throw new Error("Choose a currency for your minimum stipend.");
  if (result.earliest_start_date && result.latest_start_date && result.earliest_start_date > result.latest_start_date) throw new Error("Earliest start date cannot be after the latest start date.");
  if (!draft.max_daily_applications.trim() || !Number.isInteger(result.max_daily_applications) || result.max_daily_applications < 0 || result.max_daily_applications > 50) throw new Error("Daily application limit must be between 0 and 50.");
  if (!draft.minimum_match_score.trim() || !Number.isInteger(result.minimum_match_score) || result.minimum_match_score < 0 || result.minimum_match_score > 100) throw new Error("Minimum match score must be between 0 and 100.");
  return result;
}
