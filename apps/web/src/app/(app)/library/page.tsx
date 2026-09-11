import { BookOpen } from "lucide-react";
import type { Metadata } from "next";

import { EmptyState } from "@/components/shell/empty-state";
import { PageHeader } from "@/components/shell/page-header";

export const metadata: Metadata = {
  title: "Library",
};

export default function LibraryPage() {
  return (
    <div className="flex flex-col gap-10">
      <PageHeader
        eyebrow="Sources"
        title="Library"
        description="The Library will hold the novels, editions, and other source material that S.A.G.A. can turn into evidence-backed narrative structure."
      />

      <div className="max-w-6xl">
        <EmptyState
          icon={BookOpen}
          title="No sources yet"
          description="Source ingestion is not part of Phase 1D, so this workspace stays deliberately empty until the repository has a real source contract to display."
        />
      </div>
    </div>
  );
}
