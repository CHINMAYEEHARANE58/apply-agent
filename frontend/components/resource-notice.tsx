export function ResourceNotice({ loading, error, empty }: { loading: boolean; error: string; empty?: string }) {
  if (error) return <p role="alert" className="mt-5 rounded-xl border border-rose-500/30 p-4 text-sm text-rose-200">{error}</p>;
  if (loading) return <p role="status" className="mt-5 text-sm text-slate-400">Loading your data…</p>;
  return empty ? <p className="mt-5 rounded-xl border border-dashed border-slate-700 p-8 text-center text-sm text-slate-400">{empty}</p> : null;
}
