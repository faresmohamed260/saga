import { Activity } from "lucide-react";

export default function ActivityPage() {
  return (
    <section className="max-w-4xl">
      <Activity className="text-violet-200" size={24} />
      <h1 className="mt-5 text-3xl font-semibold tracking-[-0.035em]">Activity</h1>
      <p className="mt-4 max-w-2xl text-sm leading-7 text-zinc-500">
        Durable import, analysis and generation jobs will appear here after the application job contract is introduced. This surface will reflect real server state only.
      </p>
      <div className="mt-8 rounded-2xl border border-dashed border-white/10 p-8 text-sm text-zinc-600">No activity yet.</div>
    </section>
  );
}
