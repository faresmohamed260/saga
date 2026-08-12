"""Deterministic LangGraph pipeline for the analysis foundation."""

from __future__ import annotations

import hashlib
import time
import re
from pathlib import Path
from typing import Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from packages.agent_runtime import SqlCheckpointSaver
from packages.analysis_foundation.contracts import (
    AnalysisFoundationResult,
    BookArtifact,
    CanonicalCharacter,
    CanonicalIdentityBundle,
    ChapterArtifact,
    NarratorReferenceData,
    SceneArtifact,
)
from packages.analysis_foundation.store import AnalysisFoundationStore
from packages.identity_runtime import (
    IdentityRuntimeClient,
    IdentityRuntimeConfig,
    IdentityRuntimeProfile,
    review_identity_clusters,
)
from packages.persistence_runtime import PersistenceRuntimeClient
from packages.analysis_foundation.narrative_grounding import (
    apply_scene_narrative_grounding,
    narrative_grounding_summary,
    split_narration_and_dialogue,
)


CHAPTER_HEADING_PATTERN = re.compile(
    r"(?im)^\s*(chapter|book|part)\s+([a-z0-9ivxlcdm]+)(?:[\s:.-]+([^\n]+))?\s*$"
)
FIRST_PERSON_PRONOUNS = {"i", "me", "my", "mine", "myself", "we", "our", "ours", "us"}
THIRD_PERSON_PRONOUNS = {"he", "him", "his", "himself", "she", "her", "hers", "herself", "they", "them", "their", "theirs"}
CHARACTER_STOPWORDS = {
    "a",
    "an",
    "and",
    "anyone",
    "anywhere",
    "everything",
    "everyone",
    "faerie",
    "fairfold",
    "here",
    "home",
    "humans",
    "i",
    "it",
    "moments",
    "nothing",
    "people",
    "someone",
    "some",
    "something",
    "there",
    "they",
    "we",
    "you",
}
TITLE_LEADERS = {"king", "queen", "prince", "princess", "lord", "lady", "general", "mother", "high", "mr", "mrs", "ms", "sir"}
CHARACTER_BAD_TOKENS = {"frowned", "wondering", "because", "until", "whatever", "consent", "dance", "remember", "grow", "recall"}


class AnalysisFoundationState(TypedDict, total=False):
    series_id: str
    source_paths: list[str]
    book_index_start: int
    ingested_book_ids: list[str]
    books: list[dict[str, Any]]
    chapters: list[dict[str, Any]]
    scenes: list[dict[str, Any]]
    identity_bundle: dict[str, Any]
    run_metadata: dict[str, Any]
    error: str


class IngestionAgent:
    def __init__(self, *, store: AnalysisFoundationStore) -> None:
        self.store = store

    def run(self, *, series_id: str, source_paths: list[str], book_index_start: int = 1) -> dict[str, Any]:
        books: list[BookArtifact] = []
        chapters: list[ChapterArtifact] = []
        book_ids: list[str] = []
        self.store.persistence.library.upsert_series(series_id, title=series_id, metadata={})
        for offset, raw_path in enumerate(source_paths, start=0):
            path = Path(raw_path)
            raw_bytes = path.read_bytes()
            source_type = path.suffix.lstrip(".").lower() or "txt"
            parsed_source = _parse_source_document(path, source_type=source_type, raw_bytes=raw_bytes)
            text = parsed_source["text"]
            title = parsed_source["title"]
            book_index = int(book_index_start) + offset
            book_id = f"book-{_slug(series_id)}-{_slug(title)}-{book_index:03d}"
            source_artifact = self.store.upsert_source_document(
                series_id=series_id,
                book_id=book_id,
                filename=path.name,
                source_type=source_type,
                title=title,
                raw_bytes=raw_bytes,
                text=text,
                metadata={
                    "original_path": str(path),
                    **dict(parsed_source.get("metadata") or {}),
                },
            )
            extracted = list(parsed_source.get("chapters") or [])
            book = self.store.upsert_book(
                BookArtifact(
                    book_id=book_id,
                    series_id=series_id,
                    title=title,
                    book_index=book_index,
                    source_uri=source_artifact.object_path,
                    source_type=source_type,
                    chapter_count=len(extracted),
                    word_count=len(text.split()),
                    metadata={"source_id": source_artifact.source_id},
                )
            )
            books.append(book)
            book_ids.append(book.book_id)
            for chapter_index, chapter_row in enumerate(extracted, start=1):
                chapter = self.store.upsert_chapter(
                    ChapterArtifact(
                        chapter_id=f"{book_id}-chapter-{chapter_index:03d}",
                        series_id=series_id,
                        book_id=book_id,
                        chapter_index=chapter_index,
                        title=str(chapter_row.get("title") or f"Chapter {chapter_index}"),
                        content=str(chapter_row.get("content") or "").strip(),
                        source_id=source_artifact.source_id,
                        source_type=source_type,
                        word_count=len(str(chapter_row.get("content") or "").split()),
                        metadata={"source_path": str(path)},
                    )
                )
                chapters.append(chapter)
        return {
            "books": [item.model_dump() for item in books],
            "chapters": [item.model_dump() for item in chapters],
            "book_ids": book_ids,
        }


