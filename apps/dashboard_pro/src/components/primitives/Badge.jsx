import { cx, toneStyles } from "./helpers";

export function Badge({ children, tone = "slate" }) {
  return (
    <span className={cx("inline-flex max-w-full items-center overflow-hidden rounded-full border px-2.5 py-1 text-xs font-bold shadow-sm shadow-black/10", toneStyles[tone] || toneStyles.slate)}>
      <span className="min-w-0 truncate">{children}</span>
    </span>
  );
}
