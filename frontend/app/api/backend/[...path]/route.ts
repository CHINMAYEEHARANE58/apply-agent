import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { clerkIsConfigured } from "../../../../lib/auth-config";
import { readLimitedBody } from "../../../../lib/request-body";

const allowedRoots = new Set(["users", "profile", "preferences", "resumes", "applications", "jobs", "settings", "dashboard"]);
type Context = { params: Promise<{ path: string[] }> };

async function forward(request: Request, context: Context) {
  if (!clerkIsConfigured()) return NextResponse.json({ error: { message: "Sign-in is not configured." } }, { status: 503 });
  const { userId, getToken } = await auth();
  if (!userId) return NextResponse.json({ error: { message: "Sign in to continue." } }, { status: 401 });
  if (!["GET", "HEAD"].includes(request.method)) {
    // Clerk authenticates cookies here. Block cross-origin state changes before
    // forwarding to the bearer-only backend, including multipart uploads.
    if (request.headers.get("origin") !== new URL(request.url).origin) {
      return NextResponse.json({ error: { message: "Invalid request origin." } }, { status: 403 });
    }
  }
  const { path } = await context.params;
  if (!allowedRoots.has(path[0]) || path.some(part => !/^[a-zA-Z0-9_-]+$/.test(part))) return new Response(null, { status: 404 });
  const token = await getToken().catch(() => null);
  if (!token) return new Response(null, { status: 401 });
  const base = process.env.INTERNAGENT_API_URL || "http://localhost:8000/api/v1";
  const target = new URL(`${base.replace(/\/$/, "")}/${path.join("/")}`);
  target.search = new URL(request.url).search;
  const headers = new Headers({ Authorization: `Bearer ${token}` });
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  const idempotency = request.headers.get("idempotency-key");
  if (idempotency) headers.set("idempotency-key", idempotency);
  try {
    const response = await fetch(target, {
      method: request.method, headers, redirect: "manual", cache: "no-store",
      body: ["GET", "HEAD"].includes(request.method) ? undefined : await readLimitedBody(request),
      signal: AbortSignal.timeout(30000),
    });
    const responseHeaders = new Headers({
      "Content-Type": response.headers.get("content-type") || "application/json",
      "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
    });
    const disposition = response.headers.get("content-disposition");
    if (disposition) responseHeaders.set("content-disposition", disposition);
    return new Response(response.body, { status: response.status, headers: responseHeaders });
  } catch (error) {
    if (error instanceof RangeError) return NextResponse.json({ error: { message: "Request is too large." } }, { status: 413 });
    return NextResponse.json({ error: { message: "The API is temporarily unavailable." } }, { status: 503 });
  }
}

export const GET = forward;
export const POST = forward;
export const PUT = forward;
export const PATCH = forward;
export const DELETE = forward;
