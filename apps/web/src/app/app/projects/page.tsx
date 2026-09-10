import { FolderKanban } from "lucide-react";

export default function ProjectsPage() {
  return (
    <section className="max-w-4xl">
      <FolderKanban className="text-violet-200" size={24} />
      <h1 className="mt-5 text-3xl font-semibold tracking-[-0.035em]">Projects</h1>
      <p className="mt-4 max-w-2xl text-sm leading-7 text-zinc-500">
        Story workspaces will own source sets, structured narrative state, canon exploration and later generation activity. The relational model is intentionally deferred until the account foundation is live.
      </p>
      <div className="mt-8 rounded-2xl border border-dashed border-white/10 p-8 text-sm text-zinc-600">No projects yet.</div>
    </section>
  );
}
