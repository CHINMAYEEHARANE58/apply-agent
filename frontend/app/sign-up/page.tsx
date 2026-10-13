import { SignUp } from "@clerk/nextjs";
import Link from "next/link";
import { clerkIsConfigured } from "../../lib/auth-config";

export default function SignUpPage() {
  return <main className="flex min-h-screen flex-col items-center justify-center bg-[#09090b] px-5 py-10">
    <Link href="/" className="mb-8 text-xl font-semibold">InternAgent</Link>
    {clerkIsConfigured() ? <SignUp routing="hash" signInUrl="/login" fallbackRedirectUrl="/onboarding" appearance={{ variables: { colorPrimary: "#8b5cf6", colorBackground: "#101016", colorForeground: "#f1f5f9", colorInputForeground: "#f1f5f9" } }} /> : <p className="text-slate-400">Account creation is awaiting workspace configuration.</p>}
  </main>;
}
