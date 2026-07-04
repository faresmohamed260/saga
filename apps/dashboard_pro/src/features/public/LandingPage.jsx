import { Link } from "react-router-dom";
import { capabilityGroups, heroMetrics, publicNavLinks, studioPreviewRows, trustItems, workflowSteps } from "./publicContent";

function ProductBackdrop() {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_62%_18%,rgba(45,212,191,0.18),transparent_28%),linear-gradient(135deg,rgba(5,7,11,0.12),rgba(15,23,42,0.7)_52%,rgba(2,6,23,0.94))]" />
      <div className="absolute left-[7%] top-24 hidden h-[430px] w-[760px] rotate-[-2deg] rounded-lg border border-white/10 bg-slate-950/55 shadow-2xl shadow-black/30 backdrop-blur md:block">
        <div className="flex h-12 items-center justify-between border-b border-white/10 px-4">
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-300/80" />
            <span className="h-2.5 w-2.5 rounded-full bg-cyan-300/70" />
            <span className="h-2.5 w-2.5 rounded-full bg-slate-500/80" />
          </div>
          <div className="h-2 w-28 rounded-full bg-white/10" />
        </div>
        <div className="grid h-[calc(100%-3rem)] grid-cols-[220px_1fr]">
          <div className="border-r border-white/10 p-4">
            <div className="h-4 w-28 rounded bg-cyan-200/20" />
            <div className="mt-6 space-y-3">
              {["Overview", "Import", "Library", "Assets", "Audiobook"].map((item, index) => (
                <div key={item} className={`rounded-lg border px-3 py-2 text-xs font-bold ${index === 1 ? "border-emerald-300/35 bg-emerald-400/10 text-emerald-100" : "border-white/10 bg-white/[0.03] text-slate-400"}`}>
                  {item}
                </div>
              ))}
            </div>
          </div>
          <div className="p-5">
            <div className="grid grid-cols-3 gap-3">
              {heroMetrics.map((metric) => (
                <div key={metric.label} className="rounded-lg border border-white/10 bg-white/[0.04] p-3">
                  <p className="text-xl font-black text-white">{metric.value}</p>
                  <p className="mt-1 text-[11px] font-bold uppercase tracking-[0.16em] text-slate-500">{metric.label}</p>
                </div>
              ))}
            </div>
            <div className="mt-5 rounded-lg border border-white/10 bg-slate-950/70 p-4">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <div className="h-3 w-36 rounded-full bg-cyan-200/25" />
                  <div className="mt-2 h-2 w-48 rounded-full bg-white/10" />
                </div>
                <div className="rounded-lg border border-emerald-300/35 bg-emerald-400/10 px-3 py-1.5 text-xs font-black uppercase tracking-[0.16em] text-emerald-100">
                  Ready
                </div>
              </div>
              <div className="space-y-3">
                {studioPreviewRows.map((row) => (
                  <div key={row.label} className="grid grid-cols-[1fr_140px] items-center gap-3 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
                    <span className="text-sm font-bold text-slate-200">{row.label}</span>
                    <span className={`text-right text-xs font-black uppercase tracking-[0.14em] ${row.tone === "green" ? "text-emerald-200" : row.tone === "blue" ? "text-cyan-200" : "text-slate-400"}`}>
                      {row.detail}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
      <div className="absolute bottom-[-12rem] right-[-7rem] h-[32rem] w-[32rem] rounded-full border border-cyan-300/10" />
    </div>
  );
}

function PublicNav() {
  return (
    <nav className="relative z-10 mx-auto flex w-full max-w-7xl items-center justify-between px-5 py-5 md:px-7">
      <Link to="/" className="text-sm font-black tracking-[0.24em] text-cyan-100">
        S.A.G.A.
      </Link>
      <div className="hidden items-center gap-6 md:flex">
        {publicNavLinks.map((item) => (
          <a key={item.href} href={item.href} className="text-sm font-bold text-slate-400 transition hover:text-white">
            {item.label}
          </a>
        ))}
      </div>
      <div className="flex items-center gap-2">
        <Link to="/signin" className="rounded-lg border border-transparent px-3 py-2 text-sm font-bold text-slate-300 transition hover:border-white/10 hover:bg-white/[0.04] hover:text-white">
          Sign in
        </Link>
        <Link to="/signup" className="rounded-lg border border-emerald-300/45 bg-emerald-400/15 px-4 py-2 text-sm font-bold text-emerald-50 transition hover:border-emerald-200/70 hover:bg-emerald-400/25">
          Sign up
        </Link>
      </div>
    </nav>
  );
}

export function LandingPage() {
  return (
    <main className="min-h-screen overflow-hidden">
      <section className="relative min-h-[92vh] border-b border-white/10">
        <ProductBackdrop />
        <PublicNav />
        <div className="relative z-10 mx-auto grid min-h-[calc(92vh-5rem)] max-w-7xl content-center px-5 pb-20 pt-12 md:px-7">
          <div className="max-w-3xl">
            <h1 className="text-5xl font-black tracking-tight text-white sm:text-6xl lg:text-7xl">Story Production Studio</h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-300">
            Import books, inspect canon memory, manage visual assets, generate stories, and produce audiobooks from one connected workspace.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/signup" className="rounded-lg border border-emerald-300/45 bg-emerald-400/15 px-5 py-3 text-sm font-bold text-emerald-50 transition hover:border-emerald-200/70 hover:bg-emerald-400/25">
                Start building
              </Link>
              <Link to="/overview" className="rounded-lg border border-white/10 bg-white/[0.04] px-5 py-3 text-sm font-bold text-slate-100 transition hover:border-cyan-300/45 hover:bg-cyan-300/10">
                View studio
              </Link>
            </div>
            <div className="mt-10 grid max-w-2xl gap-3 sm:grid-cols-3">
              {heroMetrics.map((metric) => (
                <div key={metric.label} className="rounded-lg border border-white/10 bg-slate-950/45 p-4 backdrop-blur">
                  <p className="text-2xl font-black text-white">{metric.value}</p>
                  <p className="mt-1 text-xs font-bold uppercase tracking-[0.16em] text-slate-500">{metric.label}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section id="workflow" className="border-b border-white/10 bg-slate-950/35 py-20">
        <div className="mx-auto max-w-7xl px-5 md:px-7">
          <div className="max-w-2xl">
            <h2 className="text-3xl font-black tracking-tight text-white md:text-4xl">A cleaner path from source text to production output.</h2>
            <p className="mt-4 text-base leading-7 text-slate-400">S.A.G.A. keeps ingestion, analysis, generation, visual asset work, and audiobook staging in one operational flow.</p>
          </div>
          <div className="mt-10 grid gap-4 lg:grid-cols-3">
            {workflowSteps.map((step, index) => (
              <article key={step.title} className="rounded-lg border border-white/10 bg-white/[0.04] p-5 shadow-xl shadow-black/10">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-cyan-300/35 bg-cyan-300/10 text-sm font-black text-cyan-100">
                  {index + 1}
                </div>
                <h3 className="mt-5 text-xl font-black text-white">{step.title}</h3>
                <p className="mt-3 text-sm leading-6 text-slate-400">{step.body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="studio" className="border-b border-white/10 py-20">
        <div className="mx-auto grid max-w-7xl gap-10 px-5 md:px-7 lg:grid-cols-[0.95fr_1.05fr]">
          <div>
            <h2 className="text-3xl font-black tracking-tight text-white md:text-4xl">Built for the operator who needs the whole system visible.</h2>
            <p className="mt-4 text-base leading-7 text-slate-400">The interface stays close to the dashboard design language: compact panels, clear status color, disciplined hierarchy, and no decorative clutter.</p>
          </div>
          <div className="grid gap-4">
            {capabilityGroups.map((item) => (
              <article key={item.title} className="rounded-lg border border-white/10 bg-slate-950/55 p-5 shadow-xl shadow-black/10">
                <h3 className="text-lg font-black text-white">{item.title}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-400">{item.body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="security" className="border-b border-white/10 bg-slate-950/45 py-16">
        <div className="mx-auto flex max-w-7xl flex-col gap-6 px-5 md:px-7 lg:flex-row lg:items-center lg:justify-between">
          <h2 className="max-w-xl text-2xl font-black tracking-tight text-white md:text-3xl">Professional defaults for a local-first production workspace.</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {trustItems.map((item) => (
              <div key={item} className="rounded-lg border border-white/10 bg-white/[0.04] px-4 py-3 text-sm font-bold text-slate-200">
                {item}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="py-20">
        <div className="mx-auto max-w-7xl px-5 md:px-7">
          <div className="rounded-lg border border-emerald-300/25 bg-emerald-400/10 p-8 md:p-10">
            <h2 className="max-w-3xl text-3xl font-black tracking-tight text-white md:text-4xl">Start with a workspace that already understands production reality.</h2>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link to="/signup" className="rounded-lg border border-emerald-200/70 bg-emerald-300/20 px-5 py-3 text-sm font-bold text-emerald-50 transition hover:bg-emerald-300/30">
                Start building
              </Link>
              <Link to="/signin" className="rounded-lg border border-white/10 bg-slate-950/35 px-5 py-3 text-sm font-bold text-slate-100 transition hover:border-cyan-300/45 hover:bg-cyan-300/10">
                Sign in
              </Link>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
