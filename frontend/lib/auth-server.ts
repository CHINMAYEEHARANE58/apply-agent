import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { clerkIsConfigured } from "./auth-config";

// Each protected page checks identity at the resource, even if middleware
// routing is skipped. The API proxy and FastAPI verify it independently.
export async function requireSignIn(): Promise<void> {
  if (!clerkIsConfigured()) redirect("/login");
  await auth.protect();
}
