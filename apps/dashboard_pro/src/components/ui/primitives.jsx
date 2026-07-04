import React from "react";
import { Link } from "react-router-dom";

export function cx(...items) {
  return items.filter(Boolean).join(" ");
}

const toneStyles = {
  slate: "border-white/10 bg-white/[0.04] text-slate-300",
  blue: "border-cyan-400/45 bg-cyan-400/10 text-cyan-100",
  green: "border-emerald-400/45 bg-emerald-400/10 text-emerald-100",
  amber: "border-amber-400/50 bg-amber-400/10 text-amber-100",
  red: "border-rose-400/50 bg-rose-400/10 text-rose-100",
};

const inputBase = "w-full rounded-lg border border-white/10 bg-slate-950/70 px-3.5 py-2.5 text-sm text-slate-100 outline-none transition placeholder:text-slate-500 hover:border-white/20 focus:border-cyan-400/65 focus:ring-2 focus:ring-cyan-400/15";

export function toneFor(status) {
  const value = String(status || "").toLowerCase();
  if (["success", "completed", "complete", "healthy", "ready"].includes(value)) return "green";
  if (["running", "queued", "starting", "validating", "staging", "paused"].includes(value)) return "blue";
  if (["failed", "error", "blocked"].includes(value)) return "red";
  if (["partial", "warning", "unknown", "cancelled"].includes(value)) return "amber";
  return "slate";
}

export function Badge({ children, tone = "slate" }) {
  return (
    <span className={cx("inline-flex max-w-full items-center overflow-hidden rounded-full border px-2.5 py-1 text-xs font-bold shadow-sm shadow-black/10", toneStyles[tone] || toneStyles.slate)}>
      <span className="min-w-0 truncate">{children}</span>
    </span>
  );
}

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

export function Surface({ as: Component = "div", className = "", children, ...props }) {
  return (
    <Component
      className={cx(
        "rounded-lg border border-white/10 bg-slate-950/55 shadow-xl shadow-black/15 backdrop-blur",
        className,
      )}
      {...props}
    >
      {children}
    </Component>
  );
}

export function Panel({ title, subtitle, action, children, className = "" }) {
  return (
    <Surface as="section" className={cx("p-5", className)}>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <SectionHeading title={title} subtitle={subtitle} />
        {action}
      </div>
      {children}
    </Surface>
  );
}

export function Metric({ label, value, detail = "live", tone = "slate" }) {
  return (
    <Surface className="relative overflow-hidden p-4">
      <div className={cx("absolute inset-x-0 top-0 h-1", tone === "green" ? "bg-emerald-300/70" : tone === "blue" ? "bg-cyan-300/70" : tone === "amber" ? "bg-amber-300/70" : tone === "red" ? "bg-rose-300/70" : "bg-white/15")} />
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-500">{label}</p>
        <Badge tone={tone}>{detail}</Badge>
      </div>
      <p className="mt-3 text-3xl font-black text-white tabular-nums">{formatNumber(value)}</p>
    </Surface>
  );
}

export function EmptyState({ title = "Nothing here yet", children }) {
  return (
    <div className="rounded-lg border border-dashed border-white/10 bg-white/[0.03] p-6 text-sm text-slate-400">
      <p className="font-bold text-slate-200">{title}</p>
      {children ? <div className="mt-2 leading-6">{children}</div> : null}
    </div>
  );
}

export function Field({ label, children }) {
  return (
    <div className="rounded-lg border border-white/5 bg-black/20 p-4">
      <p className="mb-2 text-xs font-bold uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <div className="text-sm leading-6 text-slate-100">{children}</div>
    </div>
  );
}

export function SearchBox({ value, onChange, placeholder = "Search..." }) {
  return (
    <input
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder}
      className={cx(inputBase, "rounded-lg px-4 py-3")}
    />
  );
}

export function TextInput({ className = "", ...props }) {
  return <input className={cx(inputBase, className)} {...props} />;
}

export function SelectInput({ className = "", children, ...props }) {
  return (
    <select className={cx(inputBase, "cursor-pointer", className)} {...props}>
      {children}
    </select>
  );
}

export function TextArea({ className = "", ...props }) {
  return <textarea className={cx(inputBase, "min-h-36 resize-y", className)} {...props} />;
}

export function Toolbar({ children, className = "" }) {
  return <div className={cx("flex flex-wrap items-center gap-2", className)}>{children}</div>;
}

export function SectionHeading({ title, subtitle, className = "" }) {
  return (
    <div className={className}>
      <h2 className="text-lg font-black text-white">{title}</h2>
      {subtitle ? <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-400">{subtitle}</p> : null}
    </div>
  );
}

export function StatusBanner({ tone = "slate", message, children }) {
  if (!message && !children) return null;
  return (
    <div className={cx("rounded-lg border px-4 py-3 text-sm leading-6", toneStyles[tone] || toneStyles.slate)}>
      {message || children}
    </div>
  );
}

export function DataCard({ as: Component = "article", className = "", children, interactive = false, ...props }) {
  return (
    <Component
      className={cx(
        "rounded-lg border border-white/10 bg-slate-950/45 p-4 shadow-lg shadow-black/10",
        interactive ? "transition hover:border-cyan-300/45 hover:bg-cyan-300/5" : "",
        className,
      )}
      {...props}
    >
      {children}
    </Component>
  );
}

export function formatNumber(value) {
  const parsed = Number(value || 0);
  return Number.isFinite(parsed) ? parsed.toLocaleString() : "0";
}

export function text(value, fallback = "Not recorded") {
  const formatted = formatDisplayValue(value);
  return formatted || fallback;
}

export function formatDisplayValue(value) {
  if (Array.isArray(value)) {
    return value.map(formatDisplayValue).filter(Boolean).join(", ");
  }
  if (value && typeof value === "object") {
    return Object.entries(value)
      .map(([key, item]) => {
        const rendered = formatDisplayValue(item);
        return rendered ? `${humanizeKey(key)}: ${rendered}` : "";
      })
      .filter(Boolean)
      .join(" | ");
  }
  const raw = String(value ?? "").trim();
  if (!raw) return "";
  const normalized = raw.toLowerCase();
  if (["0", "n/a", "none", "null", "unknown", "not_explicitly_stated_in_text"].includes(normalized)) return "";
  return raw;
}

export function humanizeKey(value) {
  return String(value || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

export function shortRef(value) {
  const raw = String(value || "");
  return raw.length > 92 ? `${raw.slice(0, 44)}...${raw.slice(-36)}` : raw;
}
