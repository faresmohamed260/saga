import { cx } from "./helpers";

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
