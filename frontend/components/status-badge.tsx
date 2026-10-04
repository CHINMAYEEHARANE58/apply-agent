import { Badge } from "./ui/badge";
import type { ApplicationStatus } from "../lib/types";

const colors: Record<ApplicationStatus, string> = {
  Discovered: "border-slate-700 text-slate-300", Matched: "border-cyan-500/30 bg-cyan-500/10 text-cyan-200", Prepared: "border-violet-500/30 bg-violet-500/10 text-violet-200", "Awaiting Approval": "border-amber-500/30 bg-amber-500/10 text-amber-200", Submitted: "border-blue-500/30 bg-blue-500/10 text-blue-200", Assessment: "border-orange-500/30 bg-orange-500/10 text-orange-200", Interview: "border-emerald-500/30 bg-emerald-500/10 text-emerald-200", Rejected: "border-rose-500/30 bg-rose-500/10 text-rose-200", Offer: "border-green-500/30 bg-green-500/10 text-green-200", Withdrawn: "border-slate-700 bg-slate-800 text-slate-400"
};
export function StatusBadge({ status }: { status: ApplicationStatus }) { return <Badge className={colors[status]}>{status}</Badge>; }
