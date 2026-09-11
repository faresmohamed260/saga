import { BookOpen } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { EmptyState } from "@/components/shell/empty-state";
import { PageHeader } from "@/components/shell/page-header";
import {
  listSagaSources,
  SagaStoryOperationError,
} from "@/server/story/story-data";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Library",
};

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function formatWhen(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Unknown"
    : date.toLocaleDateString("en", { dateStyle: "medium" });
}

export default async function LibraryPage() {
  let sources;
  try {
    sources = await listSagaSources();
  } catch (error) {
    if (error instanceof SagaStoryOperationError && error.code === "unavailable") {
      redirect("/access/unavailable");
    }
    throw error;
  }

  return (
    <div className="flex flex-col gap-10">
      <PageHeader
        eyebrow="Sources"
        title="Library"
        description="The Library is the private record of story originals and deterministic ingestion state that S.A.G.A. can turn into evidence-backed narrative structure."
      />

      <section className="max-w-6xl" aria-labelledby="source-list-heading">
        <div className="flex flex-col gap-2 border-b border-[var(--app-separator)] pb-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 id="source-list-heading" className="text-base font-semibold text-[var(--app-text)]">
              Story sources
            </h2>
            <p className="mt-1 text-sm leading-6 text-[var(--app-muted)]">
              Add UTF-8 text or EPUB files from a project workspace. Upload completion is verified before ingestion work is queued.
            </p>
          </div>
          <Link
            href="/projects"
            className="text-sm font-semibold text-[var(--app-text)] underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
          >
            Manage projects
          </Link>
        </div>

        {sources.length === 0 ? (
          <div className="pt-6">
            <EmptyState
              icon={BookOpen}
              title="No sources yet"
              description="Create or open a project, then add a UTF-8 plain-text or EPUB source from its workspace."
            />
          </div>
        ) : (
          <ul className="divide-y divide-[var(--app-separator)] border-b border-[var(--app-separator)]">
            {sources.map((source) => (
              <li
                key={source.id}
                className="grid gap-3 py-5 lg:grid-cols-[minmax(0,1fr)_8rem_10rem_9rem] lg:items-center"
              >
                <div className="min-w-0">
                  <Link
                    href={`/projects/${source.projectId}`}
                    className="truncate text-sm font-semibold text-[var(--app-text)] underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
                  >
                    {source.displayName}
                  </Link>
                  <p className="mt-1 truncate text-xs text-[var(--app-muted)]">
                    {source.projectTitle ?? "Project"} · {source.originalFilename}
                  </p>
                </div>
                <p className="text-sm uppercase text-[var(--app-muted)]">{source.format}</p>
                <p className="text-sm capitalize text-[var(--app-muted)]">
                  {source.ingestionStatus.replaceAll("_", " ")}
                </p>
                <div className="text-xs text-[var(--app-muted)]">
                  <p>{formatBytes(source.byteSize)}</p>
                  <p className="mt-1">Added {formatWhen(source.createdAt)}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
