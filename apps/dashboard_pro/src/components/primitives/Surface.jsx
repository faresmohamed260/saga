import { cx } from "./helpers";

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
