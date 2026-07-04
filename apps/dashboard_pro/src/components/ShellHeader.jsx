import { NavLink } from "react-router-dom";
import { Badge, Button, Surface, cx } from "./primitives";

export function ShellHeader({ state, loading, latestLabel, latestDetail, onRefresh }) {
  return (
    <header className="overflow-hidden rounded-lg border border-white/10 bg-slate-950/70 shadow-2xl shadow-black/20">
      <div className="grid gap-0 lg:grid-cols-[1fr_340px]">
        <div className="px-5 py-6 md:px-7 md:py-7">
          <div className="mb-4 flex flex-wrap gap-2">
            <Badge tone="blue">Live library</Badge>
            <Badge tone="green">Production ready</Badge>
            <Badge>Guided workflows</Badge>
          </div>
          <p className="text-xs font-black uppercase tracking-[0.22em] text-cyan-200/80">S.A.G.A.</p>
          <h1 className="mt-2 text-3xl font-black tracking-tight text-white md:text-4xl">Story Production Studio</h1>
          <p className="mt-3 max-w-4xl text-base leading-7 text-slate-300">
            Import books, monitor analysis, explore canon data, manage visual assets, and generate stories from one polished workspace.
          </p>
          <p className="mt-4 max-w-full truncate text-sm text-slate-500">{state?.workspace?.root || "Loading workspace..."}</p>
        </div>
        <div className="border-t border-white/10 bg-gradient-to-br from-emerald-400/10 via-cyan-400/5 to-transparent p-5 lg:border-l lg:border-t-0">
          <Surface className="h-full p-5">
            <div className="flex h-full flex-col justify-between gap-5">
              <div>
                <p className="text-xs font-black uppercase tracking-[0.2em] text-emerald-200">Latest activity</p>
                <p className="mt-3 text-3xl font-black text-white">{loading ? "loading" : latestLabel}</p>
                <p className="mt-2 text-sm leading-6 text-emerald-100/75">{latestDetail}</p>
              </div>
              <Button className="w-full" onClick={onRefresh}>Refresh</Button>
            </div>
          </Surface>
        </div>
      </div>
    </header>
  );
}

export function ShellNav({ items }) {
  return (
    <nav className="sticky top-0 z-20 mt-5 border-b border-white/10 bg-[#070b11]/88 py-3 backdrop-blur-xl">
      <div className="flex gap-2 overflow-x-auto pb-1">
        {items.map((item) => (
          <NavItem key={item.to} {...item} />
        ))}
      </div>
    </nav>
  );
}

function NavItem({ to, label }) {
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
