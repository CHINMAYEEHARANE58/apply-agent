// No dotenv loading, network requests, or printing configuration values.
const required = ["NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "CLERK_SECRET_KEY", "INTERNAGENT_API_URL"];
const missing = required.filter(key => !process.env[key]?.trim());
if (missing.length) {
  console.error(`Deployment blocked. Configure these environment variables privately: ${missing.join(", ")}.`);
  process.exit(1);
}
let api;
try { api = new URL(process.env.INTERNAGENT_API_URL); }
catch {
  console.error("Deployment blocked. INTERNAGENT_API_URL is not a valid HTTPS backend URL.");
  process.exit(1);
}
if (api.protocol !== "https:" || api.username || api.password || api.search || api.hash || !api.pathname.endsWith("/api/v1") || api.hostname === "localhost" || !api.hostname.includes(".") || api.hostname.endsWith(".local") || api.hostname.endsWith(".internal") || /^[\d.:\[\]]+$/.test(api.hostname)) {
  console.error("Deployment blocked. INTERNAGENT_API_URL must be your deployed HTTPS backend ending in /api/v1, not a local address or credential-bearing URL.");
  process.exit(1);
}
const publishable = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
const secret = process.env.CLERK_SECRET_KEY;
if (!(publishable.startsWith("pk_test_") && secret.startsWith("sk_test_") || publishable.startsWith("pk_live_") && secret.startsWith("sk_live_"))) {
  console.error("Deployment blocked. Clerk key environment types must match.");
  process.exit(1);
}
if (process.env.VERCEL_ENV === "production" && !publishable.startsWith("pk_live_")) {
  console.error("Production deployment blocked. Configure a production Clerk application; development keys are for previews only.");
  process.exit(1);
}
console.log("Deployment environment checks passed. Backend reachability, storage, Redis and sign-in must still be verified before release.");
