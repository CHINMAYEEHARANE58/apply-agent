import { type HTMLAttributes } from "react";
import { cn } from "../../lib/utils";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-2xl border border-slate-800/80 bg-slate-900/50 p-5 shadow-sm shadow-black/20", className)} {...props} />;
}
