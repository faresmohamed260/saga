import { cx } from "./helpers";

export function Toolbar({ children, className = "" }) {
  return <div className={cx("flex flex-wrap items-center gap-2", className)}>{children}</div>;
}
