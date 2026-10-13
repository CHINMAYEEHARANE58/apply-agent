export function clerkIsConfigured(): boolean {
  const key = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
  return Boolean(key && /^pk_(test|live)_/.test(key));
}
