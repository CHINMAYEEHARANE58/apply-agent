import { type ButtonHTMLAttributes } from "react";
import { cn } from "../../lib/utils";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "default" | "outline" | "ghost" | "secondary" | "danger";
  size?: "default" | "sm" | "lg" | "icon";
};

const variants: Record<NonNullable<ButtonProps["variant"]>, string> = {
  default: "bg-violet-500 text-white hover:bg-violet-400 shadow-lg shadow-violet-950/40",
  outline: "border border-slate-700 bg-transparent text-slate-200 hover:border-slate-600 hover:bg-slate-800",
  ghost: "bg-transparent text-slate-400 hover:bg-slate-800 hover:text-white",
  secondary: "bg-slate-800 text-slate-100 hover:bg-slate-700",
  danger: "bg-rose-500/15 text-rose-300 hover:bg-rose-500/25"
};
const sizes: Record<NonNullable<ButtonProps["size"]>, string> = {
  default: "h-10 px-4 text-sm",
  sm: "h-8 px-3 text-xs",
  lg: "h-11 px-5 text-sm",
  icon: "h-10 w-10 p-0"
};

export function Button({ className, variant = "default", size = "default", type = "button", ...props }: ButtonProps) {
  return <button className={cn("inline-flex items-center justify-center gap-2 rounded-xl font-medium transition disabled:pointer-events-none disabled:opacity-50", variants[variant], sizes[size], className)} type={type} {...props} />;
}
