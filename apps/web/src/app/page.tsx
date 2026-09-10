import Link from "next/link";
import {
  ArrowRight,
  AudioLines,
  BookOpenText,
  Boxes,
  Clock3,
  Database,
  Images,
  Network,
  Sparkles,
} from "lucide-react";

const productAreas = [
  { label: "Library", detail: "Sources & editions", icon: BookOpenText },
  { label: "Canon", detail: "Facts & evidence", icon: Database },
  { label: "Characters", detail: "Identity & relationships", icon: Network },
  { label: "World", detail: "Locations & entities", icon: Boxes },
  { label: "Timeline", detail: "Events & causality", icon: Clock3 },
  { label: "Media", detail: "Visual & audio outputs", icon: Images },
];

const principles = [
  {
    eyebrow: "Understand",
    title: "Turn source material into structured story memory.",
    body: "Books become navigable projects with chapters, scenes, characters, places, events, canon facts, and traceable evidence.",
  },
  {
    eyebrow: "Connect",
    title: "Explore a story as a living world, not a pile of text.",
    body: "Follow identities, relationships, timelines, locations, and causal links through one coherent application model.",
  },
  {
    eyebrow: "Create",
    title: "Generate from canon instead of guessing from context windows.",
    body: "The later agentic layer will plan stories and media against durable application state and evidence-backed world knowledge.",
  },
];