class SceneSegmentationAgent:
    def __init__(self, *, store: AnalysisFoundationStore, target_words: int = 700) -> None:
        self.store = store
        self.target_words = max(100, int(target_words))
        self.target_min_words = max(100, int(self.target_words * 0.75))
        self.target_max_words = max(self.target_min_words + 40, int(self.target_words * 1.2))
        self.min_scene_words = max(90, int(self.target_words * 0.45))

    def run(self, *, book_ids: list[str]) -> dict[str, Any]:
        segmented: list[SceneArtifact] = []
        for book_id in book_ids:
            chapters = self.store.list_chapters(book_id=book_id)
            segmented.extend(self._segment_book(chapters))
        scenes = self.store.upsert_scenes(segmented)
        return {"scenes": [item.model_dump() for item in scenes]}

    def _segment_book(self, chapters: list[ChapterArtifact]) -> list[SceneArtifact]:
        paragraph_records: list[dict[str, Any]] = []
        for chapter in chapters:
            paragraphs = _split_paragraphs(chapter.content)
            for paragraph in paragraphs:
                paragraph_records.append(
                    {
                        "book_id": chapter.book_id,
                        "chapter_index": chapter.chapter_index,
                        "chapter_title": chapter.title,
                        "paragraph": paragraph,
                        "word_count": len(paragraph.split()),
                    }
                )
        if not paragraph_records:
            return []
        scenes: list[dict[str, Any]] = []
        current: list[dict[str, Any]] = []
        current_words = 0
        for record in paragraph_records:
            projected = current_words + int(record["word_count"])
            if current and current_words >= self.target_min_words and projected > self.target_max_words:
                scenes.append(self._records_to_scene(current))
                current = [record]
                current_words = int(record["word_count"])
                continue
            current.append(record)
            current_words = projected
        if current:
            scenes.append(self._records_to_scene(current))
        scenes = self._merge_small_scenes(scenes)
        return self._reindex_scenes(scenes)

    def _records_to_scene(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        text = "\n\n".join(str(item["paragraph"]) for item in rows).strip()
        chapter_indices = [int(item["chapter_index"]) for item in rows]
        return {
            "book_id": str(rows[0]["book_id"]),
            "chapter_index": int(rows[0]["chapter_index"]),
            "scene_index": 1,
            "summary": _summarize_scene(text),
            "text": text,
            "word_count": len(text.split()),
            "source_chapter_indices": sorted(set(chapter_indices)),
            "end_chapter_index": chapter_indices[-1],
            "metadata": {"chapter_title": str(rows[0].get("chapter_title") or "")},
        }

    def _merge_small_scenes(self, scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not scenes:
            return []
        merged: list[dict[str, Any]] = []
        for scene in scenes:
            if not merged:
                merged.append(scene)
                continue
            if int(scene["word_count"]) < self.min_scene_words:
                merged[-1] = self._combine_scenes(merged[-1], scene)
            else:
                merged.append(scene)
        if len(merged) > 1 and int(merged[0]["word_count"]) < self.min_scene_words:
            merged[1] = self._combine_scenes(merged[0], merged[1])
            merged = merged[1:]
        return merged

    def _combine_scenes(self, left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
        combined = f"{left['text']}\n\n{right['text']}".strip()
        return {
            **left,
            "text": combined,
            "summary": _summarize_scene(combined),
            "word_count": len(combined.split()),
            "source_chapter_indices": sorted(set(list(left.get("source_chapter_indices") or []) + list(right.get("source_chapter_indices") or []))),
            "end_chapter_index": int(right.get("end_chapter_index") or right["chapter_index"]),
        }

    def _reindex_scenes(self, scenes: list[dict[str, Any]]) -> list[SceneArtifact]:
        by_anchor: dict[tuple[str, int], int] = {}
        results: list[SceneArtifact] = []
        for raw in scenes:
            key = (str(raw["book_id"]), int(raw["chapter_index"]))
            by_anchor[key] = by_anchor.get(key, 0) + 1
            scene_index = by_anchor[key]
            results.append(
                SceneArtifact(
                    scene_id=f"{raw['book_id']}-chapter-{int(raw['chapter_index']):03d}-scene-{scene_index:03d}",
                    book_id=str(raw["book_id"]),
                    chapter_index=int(raw["chapter_index"]),
                    scene_index=scene_index,
                    summary=str(raw.get("summary") or ""),
                    text=str(raw.get("text") or ""),
                    word_count=int(raw.get("word_count") or 0),
                    source_chapter_indices=[int(value) for value in list(raw.get("source_chapter_indices") or [])],
                    end_chapter_index=int(raw.get("end_chapter_index") or 0),
                    metadata=dict(raw.get("metadata") or {}),
                )
            )
        return results


class IdentityAgent:
    def __init__(self, *, store: AnalysisFoundationStore, identity_runtime: IdentityRuntimeClient | None = None) -> None:
        self.store = store
        self.identity_runtime = identity_runtime or IdentityRuntimeClient(
            profile=IdentityRuntimeProfile(name="analysis-foundation-identity"),
            config=IdentityRuntimeConfig(profile=IdentityRuntimeProfile(name="analysis-foundation-identity")),
        )

    def run(self, *, series_id: str, book_ids: list[str]) -> dict[str, Any]:
        chapter_rows: list[ChapterArtifact] = []
        scene_rows: list[SceneArtifact] = []
        chapters_for_runtime: list[dict[str, Any]] = []
        for book in self.store.list_books(series_id=series_id):
            if book.book_id not in set(book_ids):
                continue
            for chapter in self.store.list_chapters(book_id=book.book_id):
                chapter_rows.append(chapter)
                chapters_for_runtime.append(
                    {
                        "book_index": book.book_index,
                        "chapter_index": chapter.chapter_index,
                        "chapter_title": chapter.title,
                        "content": chapter.content,
                        "source_file": chapter.metadata.get("source_path", ""),
                    }
                )
            scene_rows.extend(self.store.list_scenes(book_id=book.book_id))
        runtime_result = self.identity_runtime.analyze_chapters(chapters=chapters_for_runtime)
        bundle = self._build_bundle(
            series_id=series_id,
            book_ids=book_ids,
            chapters=chapter_rows,
            scenes=scene_rows,
            runtime_payload=runtime_result.model_dump(),
        )
        saved = self.store.save_identity_bundle(bundle)
        return {"identity_bundle": saved.model_dump()}

    def _build_bundle(
        self,
        *,
        series_id: str,
        book_ids: list[str],
        chapters: list[ChapterArtifact],
        scenes: list[SceneArtifact],
        runtime_payload: dict[str, Any],
    ) -> CanonicalIdentityBundle:
        review_result = review_identity_clusters(
            raw_clusters=list(runtime_payload.get("clusters") or []),
            chapters=[chapter.model_dump() for chapter in chapters],
            scenes=[scene.model_dump() for scene in scenes],
        )
        characters: list[CanonicalCharacter] = []
        for reviewed in review_result.reviewed_clusters:
            if not reviewed.keep_cluster:
                continue
            raw = reviewed.cluster.model_dump()
            display_name = str(reviewed.cluster.display_name or "").strip() or _select_character_display_name(raw)
            if not display_name:
                continue
            character_id = f"char-{_slug(display_name)}"
            aliases = [display_name, *list(reviewed.accepted_aliases or [])]
            chapter_indices = _character_chapter_indices(aliases, chapters)
            scene_ids = _character_scene_ids(aliases, scenes)
            characters.append(
                CanonicalCharacter(
                    character_id=character_id,
                    display_name=display_name,
                    aliases=[alias for alias in aliases if alias != display_name],
                    mention_count=int(raw.get("mention_count") or 0),
                    proper_mentions=[item for item in _unique_strings(list(raw.get("proper_mentions") or [])) if _is_character_name_candidate(item)],
                    pronoun_mentions=_unique_strings(list(raw.get("pronoun_mentions") or [])),
                    chapter_indices=chapter_indices,
                    scene_ids=scene_ids,
                )
            )
        merged_characters = _merge_characters_by_identity(characters)
        merged_alias_map: dict[str, str] = {}
        for character in merged_characters:
            merged_alias_map[character.display_name] = character.character_id
            for alias in character.aliases:
                merged_alias_map[alias] = character.character_id
        narrator = _build_narrator_reference(chapters, merged_characters)
        return CanonicalIdentityBundle(
            series_id=series_id,
            provider_name=str(runtime_payload.get("provider_name") or self.identity_runtime.provider_name()),
            book_ids=list(book_ids),
            characters=merged_characters,
            alias_map=merged_alias_map,
            narrator=narrator,
            source_stats={
                "chapter_count": len(chapters),
                "scene_count": len(scenes),
                **dict(runtime_payload.get("input_stats") or {}),
                "runtime_seconds": float(runtime_payload.get("runtime_seconds") or 0.0),
                "chunk_count": int(runtime_payload.get("chunk_count") or 0),
                "identity_kept_cluster_count": int(review_result.kept_cluster_count),
                "identity_dropped_cluster_count": int(review_result.dropped_cluster_count),
                "identity_accepted_alias_count": int(review_result.accepted_alias_count),
                "identity_rejected_alias_count": int(review_result.rejected_alias_count),
            },
            metadata={
                "app_name": str(runtime_payload.get("app_name") or ""),
                "model_name": str(runtime_payload.get("model_name") or ""),
                "identity_review": review_result.model_dump(),
            },
        )


class NarrativeGroundingAgent:
    def __init__(self, *, store: AnalysisFoundationStore) -> None:
        self.store = store

    def run(
        self,
        *,
        book_ids: list[str],
        scenes: list[SceneArtifact],
        identity_bundle: CanonicalIdentityBundle,
    ) -> dict[str, Any]:
        chapters: list[ChapterArtifact] = []
        for book_id in book_ids:
            chapters.extend(self.store.list_chapters(book_id=book_id))
        grounded_scenes = apply_scene_narrative_grounding(
            scenes=scenes,
            identity_bundle=identity_bundle,
            chapter_texts=[chapter.content for chapter in chapters],
        )
        persisted = self.store.upsert_scenes(grounded_scenes)
        return {
            "scenes": [scene.model_dump() for scene in persisted],
            "summary": narrative_grounding_summary(persisted),
        }


def build_analysis_foundation_graph(
    *,
    ingestion_agent: IngestionAgent,
    scene_agent: SceneSegmentationAgent,
    identity_agent: IdentityAgent,
    narrative_grounding_agent: NarrativeGroundingAgent,
    checkpointer: BaseCheckpointSaver | None = None,
) -> Any:
    def ingestion_node(state: AnalysisFoundationState) -> dict[str, Any]:
        started_at = time.perf_counter()
        payload = ingestion_agent.run(
            series_id=str(state.get("series_id") or ""),
            source_paths=list(state.get("source_paths") or []),
            book_index_start=int(state.get("book_index_start") or 1),
        )
        metadata = _append_stage_metadata(
            state.get("run_metadata"),
            stage_name="ingestion",
            elapsed_seconds=time.perf_counter() - started_at,
            extra={
                "book_count": len(payload["books"]),
                "chapter_count": len(payload["chapters"]),
            },
        )
        return {
            "ingested_book_ids": list(payload["book_ids"]),
            "books": list(payload["books"]),
            "chapters": list(payload["chapters"]),
            "run_metadata": metadata,
        }

    def scene_node(state: AnalysisFoundationState) -> dict[str, Any]:
        started_at = time.perf_counter()
        payload = scene_agent.run(book_ids=list(state.get("ingested_book_ids") or []))
        metadata = _append_stage_metadata(
            state.get("run_metadata"),
            stage_name="scene_segmentation",
            elapsed_seconds=time.perf_counter() - started_at,
            extra={"scene_count": len(payload["scenes"])},
        )
        return {"scenes": list(payload["scenes"]), "run_metadata": metadata}

    def identity_node(state: AnalysisFoundationState) -> dict[str, Any]:
        started_at = time.perf_counter()
        payload = identity_agent.run(
            series_id=str(state.get("series_id") or ""),
            book_ids=list(state.get("ingested_book_ids") or []),
        )
        metadata = _append_stage_metadata(
            state.get("run_metadata"),
            stage_name="identity",
            elapsed_seconds=time.perf_counter() - started_at,
            extra={
                "character_count": len((payload.get("identity_bundle") or {}).get("characters") or []),
                "identity_provider": str((payload.get("identity_bundle") or {}).get("provider_name") or ""),
            },
        )
        return {"identity_bundle": dict(payload["identity_bundle"]), "run_metadata": metadata}

    def narrative_grounding_node(state: AnalysisFoundationState) -> dict[str, Any]:
        started_at = time.perf_counter()
        payload = narrative_grounding_agent.run(
            book_ids=list(state.get("ingested_book_ids") or []),
            scenes=[SceneArtifact.model_validate(item) for item in list(state.get("scenes") or [])],
            identity_bundle=CanonicalIdentityBundle.model_validate(state.get("identity_bundle") or {}),
        )
        summary = dict(payload.get("summary") or {})
        metadata = _append_stage_metadata(
            state.get("run_metadata"),
            stage_name="narrative_grounding",
            elapsed_seconds=time.perf_counter() - started_at,
            extra=summary,
        )
        return {"scenes": list(payload["scenes"]), "run_metadata": metadata}

    builder = StateGraph(AnalysisFoundationState)
    builder.add_node("ingestion", ingestion_node)
    builder.add_node("scene_segmentation", scene_node)
    builder.add_node("identity", identity_node)
    builder.add_node("narrative_grounding", narrative_grounding_node)
    builder.add_edge(START, "ingestion")
    builder.add_edge("ingestion", "scene_segmentation")
    builder.add_edge("scene_segmentation", "identity")
    builder.add_edge("identity", "narrative_grounding")
    builder.add_edge("narrative_grounding", END)
    return builder.compile(checkpointer=checkpointer)


class AnalysisFoundationRuntime:
    def __init__(
        self,
        *,
        persistence: PersistenceRuntimeClient,
        identity_runtime: IdentityRuntimeClient | None = None,
        checkpointer: BaseCheckpointSaver | None = None,
        allow_in_memory_checkpointer: bool = False,
    ) -> None:
        self.persistence = persistence
        self.persistence.initialize()
        self.store = AnalysisFoundationStore(persistence)
        self.ingestion_agent = IngestionAgent(store=self.store)
        self.scene_agent = SceneSegmentationAgent(store=self.store)
        self.identity_agent = IdentityAgent(store=self.store, identity_runtime=identity_runtime)
        self.narrative_grounding_agent = NarrativeGroundingAgent(store=self.store)
        self.checkpointer = _resolve_checkpointer(
            persistence=persistence,
            checkpointer=checkpointer,
            allow_in_memory_checkpointer=allow_in_memory_checkpointer,
        )
        self.graph = build_analysis_foundation_graph(
            ingestion_agent=self.ingestion_agent,
            scene_agent=self.scene_agent,
            identity_agent=self.identity_agent,
            narrative_grounding_agent=self.narrative_grounding_agent,
            checkpointer=self.checkpointer,
        )

    def invoke(
        self,
        *,
        series_id: str,
        source_paths: list[str],
        book_index_start: int = 1,
        thread_id: str = "analysis-foundation",
    ) -> AnalysisFoundationResult:
        state = self.graph.invoke(
            {
                "series_id": str(series_id or "").strip(),
                "source_paths": [str(item) for item in list(source_paths or [])],
                "book_index_start": int(book_index_start or 1),
            },
            config={"configurable": {"thread_id": str(thread_id or "analysis-foundation")}},
        )
        return AnalysisFoundationResult(
            series_id=str(state.get("series_id") or series_id),
            books=[BookArtifact.model_validate(item) for item in list(state.get("books") or [])],
            chapters=[ChapterArtifact.model_validate(item) for item in list(state.get("chapters") or [])],
            scenes=[SceneArtifact.model_validate(item) for item in list(state.get("scenes") or [])],
            identity_bundle=CanonicalIdentityBundle.model_validate(state["identity_bundle"]) if state.get("identity_bundle") else None,
            run_metadata=dict(state.get("run_metadata") or {}),
        )


def _resolve_checkpointer(
    *,
    persistence: PersistenceRuntimeClient,
    checkpointer: BaseCheckpointSaver | None,
    allow_in_memory_checkpointer: bool,
) -> BaseCheckpointSaver:
    if checkpointer is not None:
        return checkpointer
    if getattr(persistence, "engine", None) is not None:
        return SqlCheckpointSaver(engine=persistence.engine)
    if allow_in_memory_checkpointer:
        return InMemorySaver()
    raise ValueError("AnalysisFoundationRuntime requires a durable checkpointer or an initialized persistence engine.")


def _extract_text(path: Path, *, source_type: str, raw_bytes: bytes) -> str:
    return str(_parse_source_document(path, source_type=source_type, raw_bytes=raw_bytes)["text"])


def _parse_source_document(path: Path, *, source_type: str, raw_bytes: bytes) -> dict[str, Any]:
    normalized = str(source_type or "").strip().lower()
    if normalized in {"txt", "md"}:
        text = raw_bytes.decode("utf-8", errors="ignore").strip()
        return {
            "title": _derive_title(path, text),
            "text": text,
            "chapters": _extract_chapters(text),
            "metadata": {},
        }
    if normalized == "pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        text = "\n\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()
        return {
            "title": _derive_title(path, text),
            "text": text,
            "chapters": _extract_chapters(text),
            "metadata": {"page_count": len(reader.pages)},
        }
    if normalized == "epub":
        from bs4 import BeautifulSoup
        from ebooklib import epub, ITEM_DOCUMENT

        book = epub.read_epub(str(path))
        metadata_title = _extract_epub_metadata_title(book)
        toc_titles = _flatten_epub_toc_titles(book)
        chapters: list[dict[str, str]] = []
        included_item_ids: list[str] = []
        content_started = False
        for item_id, _linear in list(book.spine or []):
            item = book.get_item_with_id(str(item_id))
            if item is None or item.get_type() != ITEM_DOCUMENT:
                continue
            file_name = str(getattr(item, "file_name", "") or "")
            toc_title = toc_titles.get(Path(file_name).name.casefold(), "") or toc_titles.get(Path(file_name).stem.casefold(), "")
            soup = BeautifulSoup(item.get_body_content(), "html.parser")
            text = soup.get_text("\n", strip=True)
            if content_started and _is_epub_terminal_document(
                item_id=str(item_id),
                file_name=file_name,
                text=text,
                toc_title=toc_title,
            ):
                break
            if not _should_include_epub_document(
                item_id=str(item_id),
                file_name=file_name,
                text=text,
                toc_title=toc_title,
                content_started=content_started,
            ):
                continue
            chapter_title = _epub_document_title(
                item_id=str(item_id),
                file_name=file_name,
                text=text,
                ordinal=len(chapters) + 1,
                toc_title=toc_title,
            )
            chapters.append({"title": chapter_title, "content": text})
            included_item_ids.append(str(item_id))
            content_started = True
        if not chapters:
            parts: list[str] = []
            for item in book.get_items_of_type(ITEM_DOCUMENT):
                soup = BeautifulSoup(item.get_body_content(), "html.parser")
                text = soup.get_text("\n", strip=True)
                if text:
                    parts.append(text)
            fallback_text = "\n\n".join(parts).strip()
            return {
                "title": metadata_title or _derive_title(path, fallback_text),
                "text": fallback_text,
                "chapters": _extract_chapters(fallback_text),
                "metadata": {"spine_len": len(list(book.spine or [])), "epub_item_ids": included_item_ids},
            }
        full_text = "\n\n".join(str(item["content"]).strip() for item in chapters if str(item.get("content") or "").strip()).strip()
        return {
            "title": metadata_title or _derive_title(path, full_text),
            "text": full_text,
            "chapters": chapters,
            "metadata": {"spine_len": len(list(book.spine or [])), "epub_item_ids": included_item_ids},
        }
    raise ValueError(f"Unsupported source type '{source_type}'.")


def _derive_title(path: Path, text: str) -> str:
    for line in [segment.strip() for segment in text.splitlines()[:10]]:
        if line and len(line.split()) <= 12 and not CHAPTER_HEADING_PATTERN.match(line):
            return line
    return path.stem.replace("_", " ").replace("-", " ").strip() or path.stem


def _extract_chapters(text: str) -> list[dict[str, str]]:
    normalized = re.sub(r"\r\n|\r", "\n", str(text or "")).strip()
    if not normalized:
        return []
    matches = list(CHAPTER_HEADING_PATTERN.finditer(normalized))
    if not matches:
        return [{"title": "Chapter 1", "content": normalized}]
    chapters: list[dict[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(normalized)
        title_suffix = str(match.group(3) or "").strip()
        label = f"{match.group(1).title()} {match.group(2).strip()}"
        title = f"{label}: {title_suffix}".strip(": ").strip()
        content = normalized[start:end].strip()
        if content:
            chapters.append({"title": title, "content": content})
    return chapters or [{"title": "Chapter 1", "content": normalized}]


def _append_stage_metadata(
    current: dict[str, Any] | None,
    *,
    stage_name: str,
    elapsed_seconds: float,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = dict(current or {})
    stage_order = list(metadata.get("stage_order") or [])
    stage_timings = dict(metadata.get("stage_timings_seconds") or {})
    stage_details = dict(metadata.get("stage_details") or {})
    if stage_name not in stage_order:
        stage_order.append(stage_name)
    stage_timings[stage_name] = round(max(0.0, float(elapsed_seconds)), 4)
    stage_details[stage_name] = dict(extra or {})
    metadata["stage_order"] = stage_order
    metadata["stage_timings_seconds"] = stage_timings
    metadata["stage_details"] = stage_details
    metadata["total_runtime_seconds"] = round(sum(float(stage_timings.get(name) or 0.0) for name in stage_order), 4)
    return metadata


def _extract_epub_metadata_title(book: Any) -> str:
    try:
        values = list(book.get_metadata("DC", "title") or [])
    except Exception:
        values = []
    for value, _attrs in values:
        normalized = str(value or "").strip()
        if normalized:
            return normalized
    return ""


def _should_include_epub_document(*, item_id: str, file_name: str, text: str, toc_title: str = "", content_started: bool = False) -> bool:
    normalized_id = str(item_id or "").strip().casefold()
    normalized_name = Path(str(file_name or "").strip()).stem.casefold()
    normalized_text = re.sub(r"\s+", " ", str(text or "").strip())
    normalized_toc = str(toc_title or "").strip().casefold()
    word_count = len(normalized_text.split())
    if not normalized_text:
        return False
    content_markers = ("chapter", "prologue", "epilogue", "appendix", "interlude", "part", "begin reading")
    non_content_markers = (
        "cover",
        "titlepage",
        "copyright",
        "toc",
        "nav",
        "dedication",
        "contents",
        "acknowledg",
        "aboutauthor",
        "newsletter",
        "advert",
        "lbyr",
    )
    toc_non_content_markers = ("cover", "begin reading", "half title", "title page", "copyright", "dedication", "acknowledg", "contents")
    if normalized_toc and any(marker in normalized_toc for marker in toc_non_content_markers if marker != "begin reading"):
        return False
    if normalized_toc:
        if "begin reading" in normalized_toc:
            return word_count >= 80
        if any(marker in normalized_toc for marker in content_markers):
            return True
        if word_count >= 80:
            return True
        return False
    if not content_started:
        if re.fullmatch(r"part\d+", normalized_name) or re.fullmatch(r"x_f\d+", normalized_id):
            return False
        return any(marker in normalized_id or marker in normalized_name for marker in content_markers)
    if any(marker in normalized_id or marker in normalized_name for marker in content_markers):
        if "appendix" in normalized_id or "appendix" in normalized_name:
            lowered_text = normalized_text.casefold()
            if "sneak peek" in lowered_text or "continue reading" in lowered_text or word_count < 150:
                return False
        return True
    if any(marker in normalized_id or marker in normalized_name for marker in non_content_markers):
        return False
    if word_count < 80:
        return False
    return True


def _is_epub_terminal_document(*, item_id: str, file_name: str, text: str, toc_title: str = "") -> bool:
    normalized_id = str(item_id or "").strip().casefold()
    normalized_name = Path(str(file_name or "").strip()).stem.casefold()
    normalized_toc = str(toc_title or "").strip().casefold()
    normalized_text = re.sub(r"\s+", " ", str(text or "").strip()).casefold()
    if "appendix" in normalized_id or "appendix" in normalized_name:
        return True
    if "sneak peek" in normalized_toc or "excerpt" in normalized_toc:
        return True
    if "continue reading" in normalized_text and "sneak peek" in normalized_text:
        return True
    return False


def _epub_document_title(*, item_id: str, file_name: str, text: str, ordinal: int, toc_title: str = "") -> str:
    if str(toc_title or "").strip():
        return str(toc_title or "").strip()
    candidate = _find_heading_candidate(text)
    if candidate:
        return candidate
    normalized_id = str(item_id or "").strip()
    normalized_name = Path(str(file_name or "").strip()).stem
    for value in (normalized_id, normalized_name):
        lowered = value.casefold()
        if "prologue" in lowered:
            return "Prologue"
        if "epilogue" in lowered:
            return "Epilogue"
        if "appendix" in lowered:
            return "Appendix"
        match = re.search(r"chapter\D*(\d{1,3})", lowered)
        if match:
            return f"Chapter {int(match.group(1))}"
        if "part" in lowered:
            number_match = re.search(r"part\D*(\d{1,3})", lowered)
            if number_match:
                return f"Part {int(number_match.group(1))}"
            return "Part"
    return f"Section {int(ordinal)}"


def _flatten_epub_toc_titles(book: Any) -> dict[str, str]:
    results: dict[str, str] = {}

    def visit(entry: Any) -> None:
        href = str(getattr(entry, "href", "") or "").strip()
        title = str(getattr(entry, "title", "") or "").strip()
        if href and title:
            normalized_href = href.split("#", 1)[0].strip()
            if normalized_href:
                path = Path(normalized_href)
                results[path.name.casefold()] = title
                results[path.stem.casefold()] = title
        for child in list(getattr(entry, "subitems", None) or []):
            visit(child)

    for entry in list(getattr(book, "toc", None) or []):
        visit(entry)
    return results


def _find_heading_candidate(text: str) -> str:
    for line in [segment.strip() for segment in str(text or "").splitlines()[:8]]:
        cleaned = re.sub(r"\s+", " ", line).strip()
        if not cleaned:
            continue
        if len(cleaned) <= 1:
            continue
        if len(cleaned.split()) > 12:
            continue
        if re.fullmatch(r"[ivxlcdm]+", cleaned.casefold()):
            return cleaned.upper()
        if CHAPTER_HEADING_PATTERN.match(cleaned):
            return cleaned
        if cleaned.istitle() and len(cleaned) <= 80:
            return cleaned
    return ""


def _character_aliases(raw: dict[str, Any], *, display_name: str) -> list[str]:
    candidates = [display_name, *list(raw.get("proper_mentions") or []), *list(raw.get("aliases") or [])]
    return [item for item in _unique_strings(candidates) if _is_character_name_candidate(item)]


def _select_character_display_name(raw: dict[str, Any]) -> str:
    candidates = _unique_strings(
        [
            *list(raw.get("proper_mentions") or []),
            *list(raw.get("aliases") or []),
            str(raw.get("display_name") or "").strip(),
        ]
    )
    scored = sorted(
        (
            (_character_name_score(candidate), _normalize_character_name(candidate))
            for candidate in candidates
            if _is_character_name_candidate(candidate)
        ),
        key=lambda item: item[0],
    )
    return scored[0][1] if scored else ""


def _normalize_character_name(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "").replace("\n", " ").replace("\r", " ").strip())
    cleaned = cleaned.strip(" ,.;:!?\"'()[]{}")
    cleaned = re.sub(r"\s+([,.!?;:])", r"\1", cleaned)
    return cleaned


def _is_character_name_candidate(value: str) -> bool:
    cleaned = _normalize_character_name(value)
    if not cleaned:
        return False
    if len(cleaned) < 2 or len(cleaned) > 48:
        return False
    if "\n" in str(value or "") or "�" in cleaned:
        return False
    if re.search(r"[^A-Za-z0-9 .'\-]", cleaned):
        return False
    words = cleaned.split()
    if len(words) > 5:
        return False
    lowered_words = [word.casefold().strip(".") for word in words]
    if any(word in CHARACTER_BAD_TOKENS for word in lowered_words):
        return False
    if len(words) == 1 and lowered_words[0] in CHARACTER_STOPWORDS:
        return False
    if lowered_words[0] in {"i", "you", "we", "they"}:
        return False
    if cleaned.casefold() == cleaned and len(words) == 1:
        return False
    if lowered_words[0] in {"a", "an", "this", "that", "these", "those"} and len(words) > 3:
        return False
    if lowered_words[0] in {"my", "your", "his", "her", "their", "our"} and len(words) > 2:
        return False
    if lowered_words[0] == "the" and len(words) > 4 and not any(word.casefold().strip(".") in TITLE_LEADERS for word in words[1:3]):
        return False
    has_title_case = any(word[:1].isupper() for word in words if word)
    if not has_title_case and lowered_words[0] not in {"the", "my", "your", "his", "her", "their", "our"}:
        return False
    return True


def _character_name_score(value: str) -> tuple[int, int, int, str]:
    cleaned = _normalize_character_name(value)
    words = cleaned.split()
    lowered_words = [word.casefold().strip(".") for word in words]
    penalties = 0
    if lowered_words[0] in {"the", "my", "your", "his", "her", "their", "our"}:
        penalties += 3
    if any(word.casefold().strip(".") in TITLE_LEADERS for word in words):
        penalties -= 1
    if any(word.casefold() in {"named", "called"} for word in words):
        penalties += 2
    return (penalties, len(words), len(cleaned), cleaned.casefold())


def _merge_characters_by_identity(characters: list[CanonicalCharacter]) -> list[CanonicalCharacter]:
    merged: dict[str, CanonicalCharacter] = {}
    for character in characters:
        existing = merged.get(character.character_id)
        if existing is None:
            merged[character.character_id] = character
            continue
        merged[character.character_id] = CanonicalCharacter(
            character_id=existing.character_id,
            display_name=existing.display_name,
            aliases=_unique_strings([*existing.aliases, *character.aliases]),
            mention_count=max(existing.mention_count, character.mention_count),
            proper_mentions=_unique_strings([*existing.proper_mentions, *character.proper_mentions]),
            pronoun_mentions=_unique_strings([*existing.pronoun_mentions, *character.pronoun_mentions]),
            chapter_indices=sorted(set([*existing.chapter_indices, *character.chapter_indices])),
            scene_ids=_unique_strings([*existing.scene_ids, *character.scene_ids]),
        )
    return sorted(merged.values(), key=lambda item: (-item.mention_count, item.display_name.casefold()))


def _split_paragraphs(text: str) -> list[str]:
    normalized = str(text or "").strip()
    parts = [segment.strip() for segment in re.split(r"\n\s*\n+", normalized) if segment.strip()]
    single_line_mode = False
    if len(parts) <= 1 and normalized.count("\n") >= 4:
        parts = [segment.strip() for segment in normalized.splitlines() if segment.strip()]
        single_line_mode = True
    merged: list[str] = []
    for paragraph in parts:
        cleaned = re.sub(r"[ \t]+", " ", paragraph).strip()
        if merged and not single_line_mode and len(cleaned.split()) < 12:
            merged[-1] = f"{merged[-1]} {cleaned}".strip()
        else:
            merged.append(cleaned)
    return merged or ([re.sub(r"\s+", " ", normalized).strip()] if normalized else [])


def _summarize_scene(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "").strip())
    if not cleaned:
        return ""
    words = cleaned.split()
    return " ".join(words[: min(18, len(words))])


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return cleaned or hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()[:8]


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        results.append(normalized)
    return results


def _character_chapter_indices(aliases: list[str], chapters: list[ChapterArtifact]) -> list[int]:
    results: list[int] = []
    for chapter in chapters:
        haystack = chapter.content.casefold()
        if any(alias.casefold() in haystack for alias in aliases):
            results.append(chapter.chapter_index)
    return sorted(set(results))


def _character_scene_ids(aliases: list[str], scenes: list[SceneArtifact]) -> list[str]:
    results: list[str] = []
    for scene in scenes:
        haystack = scene.text.casefold()
        if any(alias.casefold() in haystack for alias in aliases):
            results.append(scene.scene_id)
    return results


def _build_narrator_reference(chapters: list[ChapterArtifact], characters: list[CanonicalCharacter]) -> NarratorReferenceData:
    narration = "\n".join(split_narration_and_dialogue(chapter.content)[0] for chapter in chapters)
    tokens = re.findall(r"[a-zA-Z']+", narration.casefold())
    first_count = sum(1 for token in tokens if token in FIRST_PERSON_PRONOUNS)
    third_count = sum(1 for token in tokens if token in THIRD_PERSON_PRONOUNS)
    perspective = "first_person" if first_count > third_count else "third_person"
    named_candidates = [character.display_name for character in sorted(characters, key=lambda item: item.mention_count, reverse=True)[:3]]
    return NarratorReferenceData(
        perspective=perspective,
        first_person_pronoun_count=first_count,
        third_person_pronoun_count=third_count,
        named_reference_candidates=named_candidates,
    )
