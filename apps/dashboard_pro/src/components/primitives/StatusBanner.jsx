import { cx, toneStyles } from "./helpers";

export function StatusBanner({ tone = "slate", message, children }) {
  if (!message && !children) return null;
  return (
    <div className={cx("rounded-lg border px-4 py-3 text-sm leading-6", toneStyles[tone] || toneStyles.slate)}>
      {message || children}
    </div>
  );
}
