import Link from "next/link";
import { BookOpenText, FolderKanban, Network, MapPinned, Clock3, Database, Images, ArrowRight } from "lucide-react";

const areas = [
  { label: "Library", detail: "Source books, editions, chapters and imports", href: "/app/library", icon: BookOpenText, active: true },
  { label: "Projects", detail: "Story workspaces and reconstruction sessions", href: "/app/projects", icon: FolderKanban, active: true },
  { label: "Canon", detail: "Evidence-backed facts and contradictions", icon: Database, active: false },
  { label: "Characters", detail: "Identity, aliases and relationships", icon: Network, active: false },
  { label: "World", detail: "Locations, entities and world structure", icon: MapPinned, active: false },
  { label: "Timeline", detail: "Events, ordering and causality", icon: Clock3, active: false },
  { label: "Media", detail: "Grounded visual and audio outputs", icon: Images, active: false },
];

export default function AppHomePage() {
  return (
    <div>
      <div className="max-w-3xl">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-violet-300">Workspace</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-[-0.035em] sm:text-4xl">Build a story model you can trust.</h1>
        <p className="mt-4 max-w-2xl text-sm leading-7 text-zinc-500 sm:text-base">
          Phase 1 is establishing the durable application and account foundation. Narrative intelligence will attach to these user-facing concepts rather than exposing an internal AI pipeline.
        </p>
      </div>

      <section className="mt-10 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {areas.map(({ label, detail, href, icon: Icon, active }) => {
          const content = (
            <div className="group h-full rounded-2xl border border-white/8 bg-white/[0.025] p-5 transition hover:border-violet-300/15 hover:bg-white/[0.04]">
              <div className="flex items-start justify-between gap-4">
                <span className="flex size-10 items-center justify-center rounded-xl border border-white/8 bg-white/[0.035] text-zinc-300">
                  <Icon size={18} strokeWidth={1.7} />
                </span>
                {active ? <ArrowRight size={16} className="mt-1 text-zinc-600 transition group-hover:translate-x-0.5 group-hover:text-violet-200" /> : <span className="text-[10px] font-medium uppercase tracking-[0.15em] text-zinc-600">Later</span>}
              </div>
              <h2 className="mt-5 text-base font-semibold">{label}</h2>
              <p className="mt-2 text-sm leading-6 text-zinc-500">{detail}</p>
            </div>
          );
          return active && href ? <Link key={label} href={href}>{content}</Link> : <div key={label}>{content}</div>;
        })}
      </section>
    </div>
  );
}
