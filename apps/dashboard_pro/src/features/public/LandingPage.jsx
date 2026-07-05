import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { capabilityGroups, heroMetrics, publicNavLinks, studioPreviewRows, trustItems, workflowSteps } from "./publicContent";

function PublicNav() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    let animationFrame = 0;

    function updateScrolled() {
      setScrolled(window.scrollY > 18);
    }

    function scheduleUpdate() {
      window.cancelAnimationFrame(animationFrame);
      animationFrame = window.requestAnimationFrame(updateScrolled);
    }

    updateScrolled();
    window.addEventListener("scroll", scheduleUpdate, { passive: true });
    window.addEventListener("wheel", scheduleUpdate, { passive: true });
    window.addEventListener("touchmove", scheduleUpdate, { passive: true });
    const timer = window.setInterval(updateScrolled, 200);
    return () => {
      window.cancelAnimationFrame(animationFrame);
      window.clearInterval(timer);
      window.removeEventListener("scroll", scheduleUpdate);
      window.removeEventListener("wheel", scheduleUpdate);
      window.removeEventListener("touchmove", scheduleUpdate);
    };
  }, []);

  return (
    <div
      className={`fixed inset-x-0 top-0 z-40 transition-all duration-300 ${
        scrolled
          ? "border-b border-white/10 bg-[#07111a]/88 shadow-2xl shadow-black/18 backdrop-blur-xl"
          : "border-b border-transparent bg-transparent"
      }`}
    >
      <nav className="mx-auto flex h-20 max-w-7xl items-center justify-between px-5 md:px-7">
        <Link to="/" className="text-sm font-black tracking-[0.3em] text-white">
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
          <Link to="/signup" className="rounded-lg border border-emerald-300/35 bg-emerald-300/[0.12] px-4 py-2 text-sm font-bold text-emerald-50 transition hover:border-emerald-200/55 hover:bg-emerald-300/[0.2]">
            Sign up
          </Link>
        </div>
      </nav>
    </div>
  );
}

