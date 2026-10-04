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
