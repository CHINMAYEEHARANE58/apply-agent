import { clerkMiddleware } from "@clerk/nextjs/server";
import { NextResponse, type NextRequest, type NextFetchEvent } from "next/server";
import { clerkIsConfigured } from "./lib/auth-config";

// Establish Clerk request context only. Each page/handler owns its auth check.
const authenticate = clerkMiddleware();

export default function middleware(request: NextRequest, event: NextFetchEvent) {
  if (!clerkIsConfigured()) {
    const path = request.nextUrl.pathname;
    if (path === "/" || path === "/login" || path.startsWith("/login/") || path === "/sign-up" || path.startsWith("/sign-up/")) return NextResponse.next();
    if (request.nextUrl.pathname.startsWith("/api/")) {
      return NextResponse.json({ error: { message: "Sign-in is not configured." } }, { status: 503 });
    }
    return NextResponse.redirect(new URL("/login", request.url));
  }
  return authenticate(request, event);
}

export const config = {
  matcher: ["/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)", "/(api|trpc)(.*)"],
};
