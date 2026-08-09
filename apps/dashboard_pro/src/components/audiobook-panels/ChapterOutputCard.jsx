import { runtimeApi } from "../../api/runtimeApi";
import { artifactUrl } from "../../api/artifactUrls";
import { Button, DataCard, Toolbar } from "../primitives";
import { chapterLabel } from "../../features/audiobook/audiobookUtils";

export function ChapterOutputCard({ selectedRun, chapter, expanded, onToggle }) {
  const audioUrl = artifactUrl(chapter.audio_artifact || chapter.audio_file)
    || runtimeApi.audiobookChapterAudioUrl(selectedRun.id, chapter.chapter_id);
  const filename = `${selectedRun.title || "audiobook"}-book-${chapter.book_index || "x"}-chapter-${chapter.chapter_index || "x"}.${selectedRun.audio_format || "wav"}`;
  return (
    <DataCard className="bg-[#0b1117]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-black text-white">{chapter.chapter_title || `Chapter ${chapter.chapter_index || "?"}`}</p>
          <p className="mt-1 text-sm text-slate-400">{chapterLabel(chapter)}</p>
        </div>
        <Toolbar>
          <Button type="button" onClick={onToggle}>
            {expanded ? "Collapse" : "Expand"}
          </Button>
          <a
            href={audioUrl}
            download={filename}
            className="rounded-lg border border-emerald-400/50 bg-emerald-400/10 px-4 py-2 text-sm font-bold text-emerald-100 transition hover:bg-emerald-400/20"
          >
            Download
          </a>
        </Toolbar>
      </div>
      {expanded ? <audio className="mt-4 w-full" controls preload="none" src={audioUrl} /> : null}
    </DataCard>
  );
}
