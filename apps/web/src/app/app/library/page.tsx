import { BookOpenText } from "lucide-react";

export default function LibraryPage() {
  return (
    <section className="max-w-4xl">
      <BookOpenText className="text-violet-200" size={24} />
      <h1 className="mt-5 text-3xl font-semibold tracking-[-0.035em]">Library</h1>
      <p className="mt-4 max-w-2xl text-sm leading-7 text-zinc-500">
        This will become the source-ingestion and edition workspace. Real uploads remain disabled until scoped B2 runtime credentials and the S.A.G.A. Supabase project are connected.
      </p>
      <div className="mt-8 rounded-2xl border border-dashed border-white/10 p-8 text-sm text-zinc-600">No sources yet.</div>
    </section>
  );
}
