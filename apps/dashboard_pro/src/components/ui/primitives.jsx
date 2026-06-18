import React from "react";
import { Link } from "react-router-dom";

export function cx(...items) {
  return items.filter(Boolean).join(" ");
}

export function toneFor(status) {
  const value = String(status || "").toLowerCase();
  if (["success", "completed", "complete", "healthy", "ready"].includes(value)) return "green";
  if (["running", "queued", "starting", "validating", "staging", "paused"].includes(value)) return "blue";
  if (["failed", "error", "blocked"].includes(value)) return "red";
  if (["partial", "warning", "unknown", "cancelled"].includes(value)) return "amber";
  return "slate";
}

export function Badge({ children, tone = "slate" }) {
  const tones = {
    slate: "border-slate-700 bg-slate-900/80 text-slate-300",
    blue: "border-sky-500/50 bg-sky-500/10 text-sky-200",
    green: "border-emerald-500/50 bg-emerald-500/10 text-emerald-200",
    amber: "border-amber-500/50 bg-amber-500/10 text-amber-200",
    red: "border-red-500/50 bg-red-500/10 text-red-200",
  };
  return <span className={cx("inline-flex max-w-full items-center overflow-hidden rounded-full border px-2.5 py-1 text-xs font-bold", tones[tone])}><span className="min-w-0 truncate">{children}</span></span>;
}

export function Button({ children, variant = "secondary", className = "", asLink = "", ...props }) {
  const variants = {
    primary: "border-emerald-400/50 bg-emerald-500/15 text-emerald-100 hover:bg-emerald-500/25",
    secondary: "border-slate-700 bg-slate-950/70 text-slate-100 hover:border-sky-500/60 hover:bg-sky-500/10",
    danger: "border-red-500/50 bg-red-500/10 text-red-100 hover:bg-red-500/20",
  };
  const classes = cx("rounded-xl border px-4 py-2 text-sm font-bold transition disabled:cursor-not-allowed disabled:opacity-50", variants[variant], className);
  if (asLink) return <Link to={asLink} className={classes}>{children}</Link>;
  return <button className={classes} {...props}>{children}</button>;
}

export function Panel({ title, subtitle, action, children }) {
  return (
    <section className="rounded-3xl border border-slate-800 bg-slate-950/70 p-5 shadow-2xl shadow-black/20">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-black text-white">{title}</h2>
          {subtitle ? <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-400">{subtitle}</p> : null}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

export function Metric({ label, value, detail = "live", tone = "slate" }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-[#0d1017] p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-slate-500">{label}</p>
        <Badge tone={tone}>{detail}</Badge>
      </div>
      <p className="mt-3 text-3xl font-black text-white">{formatNumber(value)}</p>
    </div>
  );
}

export function EmptyState({ title = "Nothing here yet", children }) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-800 bg-slate-950/60 p-6 text-sm text-slate-400">
      <p className="font-bold text-slate-200">{title}</p>
      {children ? <div className="mt-2 leading-6">{children}</div> : null}
    </div>
  );
}

export function Field({ label, children }) {
  return (
    <div className="rounded-2xl bg-black/25 p-4">
      <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-slate-500">{label}</p>
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
      className="w-full rounded-2xl border border-slate-800 bg-slate-950/80 px-4 py-3 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-sky-500"
    />
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
