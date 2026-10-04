export type ApplicationPath = "authorized_submission" | "assisted_manual";

export interface SourceCapability {
  source_name: string;
  discovery_supported: boolean;
  discovery_method: "api" | "feed" | "manual_import" | null;
  application_supported: boolean;
  application_method: "authorized_api" | "assisted_manual" | null;
  messaging_supported: boolean;
  requires_user_confirmation: boolean;
  authorization_verified: boolean;
}

export type ApplicationStatus = "Discovered" | "Matched" | "Prepared" | "Awaiting Approval" | "Submitted" | "Assessment" | "Interview" | "Rejected" | "Offer" | "Withdrawn";
export type ApplicationMode = "review" | "batch" | "authorized-auto";

export interface DashboardMetric { label: string; value: string; change: string; icon: string; }
export interface Job { id: string; role: string; company: string; location: string; duration: string; stipend: string; source: string; match: number; skills: string[]; missingSkills: string[]; postedDate: string; status: ApplicationStatus; remote: boolean; }
export interface Application { id: string; company: string; role: string; status: ApplicationStatus; updatedAt: string; match: number; }
export interface Resume { id: string; name: string; kind: "Master" | "Tailored"; updatedAt: string; targetedRole: string; }
