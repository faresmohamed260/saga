import { NavLink } from "react-router-dom";
import { cx } from "../primitives";

export function NavItem({ to, label }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        cx(
          "shrink-0 rounded-lg border px-4 py-2 text-sm font-black transition",
          isActive
            ? "border-cyan-300/60 bg-cyan-300/15 text-white shadow-lg shadow-cyan-950/20"
            : "border-white/10 bg-white/[0.035] text-slate-300 hover:border-white/20 hover:bg-white/[0.06]",
        )
      }
    >
      {label}
    </NavLink>
  );
}
