export class ApiError extends Error {
  constructor(message: string, readonly status: number) { super(message); }
}

// Same-origin server proxy obtains the Clerk token. No tokens/UUID identities
// are persisted in browser storage or supplied by application forms.
export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/backend/${path.replace(/^\//, "")}`, {
    ...options, cache: "no-store", credentials: "same-origin",
  });
  const body = response.status === 204 ? null : await response.json();
  if (!response.ok) throw new ApiError(body?.error?.message || "Request failed. Please try again.", response.status);
  return body as T;
}
