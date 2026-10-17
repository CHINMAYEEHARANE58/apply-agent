"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "./api";
import type { Job } from "./types";

export interface Page<T> { items: T[]; total: number; limit: number; offset: number; }
export interface StoredJob { id: string; title: string; company: string; description: string; job_url: string; location: string | null; duration: string | null; stipend: string | null; currency: string | null; source: string; posted_at: string | null; workplace_type: string | null; saved: boolean; ignored: boolean; match_score: number | null; matched_skills: string[]; missing_skills: string[]; hard_filter_passed?: boolean | null; match_explanation?: string | null; }
export interface Dashboard { jobs_discovered_today: number; strong_matches: number; applications_prepared: number; applications_submitted: number; interviews: number; responses: number; }
export interface SearchSourceReport { source: string; status: string; listings: number; boards?: { board: string; status: string; listings: number; role_matches?: number }[]; }
export interface SearchResult { status: string; jobs_evaluated: number; applications_prepared: number; strong_matches?: number; catalog_only?: boolean; trigger?: "manual" | "scheduled"; search_id?: string; selected_roles?: string[]; sources?: SearchSourceReport[]; rejection_reasons?: Record<string, number>; previous_summary?: SearchResult; }
export interface SearchStatus { live_discovery_enabled: boolean; boards: string[]; selected_roles: string[]; manual_search_limit: number; public_cache_seconds: number; last_search: SearchResult | null; }
export interface StoredResume { id: string; type: "master" | "tailored"; version: number; original_filename: string | null; created_at: string; approval_status: string; source_resume_id: string | null; generated_bullets: { text: string; supporting_fact_ids: string[] }[] | null; }
export interface StoredApplication { id: string; job_id: string; resume_id: string | null; status: string; cover_letter: string | null; application_message: string | null; submitted_at: string | null; }
export interface StoredSettings { search_enabled: boolean; search_time: string; timezone: string; minimum_match_score: number; max_daily_applications: number; maximum_jobs_evaluated_daily: number; maximum_applications_prepared_daily: number; application_mode: "review" | "batch" | "authorized-auto"; email_notifications: boolean; application_notifications: boolean; enabled_sources: string[]; user_id: string; }

export function useResource<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const refresh = useCallback(async () => {
    setLoading(true); setError("");
    try { setData(await apiFetch<T>(path)); }
    catch (problem) { setError(problem instanceof Error ? problem.message : "Unable to load your data."); }
    finally { setLoading(false); }
  }, [path]);
  useEffect(() => { void refresh(); }, [refresh]);
  return { data, error, loading, refresh };
}

export function displayJob(job: StoredJob): Job {
  return { id: job.id, role: job.title, company: job.company, location: job.location || "Not specified", duration: job.duration || "Duration not specified", stipend: job.stipend == null ? "Compensation not specified" : (job.currency || "") + " " + job.stipend, source: job.source === "greenhouse_public" ? "Greenhouse public API" : job.source, match: job.match_score || 0, skills: job.matched_skills, missingSkills: job.missing_skills, postedDate: job.posted_at ? new Date(job.posted_at).toLocaleDateString() : "Date not specified", status: job.hard_filter_passed === false ? "Discovered" : "Matched", remote: job.workplace_type === "remote", saved: job.saved, ignored: job.ignored, url: job.job_url, fit: job.match_score === null ? "unchecked" : job.hard_filter_passed === false ? "rejected" : job.hard_filter_passed === true ? "eligible" : "unchecked", matchExplanation: job.match_explanation || undefined };
}

export async function downloadResume(id: string, name: string) {
  const response = await fetch("/api/backend/resumes/" + id + "/download", { credentials: "same-origin", cache: "no-store" });
  if (!response.ok) {
    const payload = await response.json();
    throw new Error(payload?.error?.message || "Unable to download this resume.");
  }
  const url = URL.createObjectURL(await response.blob());
  try {
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = name;
    document.body.append(anchor); anchor.click(); anchor.remove();
  } finally { URL.revokeObjectURL(url); }
}
