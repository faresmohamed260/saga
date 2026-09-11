import { FolderKanban } from "lucide-react";
import type { Metadata } from "next";

import { EmptyState } from "@/components/shell/empty-state";
import { PageHeader } from "@/components/shell/page-header";

export const metadata: Metadata = {
  title: "Projects",
};

export default function ProjectsPage() {
  return (
    <div className="flex flex-col gap-10">
      <PageHeader
        eyebrow="Story workspaces"
        title="Projects"
        description="Projects will organize each narrative system into a durable workspace for canon, characters, world structure, timelines, story, and media."
      />

      <div className="max-w-6xl">
        <EmptyState
          icon={FolderKanban}
          title="No projects yet"
          description="Project persistence and creation have not shipped yet. This list will stay empty rather than presenting fabricated stories or progress state."
        />
      </div>
    </div>
  );
}
