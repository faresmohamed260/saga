import { Activity, BookOpen, Users } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { PageHeader } from "@/components/shell/page-header";
import { SourceUploadForm } from "@/features/library/source-upload-form";
import {
  getSagaProjectWorkspace,
  SagaStoryOperationError,
  type SagaAnalysisJob,
} from "@/server/story/story-data";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Project",
};

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function latestJobBySource(jobs: SagaAnalysisJob[]) {
  const latest = new Map<string, SagaAnalysisJob>();
  for (const job of jobs) {
    if (!latest.has(job.sourceId)) latest.set(job.sourceId, job);
  }
  return latest;
}

function statusLabel(value: string) {
  return value.replaceAll("_", " ");
}

export default async function ProjectWorkspacePage({
  params,
  searchParams,
}: Readonly<{
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{ notice?: string }>;
}>) {
  const { projectId } = await params;
  let workspace;

  try {
    workspace = await getSagaProjectWorkspace(projectId);
  } catch (error) {
    if (error instanceof SagaStoryOperationError && error.code === "unavailable") {
      redirect("/access/unavailable");
    }
    throw error;
  }

  if (!workspace) notFound();

  const { notice } = await searchParams;
  const latestJobs = latestJobBySource(workspace.jobs);
  const activeJobs = workspace.jobs.filter(
    (job) => job.status === "queued" || job.status === "running",
  ).length;

  return (
    <div className="flex flex-col gap-10">
      <PageHeader
        eyebrow="Project workspace"
        title={workspace.project.title}
        description={
          workspace.project.description ??
          "This project owns its sources, analysis provenance, and evidence-backed narrative results."
        }
      />

      {notice === "project_created" ? (
        <p
          role="status"
          className="max-w-4xl border-y border-[var(--app-separator)] py-3 text-sm leading-6 text-[var(--app-muted)]"
        >
          Project created. Add a UTF-8 text or EPUB source when you are ready.
        </p>
      ) : null}

      <section className="max-w-6xl" aria-labelledby="overview-heading">
        <div className="border-b border-[var(--app-separator)] pb-4">
          <h2 id="overview-heading" className="text-base font-semibold text-[var(--app-text)]">
            Overview
          </h2>
          <p className="mt-1 text-sm leading-6 text-[var(--app-muted)]">
            These counts come from private project-owned records, not inferred client state.
          </p>
        </div>

        <dl className="grid gap-6 border-b border-[var(--app-separator)] py-6 sm:grid-cols-3">
          <div>
            <dt className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--app-muted)]">
              <BookOpen className="size-4" aria-hidden="true" />
              Sources
            </dt>
            <dd className="mt-2 text-2xl font-semibold text-[var(--app-text)]">
              {workspace.sources.length}
            </dd>
          </div>
          <div>
            <dt className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--app-muted)]">
              <Activity className="size-4" aria-hidden="true" />
              Active jobs
            </dt>
            <dd className="mt-2 text-2xl font-semibold text-[var(--app-text)]">{activeJobs}</dd>
          </div>
          <div>
            <dt className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--app-muted)]">
              <Users className="size-4" aria-hidden="true" />
              Characters
            </dt>
            <dd className="mt-2 text-2xl font-semibold text-[var(--app-text)]">
              {workspace.characterCount}
            </dd>
          </div>
        </dl>
      </section>

      <section className="max-w-6xl" aria-labelledby="sources-heading">
        <div className="flex flex-col gap-2 border-b border-[var(--app-separator)] pb-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 id="sources-heading" className="text-base font-semibold text-[var(--app-text)]">
              Sources
            </h2>
            <p className="mt-1 text-sm leading-6 text-[var(--app-muted)]">
              Originals stay private in object storage. Upload completion is verified before deterministic ingestion is queued.
            </p>
          </div>
          <Link
            href="/library"
            className="text-sm font-semibold text-[var(--app-text)] underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
          >
            Open Library
          </Link>
        </div>

        <SourceUploadForm projectId={workspace.project.id} />

        {workspace.sources.length === 0 ? (
          <p className="border-b border-[var(--app-separator)] py-8 text-sm leading-6 text-[var(--app-muted)]">
            No source records yet. Add a UTF-8 plain-text or EPUB source above.
          </p>
        ) : (
          <ul className="divide-y divide-[var(--app-separator)] border-b border-[var(--app-separator)]">
            {workspace.sources.map((source) => {
              const latestJob = latestJobs.get(source.id);
              const canReadOriginal =
                source.ingestionStatus === "uploaded" ||
                source.ingestionStatus === "processing" ||
                source.ingestionStatus === "ready";
              return (
                <li
                  key={source.id}
                  className="grid gap-3 py-5 lg:grid-cols-[minmax(0,1fr)_7rem_9rem_10rem_auto] lg:items-center"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-[var(--app-text)]">
                      {source.displayName}
                    </p>
                    <p className="mt-1 truncate text-xs text-[var(--app-muted)]">
                      {source.originalFilename} · {formatBytes(source.byteSize)}
                    </p>
                  </div>
                  <p className="text-sm uppercase text-[var(--app-muted)]">{source.format}</p>
                  <p className="text-sm capitalize text-[var(--app-muted)]">
                    {statusLabel(source.ingestionStatus)}
                  </p>
                  <p className="text-xs capitalize text-[var(--app-muted)]">
                    {latestJob ? `${statusLabel(latestJob.kind)}: ${latestJob.status}` : "No analysis job"}
                  </p>
                  {canReadOriginal ? (
                    <a
                      href={`/api/sources/${source.id}/original`}
                      className="text-sm font-semibold text-[var(--app-text)] underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
                    >
                      Original
                    </a>
                  ) : (
                    <span className="text-xs text-[var(--app-muted)]">Unavailable</span>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="max-w-6xl" aria-labelledby="analysis-heading">
        <div className="border-b border-[var(--app-separator)] pb-4">
          <h2 id="analysis-heading" className="text-base font-semibold text-[var(--app-text)]">
            Analysis
          </h2>
          <p className="mt-1 text-sm leading-6 text-[var(--app-muted)]">
            Durable jobs are separate from immutable analysis runs. Full-book work executes outside the web request boundary.
          </p>
        </div>

        {workspace.jobs.length === 0 ? (
          <p className="border-b border-[var(--app-separator)] py-8 text-sm text-[var(--app-muted)]">
            No analysis jobs have been requested for this project.
          </p>
        ) : (
          <ul className="divide-y divide-[var(--app-separator)] border-b border-[var(--app-separator)]">
            {workspace.jobs.slice(0, 12).map((job) => (
              <li key={job.id} className="grid gap-2 py-4 sm:grid-cols-[minmax(0,1fr)_8rem_8rem] sm:items-center">
                <p className="text-sm capitalize text-[var(--app-text)]">{statusLabel(job.kind)}</p>
                <p className="text-sm capitalize text-[var(--app-muted)]">{job.status}</p>
                <p className="text-xs text-[var(--app-muted)]">
                  Attempt {job.attemptCount}/{job.maxAttempts}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="max-w-6xl" aria-labelledby="characters-heading">
        <div className="border-b border-[var(--app-separator)] pb-4">
          <h2 id="characters-heading" className="text-base font-semibold text-[var(--app-text)]">
            Characters
          </h2>
          <p className="mt-1 text-sm leading-6 text-[var(--app-muted)]">
            Character identities remain empty until the Phase 2C resolver writes evidence-backed results. Unresolved mentions will not be counted as canonicals.
          </p>
        </div>
        <p className="border-b border-[var(--app-separator)] py-8 text-sm text-[var(--app-muted)]">
          {workspace.characterCount === 0
            ? "No resolved characters yet."
            : `${workspace.characterCount} resolved character${workspace.characterCount === 1 ? "" : "s"} recorded for this project.`}
        </p>
      </section>
    </div>
  );
}