function MiniTimeline() {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.035] p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[11px] font-black uppercase tracking-[0.2em] text-slate-500">Active workflow</p>
          <p className="mt-1 text-lg font-black text-white">Import plan ready</p>
        </div>
        <span className="rounded-full border border-emerald-300/35 bg-emerald-300/[0.1] px-3 py-1 text-[11px] font-black uppercase tracking-[0.16em] text-emerald-100">
          Ready
        </span>
      </div>
      <div className="mt-4 space-y-2.5">
        {studioPreviewRows.map((row) => (
          <div key={row.label} className="grid grid-cols-[1fr_auto] items-center gap-3 rounded-lg border border-white/10 bg-slate-950/62 px-3 py-2.5">
            <span className="text-sm font-bold text-slate-200">{row.label}</span>
            <span className={`text-[11px] font-black uppercase tracking-[0.14em] ${row.tone === "green" ? "text-emerald-200" : row.tone === "blue" ? "text-cyan-200" : "text-slate-400"}`}>
              {row.detail}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function StudioPreview() {
  return (
    <div className="relative mx-auto w-full max-w-[560px]">
      <div className="absolute inset-x-10 top-10 h-44 bg-cyan-300/[0.09] blur-3xl" />
      <div className="relative overflow-hidden rounded-lg border border-white/10 bg-slate-950/74 shadow-2xl shadow-black/28 backdrop-blur">
        <div className="flex h-12 items-center justify-between border-b border-white/10 px-4">
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-300/90" />
            <span className="h-2.5 w-2.5 rounded-full bg-cyan-300/80" />
            <span className="h-2.5 w-2.5 rounded-full bg-slate-500/80" />
          </div>
          <span className="text-[11px] font-black uppercase tracking-[0.18em] text-slate-500">Studio</span>
        </div>
        <div className="grid gap-4 p-4 md:grid-cols-[150px_1fr]">
          <div className="hidden rounded-lg border border-white/10 bg-white/[0.03] p-3 md:block">
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-cyan-200">Queue</p>
            <div className="mt-3 space-y-2">
              {["Overview", "Import", "Library", "Assets"].map((item, index) => (
                <div
                  key={item}
                  className={`rounded-lg border px-3 py-2 text-xs font-bold ${index === 1 ? "border-emerald-300/35 bg-emerald-300/[0.1] text-emerald-50" : "border-white/10 bg-slate-950/50 text-slate-400"}`}
                >
                  {item}
                </div>
              ))}
            </div>
          </div>
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-2.5">
              {heroMetrics.map((metric) => (
                <div key={metric.label} className="rounded-lg border border-white/10 bg-white/[0.04] p-3">
                  <p className="text-xl font-black text-white">{metric.value}</p>
                  <p className="mt-1 truncate text-[10px] font-black uppercase tracking-[0.14em] text-slate-500">{metric.label}</p>
                </div>
              ))}
            </div>
            <MiniTimeline />
          </div>
        </div>
      </div>
    </div>
  );
}

function ProofStrip() {
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {heroMetrics.map((metric) => (
        <div key={metric.label} className="rounded-lg border border-white/10 bg-slate-950/45 px-4 py-3 backdrop-blur">
          <p className="text-xl font-black text-white">{metric.value}</p>
          <p className="mt-1 text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">{metric.label}</p>
        </div>
      ))}
    </div>
  );
}

export function LandingPage() {
  return (
    <main className="min-h-screen text-slate-100">
      <PublicNav />

      <section className="relative overflow-hidden border-b border-white/10">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_8%,rgba(16,185,129,0.14),transparent_27%),radial-gradient(circle_at_76%_12%,rgba(34,211,238,0.12),transparent_24%),linear-gradient(180deg,rgba(6,11,18,0.96),rgba(5,8,14,1))]" />
        <div className="absolute inset-y-0 left-[12%] w-px bg-white/[0.045]" />
        <div className="absolute inset-y-0 right-[18%] w-px bg-white/[0.04]" />
        <div className="relative mx-auto grid min-h-[760px] max-w-7xl gap-10 px-5 pb-14 pt-28 md:px-7 lg:grid-cols-[0.88fr_1.12fr] lg:items-center lg:pb-16 lg:pt-28">
          <div className="max-w-xl">
            <h1 className="text-4xl font-black tracking-tight text-white sm:text-5xl lg:text-6xl lg:leading-[1.02]">
              Story Production Studio
            </h1>
            <p className="mt-5 max-w-xl text-base leading-7 text-slate-300 md:text-lg md:leading-8">
              Import books, inspect canon memory, manage visual assets, generate stories, and produce audiobooks from one connected workspace.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link to="/signup" className="inline-flex min-h-11 items-center justify-center rounded-lg border border-emerald-300/35 bg-emerald-300/[0.12] px-4 py-2.5 text-sm font-bold text-emerald-50 transition hover:border-emerald-200/55 hover:bg-emerald-300/[0.2]">
                Start building
              </Link>
              <Link to="/overview" className="inline-flex min-h-11 items-center justify-center rounded-lg border border-white/10 bg-white/[0.04] px-4 py-2.5 text-sm font-bold text-slate-100 transition hover:border-cyan-300/30 hover:bg-cyan-300/[0.08]">
                View studio
              </Link>
            </div>
            <div className="mt-8 max-w-lg">
              <ProofStrip />
            </div>
          </div>

          <StudioPreview />
        </div>
      </section>

      <section id="workflow" className="border-b border-white/10 bg-slate-950/40 py-16">
        <div className="mx-auto max-w-7xl px-5 md:px-7">
          <div className="grid gap-8 lg:grid-cols-[0.84fr_1.16fr] lg:items-start">
            <div className="max-w-xl">
              <p className="text-[11px] font-black uppercase tracking-[0.18em] text-cyan-200">Workflow</p>
              <h2 className="mt-3 text-3xl font-black tracking-tight text-white md:text-4xl">
                A cleaner path from source material to production output.
              </h2>
              <p className="mt-4 text-base leading-7 text-slate-400">
                Keep the whole production loop visible without crowding the screen: ingestion, canon review, generation, assets, and audio staging.
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              {workflowSteps.map((step, index) => (
                <article key={step.title} className="rounded-lg border border-white/10 bg-[linear-gradient(180deg,rgba(15,23,42,0.72),rgba(7,12,20,0.96))] p-5 shadow-xl shadow-black/10">
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-cyan-300/25 bg-cyan-300/[0.08] text-sm font-black text-cyan-100">
                    {index + 1}
                  </div>
                  <h3 className="mt-4 text-lg font-black text-white">{step.title}</h3>
                  <p className="mt-3 text-sm leading-6 text-slate-400">{step.body}</p>
                </article>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section id="studio" className="border-b border-white/10 py-16">
        <div className="mx-auto grid max-w-7xl gap-4 px-5 md:px-7 lg:grid-cols-3">
          {capabilityGroups.map((item, index) => (
            <article
              key={item.title}
              className={`rounded-lg border p-5 ${index === 1 ? "border-cyan-300/20 bg-cyan-300/[0.05]" : "border-white/10 bg-slate-950/45"}`}
            >
              <p className="text-[11px] font-black uppercase tracking-[0.18em] text-slate-500">Capability</p>
              <h2 className="mt-3 text-xl font-black tracking-tight text-white">{item.title}</h2>
              <p className="mt-3 text-sm leading-7 text-slate-400">{item.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="security" className="border-b border-white/10 bg-slate-950/38 py-16">
        <div className="mx-auto grid max-w-7xl gap-8 px-5 md:px-7 lg:grid-cols-[0.78fr_1.22fr] lg:items-center">
          <div className="max-w-xl">
            <p className="text-[11px] font-black uppercase tracking-[0.18em] text-emerald-200">Trust</p>
            <h2 className="mt-3 text-3xl font-black tracking-tight text-white md:text-4xl">
              Professional polish with the runtime still visible.
            </h2>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {trustItems.map((item) => (
              <div key={item} className="rounded-lg border border-white/10 bg-white/[0.04] px-4 py-3 text-sm font-bold text-slate-200">
                {item}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="py-16">
        <div className="mx-auto max-w-7xl px-5 md:px-7">
          <div className="overflow-hidden rounded-lg border border-white/10 bg-[linear-gradient(135deg,rgba(7,18,25,0.98),rgba(13,34,35,0.98))] p-6 shadow-2xl shadow-black/20 md:p-8">
            <div className="grid gap-6 lg:grid-cols-[1fr_auto] lg:items-end">
              <div className="max-w-2xl">
                <p className="text-[11px] font-black uppercase tracking-[0.18em] text-cyan-200">Next step</p>
                <h2 className="mt-3 text-2xl font-black tracking-tight text-white md:text-3xl">
                  Open a workspace that feels like the product, not a poster for it.
                </h2>
              </div>
              <div className="flex flex-wrap gap-3">
                <Link to="/signup" className="inline-flex min-h-11 items-center justify-center rounded-lg border border-emerald-200/55 bg-emerald-300/[0.16] px-4 py-2.5 text-sm font-bold text-emerald-50 transition hover:bg-emerald-300/[0.24]">
                  Start building
                </Link>
                <Link to="/signin" className="inline-flex min-h-11 items-center justify-center rounded-lg border border-white/10 bg-white/[0.04] px-4 py-2.5 text-sm font-bold text-slate-100 transition hover:border-cyan-300/30 hover:bg-cyan-300/[0.08]">
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
