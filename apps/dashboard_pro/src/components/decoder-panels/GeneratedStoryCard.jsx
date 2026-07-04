import { Badge, DataCard, toneFor } from "../primitives";

export function GeneratedStoryCard({ story }) {
  return (
    <DataCard>
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-black text-white">{story.title || story.id}</h3>
        <Badge tone={toneFor(story.status)}>{story.status || "unknown"}</Badge>
      </div>
      <p className="mt-2 text-sm text-slate-400">
        {story.story_mode} / {story.primary_pov_character || "POV n/a"} / {story.series_id || story.series_title || "series n/a"}
      </p>
      <a
        className="mt-3 inline-flex rounded-lg border border-emerald-400/50 bg-emerald-400/10 px-3 py-2 text-sm font-bold text-emerald-100 transition hover:bg-emerald-400/20"
        href={`/runtime/export-generated-story-epub?story_id=${encodeURIComponent(story.id)}`}
      >
        Export EPUB
      </a>
    </DataCard>
  );
}
