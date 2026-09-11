import { FolderKanban, Plus } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { EmptyState } from "@/components/shell/empty-state";
import { PageHeader } from "@/components/shell/page-header";
import { createProjectAction } from "@/features/projects/actions";
import {
  listSagaProjects,
  SagaStoryOperationError,
} from "@/server/story/story-data";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Projects",
};

const noticeCopy: Record<string, string> = {
  invalid_request: "Give the project a title between 1 and 160 characters. Descriptions are optional.",
  unavailable: "Projects are temporarily unavailable. Nothing was created.",
};

function formatWhen(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Unknown"
    : date.toLocaleDateString("en", { dateStyle: "medium" });
}

export default async function ProjectsPage({
  searchParams,
}: Readonly<{ searchParams: Promise<{ notice?: string }> }>) {
  let projects;
  try {
    projects = await listSagaProjects();
  } catch (error) {
    if (error instanceof SagaStoryOperationError && error.code === "unavailable") {
      redirect("/access/unavailable");
    }
    throw error;
  }

  const { notice } = await searchParams;
  const message = notice ? noticeCopy[notice] : undefined;

  return (
    <div className="flex flex-col gap-10">
      <PageHeader
        eyebrow="Story workspaces"
        title="Projects"
        description="Create a durable workspace for one narrative system. Sources, analysis runs, character evidence, and later canon stay scoped to the project that owns them."
      />

      {message ? (
        <p
          role="status"
          className="max-w-4xl border-y border-[var(--app-separator)] py-3 text-sm leading-6 text-[var(--app-muted)]"
        >
          {message}
        </p>
      ) : null}

      <section className="max-w-6xl" aria-labelledby="create-project-heading">
        <div className="border-b border-[var(--app-separator)] pb-6">
          <div className="max-w-2xl">
            <h2 id="create-project-heading" className="text-base font-semibold text-[var(--app-text)]">
              New project
            </h2>
            <p className="mt-1 text-sm leading-6 text-[var(--app-muted)]">
              Start with the story boundary. Source upload and ingestion attach to this project in the next Phase 2 slice.
            </p>
          </div>

          <form action={createProjectAction} className="mt-5 grid max-w-3xl gap-4">
            <label className="grid gap-1 text-xs font-medium text-[var(--app-muted)]">
              Project title
              <input
                required
                maxLength={160}
                name="title"
                autoComplete="off"
                className="min-h-11 rounded-lg border border-[var(--app-separator)] bg-[var(--app-surface)] px-3 text-sm text-[var(--app-text)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
                placeholder="The Glass Archive"
              />
            </label>

            <label className="grid gap-1 text-xs font-medium text-[var(--app-muted)]">
              Description <span className="font-normal">(optional)</span>
              <textarea
                maxLength={4000}
                name="description"
                rows={3}
                className="rounded-lg border border-[var(--app-separator)] bg-[var(--app-surface)] px-3 py-2 text-sm leading-6 text-[var(--app-text)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
                placeholder="What story or series does this workspace represent?"
              />
            </label>

            <button
              type="submit"
              className="flex min-h-11 w-fit items-center gap-2 rounded-lg bg-[var(--app-text)] px-4 text-sm font-semibold text-[var(--app-canvas)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)]"
            >
              <Plus className="size-4" aria-hidden="true" />
              Create project
            </button>
          </form>
        </div>
      </section>

      <section className="max-w-6xl" aria-labelledby="project-list-heading">
        <div className="border-b border-[var(--app-separator)] pb-4">
          <h2 id="project-list-heading" className="text-base font-semibold text-[var(--app-text)]">
            Your projects
          </h2>
          <p className="mt-1 text-sm leading-6 text-[var(--app-muted)]">
            Projects are private to your admitted S.A.G.A. account in this phase.
          </p>
        </div>

        {projects.length === 0 ? (
          <div className="pt-6">
            <EmptyState
              icon={FolderKanban}
              title="No projects yet"
              description="Create the first project above. It becomes the ownership boundary for every source and analysis result that follows."
            />
          </div>
        ) : (
          <ul className="divide-y divide-[var(--app-separator)] border-b border-[var(--app-separator)]">
            {projects.map((project) => (
              <li key={project.id}>
                <Link
                  href={`/projects/${project.id}`}
                  className="group grid gap-2 py-5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--app-focus)] sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="truncate text-sm font-semibold text-[var(--app-text)] group-hover:underline">
                        {project.title}
                      </h3>
                      {project.status === "archived" ? (
                        <span className="text-[0.68rem] font-semibold uppercase tracking-[0.12em] text-[var(--app-muted)]">
                          Archived
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-1 line-clamp-2 text-sm leading-6 text-[var(--app-muted)]">
                      {project.description ?? "No project description yet."}
                    </p>
                  </div>
                  <p className="text-xs text-[var(--app-muted)]">
                    Updated {formatWhen(project.updatedAt)}
                  </p>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
