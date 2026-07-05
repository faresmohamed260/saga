import { Link } from "react-router-dom";
import { capabilityGroups, heroMetrics, publicNavLinks, studioPreviewRows, trustItems, workflowSteps } from "./publicContent";

function PublicNav() {
  return (
    <div className="sticky top-0 z-30 border-b border-white/10 bg-[#07111a]/82 backdrop-blur-xl">
      <nav className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4 md:px-7">
        <Link to="/" className="text-sm font-black tracking-[0.3em] text-slate-50">
          S.A.G.A.
        </Link>
        <div className="hidden items-center gap-8 lg:flex">
          {publicNavLinks.map((item) => (
            <a key={item.href} href={item.href} className="text-sm font-bold text-slate-400 transition hover:text-white">
              {item.label}
            </a>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <Link to="/signin" className="rounded-lg px-3 py-2 text-sm font-bold text-slate-300 transition hover:bg-white/[0.04] hover:text-white">
            Sign in
          </Link>
          <Link to="/signup" className="rounded-lg border border-emerald-300/35 bg-emerald-400/12 px-4 py-2 text-sm font-bold text-emerald-50 transition hover:border-emerald-200/55 hover:bg-emerald-400/22">
            Sign up
          </Link>
        </div>
      </nav>
    </div>
  );
}

function HeroPreview() {
  return (
    <div className="relative">
      <div className="absolute inset-x-8 top-8 h-56 rounded-full bg-cyan-300/12 blur-3xl" />
      <div className="relative overflow-hidden rounded-[28px] border border-white/10 bg-slate-950/78 shadow-[0_40px_120px_rgba(0,0,0,0.45)]">
        <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-300/90" />
            <span className="h-2.5 w-2.5 rounded-full bg-cyan-300/80" />
            <span className="h-2.5 w-2.5 rounded-full bg-slate-500/80" />
          </div>
          <div className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[11px] font-black uppercase tracking-[0.18em] text-slate-400">
            Story production workspace
          </div>
        </div>

        <div className="grid gap-4 p-5 xl:grid-cols-[220px_1fr]">
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
            <p className="text-[11px] font-black uppercase tracking-[0.2em] text-cyan-200">Navigation</p>
            <div className="mt-4 space-y-2.5">
              {["Overview", "Import", "Library", "Assets", "Audiobook", "Providers"].map((item, index) => (
                <div
                  key={item}
                  className={`rounded-xl border px-3 py-2.5 text-sm font-bold ${index === 1 ? "border-emerald-300/35 bg-emerald-400/10 text-emerald-50" : "border-white/8 bg-slate-950/55 text-slate-400"}`}
                >
                  {item}
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-3">
              {heroMetrics.map((metric) => (
                <div key={metric.label} className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                  <p className="text-[11px] font-black uppercase tracking-[0.18em] text-slate-500">{metric.label}</p>
                  <p className="mt-3 text-3xl font-black text-white">{metric.value}</p>
                </div>
              ))}
            </div>

            <div className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
              <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-[11px] font-black uppercase tracking-[0.18em] text-slate-500">Current workflow</p>
                    <p className="mt-2 text-xl font-black text-white">Import plan ready for execution</p>
                  </div>
                  <span className="rounded-full border border-emerald-300/35 bg-emerald-400/10 px-3 py-1 text-[11px] font-black uppercase tracking-[0.18em] text-emerald-100">
                    Ready
                  </span>
                </div>
                <div className="mt-5 space-y-3">
                  {studioPreviewRows.map((row) => (
                    <div key={row.label} className="grid grid-cols-[1fr_136px] items-center gap-3 rounded-xl border border-white/10 bg-slate-950/60 px-4 py-3">
                      <span className="text-sm font-bold text-slate-200">{row.label}</span>
                      <span className={`text-right text-[11px] font-black uppercase tracking-[0.16em] ${row.tone === "green" ? "text-emerald-200" : row.tone === "blue" ? "text-cyan-200" : "text-slate-400"}`}>
                        {row.detail}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-2xl border border-white/10 bg-[linear-gradient(180deg,rgba(17,24,39,0.9),rgba(6,12,20,0.96))] p-4">
                <p className="text-[11px] font-black uppercase tracking-[0.18em] text-slate-500">Signals</p>
                <div className="mt-4 space-y-4">
                  <div className="rounded-xl border border-cyan-300/15 bg-cyan-300/[0.06] p-4">
                    <p className="text-sm font-bold text-cyan-100">Canon memory stays queryable across runs.</p>
                    <p className="mt-2 text-sm leading-6 text-slate-400">Structured records make downstream story and visual decisions easier to verify.</p>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
                    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
                      <p className="text-lg font-black text-white">9 stages</p>
                      <p className="mt-1 text-sm text-slate-400">From source upload through export handoff.</p>
                    </div>
                    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
                      <p className="text-lg font-black text-white">Live provider health</p>
                      <p className="mt-1 text-sm text-slate-400">Operational status is visible before long-running jobs begin.</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function LandingPage() {
  return (
    <main className="min-h-screen text-slate-100">
      <PublicNav />

      <section className="relative overflow-hidden border-b border-white/10">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(16,185,129,0.16),transparent_28%),radial-gradient(circle_at_78%_16%,rgba(34,211,238,0.14),transparent_26%),linear-gradient(180deg,rgba(6,11,18,0.96),rgba(5,8,14,1))]" />
        <div className="absolute inset-y-0 left-[14%] w-px bg-white/[0.05]" />
        <div className="absolute inset-y-0 right-[18%] w-px bg-white/[0.04]" />
        <div className="relative mx-auto grid max-w-7xl gap-12 px-5 py-14 md:px-7 lg:grid-cols-[0.92fr_1.08fr] lg:items-center lg:py-20">
          <div className="max-w-2xl">
            <div className="inline-flex items-center gap-3 rounded-full border border-cyan-300/18 bg-cyan-300/[0.06] px-4 py-2 text-[11px] font-black uppercase tracking-[0.22em] text-cyan-100">
              Operator-grade narrative production
            </div>
            <h1 className="mt-7 max-w-4xl text-5xl font-black tracking-[-0.03em] text-white sm:text-6xl lg:text-[4.8rem] lg:leading-[0.94]">
              Story production, without losing the system behind the story.
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-8 text-slate-300">
              Import books, inspect canon memory, manage visual assets, generate stories, and produce audiobooks from one connected workspace.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/signup" className="inline-flex min-h-12 items-center justify-center rounded-xl border border-emerald-300/35 bg-emerald-400/12 px-5 py-3 text-sm font-bold text-emerald-50 transition hover:border-emerald-200/55 hover:bg-emerald-400/22">
                Start building
              </Link>
              <Link to="/overview" className="inline-flex min-h-12 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] px-5 py-3 text-sm font-bold text-slate-100 transition hover:border-cyan-300/30 hover:bg-cyan-300/[0.08]">
                View studio
              </Link>
            </div>
            <div className="mt-10 grid gap-3 sm:grid-cols-3">
              {heroMetrics.map((metric) => (
                <div key={metric.label} className="rounded-2xl border border-white/10 bg-slate-950/50 px-4 py-4 backdrop-blur">
                  <p className="text-2xl font-black text-white">{metric.value}</p>
                  <p className="mt-1 text-[11px] font-black uppercase tracking-[0.18em] text-slate-500">{metric.label}</p>
                </div>
              ))}
            </div>
          </div>

          <HeroPreview />
        </div>
      </section>

      <section id="workflow" className="border-b border-white/10 bg-slate-950/40 py-20">
        <div className="mx-auto max-w-7xl px-5 md:px-7">
          <div className="grid gap-10 lg:grid-cols-[0.86fr_1.14fr] lg:items-start">
            <div className="max-w-xl">
              <p className="text-[11px] font-black uppercase tracking-[0.22em] text-cyan-200">Workflow</p>
              <h2 className="mt-4 text-3xl font-black tracking-tight text-white md:text-4xl">
                A tighter path from source material to production output.
              </h2>
              <p className="mt-4 text-base leading-7 text-slate-400">
                The public surface now matches the dashboard’s tone: precise, structured, and built for a real operator workflow instead of generic marketing furniture.
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              {workflowSteps.map((step, index) => (
                <article key={step.title} className="rounded-2xl border border-white/10 bg-[linear-gradient(180deg,rgba(15,23,42,0.92),rgba(7,12,20,0.98))] p-6 shadow-xl shadow-black/10">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-cyan-300/25 bg-cyan-300/[0.08] text-sm font-black text-cyan-100">
                    {index + 1}
                  </div>
                  <h3 className="mt-5 text-xl font-black text-white">{step.title}</h3>
                  <p className="mt-3 text-sm leading-6 text-slate-400">{step.body}</p>
                </article>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section id="studio" className="border-b border-white/10 py-20">
        <div className="mx-auto grid max-w-7xl gap-6 px-5 md:px-7 lg:grid-cols-3">
          {capabilityGroups.map((item, index) => (
            <article
              key={item.title}
              className={`rounded-2xl border p-6 ${index === 1 ? "border-cyan-300/20 bg-cyan-300/[0.05]" : "border-white/10 bg-slate-950/45"}`}
            >
              <p className="text-[11px] font-black uppercase tracking-[0.2em] text-slate-500">Capability</p>
              <h2 className="mt-4 text-2xl font-black tracking-tight text-white">{item.title}</h2>
              <p className="mt-3 text-sm leading-7 text-slate-400">{item.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="security" className="border-b border-white/10 bg-slate-950/38 py-18">
        <div className="mx-auto max-w-7xl px-5 py-20 md:px-7">
          <div className="grid gap-10 lg:grid-cols-[0.78fr_1.22fr] lg:items-center">
            <div className="max-w-xl">
              <p className="text-[11px] font-black uppercase tracking-[0.22em] text-emerald-200">Trust</p>
              <h2 className="mt-4 text-3xl font-black tracking-tight text-white md:text-4xl">
                Modern polish, but still honest about the runtime underneath.
              </h2>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {trustItems.map((item) => (
                <div key={item} className="rounded-2xl border border-white/10 bg-white/[0.04] px-5 py-4 text-sm font-bold text-slate-200">
                  {item}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="py-20">
        <div className="mx-auto max-w-7xl px-5 md:px-7">
          <div className="overflow-hidden rounded-[28px] border border-white/10 bg-[linear-gradient(135deg,rgba(7,18,25,0.98),rgba(13,34,35,0.98))] p-8 shadow-2xl shadow-black/20 md:p-10">
            <div className="grid gap-6 lg:grid-cols-[1fr_auto] lg:items-end">
              <div className="max-w-3xl">
                <p className="text-[11px] font-black uppercase tracking-[0.22em] text-cyan-200">Next step</p>
                <h2 className="mt-4 text-3xl font-black tracking-tight text-white md:text-4xl">
                  Open a workspace that already feels like part of the real product.
                </h2>
              </div>
              <div className="flex flex-wrap gap-3">
                <Link to="/signup" className="inline-flex min-h-12 items-center justify-center rounded-xl border border-emerald-200/55 bg-emerald-300/18 px-5 py-3 text-sm font-bold text-emerald-50 transition hover:bg-emerald-300/28">
                  Start building
                </Link>
                <Link to="/signin" className="inline-flex min-h-12 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] px-5 py-3 text-sm font-bold text-slate-100 transition hover:border-cyan-300/30 hover:bg-cyan-300/[0.08]">
                  Sign in
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
