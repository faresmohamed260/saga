import { useState } from "react";
import { runtimeApi } from "../../api/runtimeApi";
import { Badge, Button, EmptyState, Field, Panel, toneFor } from "../../components/ui/primitives";
import { useAsync } from "../../hooks/useAsync";
import { useRuntimeState } from "../../hooks/useRuntimeState";

const MODES = ["pre_canon", "mid_canon", "post_canon", "alternate_universe"];

export function DecoderPage() {
  const { state } = useRuntimeState();
  const stories = useAsync(() => runtimeApi.stories(), []);
  const options = useAsync(() => runtimeApi.decoderOptions(), []);
  const firstBook = state?.artifacts?.books?.[0]?.path || "";
  const [payload, setPayload] = useState({ story_mode: "post_canon", book_ref: firstBook, chapter_count: 20, user_prompt: "Write a canon-aware long-form story using the selected mode.", primary_pov_character: "" });
  const [validation, setValidation] = useState(null);

  async function validate() {
    setValidation(await runtimeApi.validateDecoderPlan(payload));
  }
  async function start() {
    const job = await runtimeApi.startDecoder(payload);
    window.location.href = `/runs/${encodeURIComponent(job.id)}`;
  }
  const storyRows = stories.value?.stories || [];
  return (
    <div className="grid gap-5 xl:grid-cols-[520px_1fr]">
      <Panel title="Decoder Controls" subtitle="Validate a generation plan before starting a story job.">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-2">{MODES.map((mode) => <Button key={mode} onClick={() => setPayload({ ...payload, story_mode: mode })} variant={payload.story_mode === mode ? "primary" : "secondary"}>{mode.replaceAll("_", " ")}</Button>)}</div>
          <select value={payload.book_ref} onChange={(event) => setPayload({ ...payload, book_ref: event.target.value })} className="w-full rounded-2xl border border-slate-800 bg-slate-950 p-3 text-sm">
            {(options.value?.books || state?.artifacts?.books || []).map((book) => <option key={book.path || book.book_ref} value={book.path || book.book_ref}>{book.name || book.title}</option>)}
          </select>
          <input type="number" min="1" max="60" value={payload.chapter_count} onChange={(event) => setPayload({ ...payload, chapter_count: Number(event.target.value) })} className="w-full rounded-2xl border border-slate-800 bg-slate-950 p-3 text-sm" />
          <input placeholder="Primary POV character" value={payload.primary_pov_character} onChange={(event) => setPayload({ ...payload, primary_pov_character: event.target.value })} className="w-full rounded-2xl border border-slate-800 bg-slate-950 p-3 text-sm" />
          <textarea value={payload.user_prompt} onChange={(event) => setPayload({ ...payload, user_prompt: event.target.value })} className="min-h-[180px] w-full rounded-2xl border border-slate-800 bg-slate-950 p-3 text-sm" />
          <div className="flex gap-2"><Button onClick={validate}>Validate plan</Button><Button onClick={start} disabled={!validation?.valid} variant="primary">Start generation</Button></div>
          {validation ? <Field label={`Validation: ${validation.valid ? "ready" : "blocked"}`}>{[...(validation.errors || []), ...(validation.warnings || [])].join(" | ") || "Plan is ready."}</Field> : null}
        </div>
      </Panel>
      <Panel title="Generated Stories" subtitle="Persisted stories and export links.">
        {storyRows.length ? <div className="space-y-3">{storyRows.map((story) => (
          <article key={story.id} className="rounded-2xl border border-slate-800 bg-slate-900/45 p-4">
            <div className="flex items-start justify-between gap-3"><h3 className="font-black text-white">{story.title || story.id}</h3><Badge tone={toneFor(story.status)}>{story.status || "unknown"}</Badge></div>
            <p className="mt-2 text-sm text-slate-400">{story.story_mode} · {story.primary_pov_character || "POV n/a"}</p>
            <a className="mt-3 inline-block rounded-xl border border-emerald-500/50 px-3 py-2 text-sm font-bold text-emerald-100" href={`/runtime/export-generated-story-epub?story_id=${encodeURIComponent(story.id)}`}>Export EPUB</a>
          </article>
        ))}</div> : <EmptyState title="No generated stories" />}
      </Panel>
    </div>
  );
}
