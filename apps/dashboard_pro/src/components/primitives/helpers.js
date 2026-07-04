export function cx(...items) {
  return items.filter(Boolean).join(" ");
}

export const toneStyles = {
  slate: "border-white/10 bg-white/[0.04] text-slate-300",
  blue: "border-cyan-400/45 bg-cyan-400/10 text-cyan-100",
  green: "border-emerald-400/45 bg-emerald-400/10 text-emerald-100",
  amber: "border-amber-400/50 bg-amber-400/10 text-amber-100",
  red: "border-rose-400/50 bg-rose-400/10 text-rose-100",
};

export const inputBase = "w-full rounded-lg border border-white/10 bg-slate-950/70 px-3.5 py-2.5 text-sm text-slate-100 outline-none transition placeholder:text-slate-500 hover:border-white/20 focus:border-cyan-400/65 focus:ring-2 focus:ring-cyan-400/15";

export function toneFor(status) {
  const value = String(status || "").toLowerCase();
  if (["success", "completed", "complete", "healthy", "ready"].includes(value)) return "green";
  if (["running", "queued", "starting", "validating", "staging", "paused"].includes(value)) return "blue";
  if (["failed", "error", "blocked"].includes(value)) return "red";
  if (["partial", "warning", "unknown", "cancelled"].includes(value)) return "amber";
  return "slate";
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
