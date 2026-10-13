import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { clerkIsConfigured } from "../lib/auth-config";
import "./globals.css";

export const metadata: Metadata = {
  title: "InternAgent",
  description: "Policy-first internship discovery assistant"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{clerkIsConfigured() ? <ClerkProvider afterSignOutUrl="/login" signInUrl="/login" signUpUrl="/sign-up" signInFallbackRedirectUrl="/dashboard" signUpFallbackRedirectUrl="/onboarding">{children}</ClerkProvider> : children}</body></html>;
}