export default function Home() {
  return (
    <main className="relative min-h-screen overflow-hidden">
      <div className="saga-grid pointer-events-none absolute inset-0" />
      <div className="pointer-events-none absolute left-1/2 top-[-20rem] h-[36rem] w-[36rem] -translate-x-1/2 rounded-full bg-violet-500/10 blur-3xl" />

      <div className="relative mx-auto flex min-h-screen w-full max-w-[1440px] flex-col px-5 pb-12 sm:px-8 lg:px-12">
        <header className="flex h-20 items-center justify-between border-b border-white/8">
          <Link href="/" className="flex items-center gap-3" aria-label="S.A.G.A. home">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl border border-violet-300/20 bg-violet-400/10 text-violet-200 shadow-[inset_0_1px_0_rgba(255,255,255,.08)]">
              <Sparkles size={17} strokeWidth={1.8} />
            </span>
            <span className="text-sm font-semibold tracking-[0.24em] text-white">S.A.G.A.</span>
          </Link>

          <div className="flex items-center gap-2 text-sm">
            <span className="hidden rounded-full border border-white/8 bg-white/[0.025] px-3 py-1.5 text-zinc-400 sm:inline-flex">
              v2 foundation
            </span>
            <Link
              href="/api/health"
              className="rounded-full border border-white/10 px-4 py-2 text-zinc-200 transition hover:border-white/20 hover:bg-white/[0.04]"
            >
              System status
            </Link>
          </div>
        </header>

        <section className="grid flex-1 items-center gap-12 py-20 lg:grid-cols-[1.03fr_.97fr] lg:py-24">
          <div className="max-w-3xl">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-violet-300/15 bg-violet-300/[0.06] px-3 py-1.5 text-xs font-medium tracking-wide text-violet-200">
              <span className="h-1.5 w-1.5 rounded-full bg-violet-300 shadow-[0_0_16px_rgba(196,181,253,.9)]" />
              Story intelligence, rebuilt for the web
            </div>

            <h1 className="max-w-4xl text-balance text-5xl font-semibold leading-[0.98] tracking-[-0.055em] text-white sm:text-6xl lg:text-[5.2rem]">
              Understand stories.
              <span className="block bg-gradient-to-r from-violet-200 via-white to-cyan-200 bg-clip-text text-transparent">
                Build from canon.
              </span>
            </h1>

            <p className="mt-7 max-w-2xl text-pretty text-base leading-7 text-zinc-400 sm:text-lg sm:leading-8">
              S.A.G.A. turns narrative sources into structured, explorable worlds—then gives future agents a reliable foundation for grounded storytelling and multimedia creation.
            </p>

            <div className="mt-9 flex flex-wrap items-center gap-3">
              <a
                href="#workspace"
                className="group inline-flex items-center gap-2 rounded-xl bg-white px-5 py-3 text-sm font-semibold text-zinc-950 transition hover:bg-violet-100"
              >
                Explore the workspace
                <ArrowRight size={16} className="transition group-hover:translate-x-0.5" />
              </a>
              <Link
                href="https://github.com/faresmohamed260/saga"
                className="inline-flex items-center rounded-xl border border-white/10 bg-white/[0.025] px-5 py-3 text-sm font-medium text-zinc-200 transition hover:border-white/20 hover:bg-white/[0.05]"
              >
                View source
              </Link>
            </div>
          </div>

          <div id="workspace" className="saga-panel saga-glow saga-float relative rounded-[1.75rem] p-3 sm:p-4">
            <div className="rounded-[1.35rem] border border-white/8 bg-[#090d14]/95 p-4 sm:p-5">
              <div className="mb-5 flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium uppercase tracking-[0.18em] text-zinc-500">Workspace</p>
                  <h2 className="mt-1 text-lg font-semibold tracking-tight text-white">A story becomes a system.</h2>
                </div>
                <span className="rounded-lg border border-emerald-300/10 bg-emerald-300/[0.06] px-2.5 py-1 text-[11px] font-medium text-emerald-200">
                  Web foundation
                </span>
              </div>

              <div className="grid gap-2 sm:grid-cols-2">
                {productAreas.map(({ label, detail, icon: Icon }, index) => (
                  <div
                    key={label}
                    className="group flex items-center gap-3 rounded-xl border border-white/[0.065] bg-white/[0.018] p-3.5 transition hover:border-violet-300/15 hover:bg-violet-300/[0.035]"
                  >
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-white/8 bg-white/[0.025] text-zinc-300 group-hover:text-violet-200">
                      <Icon size={16} strokeWidth={1.7} />
                    </span>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-zinc-100">{label}</span>
                        {index === 0 ? (
                          <span className="rounded bg-violet-300/10 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-violet-200">
                            first
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-0.5 truncate text-xs text-zinc-500">{detail}</p>
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-3 grid gap-3 rounded-xl border border-white/[0.065] bg-gradient-to-br from-violet-400/[0.05] to-cyan-300/[0.025] p-4 sm:grid-cols-[1fr_auto] sm:items-center">
                <div>
                  <div className="flex items-center gap-2 text-sm font-medium text-white">
                    <AudioLines size={15} className="text-cyan-200" />
                    Agentic intelligence comes after the product foundation.
                  </div>
                  <p className="mt-1.5 text-xs leading-5 text-zinc-500">
                    The web app owns durable state, storage and jobs. Future agents plug into those contracts—not the other way around.
                  </p>
                </div>
                <div className="hidden h-10 w-px bg-white/8 sm:block" />
              </div>
            </div>
          </div>
        </section>

        <section className="grid gap-px overflow-hidden rounded-2xl border border-white/8 bg-white/8 md:grid-cols-3">
          {principles.map((item) => (
            <article key={item.eyebrow} className="bg-[#0a0e15] p-6 sm:p-7">
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-violet-300">{item.eyebrow}</p>
              <h2 className="mt-4 text-lg font-semibold leading-6 tracking-tight text-white">{item.title}</h2>
              <p className="mt-3 text-sm leading-6 text-zinc-500">{item.body}</p>
            </article>
          ))}
        </section>

        <footer className="mt-8 flex flex-col gap-3 border-t border-white/8 pt-6 text-xs text-zinc-600 sm:flex-row sm:items-center sm:justify-between">
          <span>S.A.G.A. · Story Analysis, Generation & Archives</span>
          <span>GitHub · Vercel · Supabase · Cloudflare · Backblaze B2</span>
        </footer>
      </div>
    </main>
  );
}
