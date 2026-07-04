import { Link } from "react-router-dom";
import { cx } from "./helpers";

export function Button({ children, variant = "secondary", className = "", asLink = "", ...props }) {
  const variants = {
    primary: "border-emerald-300/45 bg-emerald-400/15 text-emerald-50 hover:border-emerald-200/70 hover:bg-emerald-400/25",
    secondary: "border-white/10 bg-white/[0.04] text-slate-100 hover:border-cyan-300/45 hover:bg-cyan-300/10",
    danger: "border-rose-300/45 bg-rose-400/10 text-rose-50 hover:bg-rose-400/20",
    ghost: "border-transparent bg-transparent text-slate-300 hover:border-white/10 hover:bg-white/[0.05] hover:text-white",
  };
  const classes = cx("inline-flex min-h-10 items-center justify-center rounded-lg border px-4 py-2 text-sm font-bold transition focus:outline-none focus:ring-2 focus:ring-cyan-400/25 disabled:cursor-not-allowed disabled:opacity-50", variants[variant], className);
  if (asLink) return <Link to={asLink} className={classes}>{children}</Link>;
  return <button className={classes} {...props}>{children}</button>;
}
