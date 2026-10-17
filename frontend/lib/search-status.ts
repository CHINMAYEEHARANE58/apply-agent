import type { SearchResult } from "./resources";

export function searchMessage(result: SearchResult): string {
  if (result.status === "disabled") return "Search is disabled. Enable it in Settings.";
  if (result.status === "needs_preferences") return "Save your internship preferences before searching.";
  if (result.status === "needs_roles") return "Select at least one internship role in your preferences before searching.";
  if (result.status === "already_running") return "A search is already running. Let it finish before starting another; you can search again afterwards.";
  if (result.status === "needs_resume") return "Listings were checked, but a verified master resume is needed to prepare applications.";
  if (result.status === "no_sources_enabled") return "No permitted discovery sources are enabled. Choose a source in Settings.";
  if (result.status === "daily_evaluation_limit") return "Today's evaluation limit has been reached. No additional applications were submitted.";
  if (result.status === "retry_limit_reached") return "Search stopped after repeated failures. Check source availability before trying again tomorrow.";
  if (result.status === "source_unavailable") return "The public job sources are temporarily unavailable or cooling down. Please try again later; no application was submitted.";
  if (result.status === "failed") return "The last search failed safely. No application was submitted; you can try again.";
  const summary = result.previous_summary ?? result;
  const prefix = result.status === "already_completed" ? "Today's search already ran. Last run:" : result.status === "partial" ? "Search partially completed:" : "Search completed:";
  const counts = `${summary.jobs_evaluated} ${summary.trigger === "manual" ? "role-relevant listings" : "listings"} evaluated; ${summary.strong_matches ?? 0} strong matches; ${summary.applications_prepared} applications prepared. No external submission.${summary.trigger === "manual" ? " You can run another search whenever you like." : ""}`;
  // Summaries written before live discovery existed were catalogue-only.
  const catalogOnly = summary.catalog_only ?? !summary.sources?.some(source => source.source === "greenhouse_public");
  const empty = summary.jobs_evaluated === 0 ? (catalogOnly ? " No role-relevant internships were found in the imported catalogue. Enable public employer boards in Settings for live discovery." : " No internships for your selected roles were returned by the configured employer boards.") : "";
  return `${prefix} ${counts}${empty}`;
}
