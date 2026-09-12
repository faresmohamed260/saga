import { ArrowRight, BookOpen, FolderKanban } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { PageHeader } from "@/components/shell/page-header";

export const metadata: Metadata = {
  title: "Home",
};

const workspaceLinks = [
  {
    href: "/library",
    title: "Library",
    description: "Private source records, upload verification, and deterministic ingestion state live here.",
    icon: BookOpen,
  },
  {
    href: "/projects",
    title: "Projects",
    description: "Create private story workspaces that own sources, analysis provenance, character evidence, and later canon.",
    icon: FolderKanban,
  },
] as const;

export default function HomePage() {
  return (
    <div className="flex flex-col gap-10">
      <PageHeader
        eyebrow="Narrative Desk"
        title="Home"
        description="S.A.G.A. is your private workspace for turning narrative sources into structured, inspectable story systems."
      />

      <section aria-labelledby="workspace-heading" className="max-w-5xl">
        <div className="mb-4 flex items-end justify-between gap-4">
          <div>
            <h2 id="workspace-heading" className="text-base font-semibold text-[var(--app-text)]">
              Workspace
            </h2>
            <p className="mt-1 text-sm leading-6 text-[var(--app-muted)]">
              Projects own your private story boundaries. Add UTF-8 text or EPUB sources from a project workspace; ingestion runs outside the web request.
            </p>
          </div>
        </div>

        <div className="border-y border-[var(--app-separator)]">
          {workspaceLinks.map(({ href, title, description, icon: Icon }, index) => (
            <Link
              key={href}
              href={href}
              className={`group flex min-h-24 items-center gap-4 px-1 py-5 transition-colors hover:bg-white/[0.025] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--app-focus)] ${
                index > 0 ? "border-t border-[var(--app-separator)]" : ""
              }`}
            >
              <div className="flex size-10 shrink-0 items-center justify-center rounded-full border border-[var(--app-separator)] bg-[var(--app-surface)] text-[var(--app-muted)] transition-colors group-hover:text-[var(--app-text)]">
                <Icon aria-hidden="true" className="size-[18px]" strokeWidth={1.8} />
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="text-sm font-semibold text-[var(--app-text)]">{title}</h3>
                <p className="mt-1 max-w-2xl text-sm leading-5 text-[var(--app-muted)]">{description}</p>
              </div>
              <ArrowRight
                aria-hidden="true"
                className="mr-2 size-[18px] shrink-0 text-[var(--app-muted)] transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-[var(--app-text)]"
                strokeWidth={1.8}
              />
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
