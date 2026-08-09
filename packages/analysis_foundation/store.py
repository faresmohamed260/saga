"""Persistence mapping for analysis-foundation artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from packages.analysis_foundation.contracts import (
    BookArtifact,
    CanonicalIdentityBundle,
    ChapterArtifact,
    SceneArtifact,
    SourceDocumentArtifact,
)
from packages.persistence_runtime import PersistenceRuntimeClient


class AnalysisFoundationStore:
    def __init__(self, persistence: PersistenceRuntimeClient) -> None:
        self.persistence = persistence

    def upsert_source_document(
        self,
        *,
        series_id: str,
        book_id: str,
        filename: str,
        source_type: str,
        title: str,
        raw_bytes: bytes,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> SourceDocumentArtifact:
        digest = hashlib.sha256(raw_bytes).hexdigest()[:24]
        source_id = f"source-{digest}"
        payload = {
            "source_id": source_id,
            "filename": Path(filename).name,
            "source_type": source_type,
            "title": title,
            "text_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "text_length": len(text),
            "word_count": len(text.split()),
            **dict(metadata or {}),
        }
        stored = self.persistence.artifacts.store_bytes(
            artifact_type="source_document",
            data=raw_bytes,
            filename=Path(filename).name,
            content_type=_content_type_for_source_type(source_type),
            series_id=series_id,
            book_id=book_id,
            metadata=payload,
            record_type="source_document",
        )
        self.persistence.library.upsert_record(
            source_id,
            record_type="source_document",
            series_id=series_id,
            book_id=book_id,
            title=title,
            payload={
                **payload,
                "bucket_name": stored["bucket_name"],
                "object_path": stored["object_path"],
            },
        )
        return SourceDocumentArtifact(
            source_id=source_id,
            series_id=series_id,
            book_id=book_id,
            filename=Path(filename).name,
            source_type=source_type,
            title=title,
            object_path=stored["object_path"],
            bucket_name=stored["bucket_name"],
            text_hash=payload["text_hash"],
            text_length=payload["text_length"],
            word_count=payload["word_count"],
            metadata=dict(metadata or {}),
        )

    def upsert_book(self, book: BookArtifact) -> BookArtifact:
        payload = self.persistence.library.upsert_book(
            book.book_id,
            series_id=book.series_id,
            title=book.title,
            book_index=book.book_index,
            source_uri=book.source_uri,
            source_type=book.source_type,
            metadata={
                **dict(book.metadata or {}),
                "chapter_count": int(book.chapter_count),
                "word_count": int(book.word_count),
            },
        )
        return BookArtifact(
            book_id=payload["book_id"],
            series_id=payload["series_id"],
            title=payload["title"],
            book_index=int(payload["book_index"] or 0),
            source_uri=payload["source_uri"],
            source_type=payload["source_type"],
            chapter_count=int((payload.get("metadata") or {}).get("chapter_count") or 0),
            word_count=int((payload.get("metadata") or {}).get("word_count") or 0),
            metadata=dict(payload.get("metadata") or {}),
        )

    def list_books(self, *, series_id: str) -> list[BookArtifact]:
        return [
            BookArtifact(
                book_id=row["book_id"],
                series_id=row["series_id"],
                title=row["title"],
                book_index=int(row.get("book_index") or 0),
                source_uri=row.get("source_uri") or "",
                source_type=row.get("source_type") or "",
                chapter_count=int((row.get("metadata") or {}).get("chapter_count") or 0),
                word_count=int((row.get("metadata") or {}).get("word_count") or 0),
                metadata=dict(row.get("metadata") or {}),
            )
            for row in self.persistence.library.list_books(series_id=series_id, limit=1000)
        ]

    def upsert_chapter(self, chapter: ChapterArtifact) -> ChapterArtifact:
        payload = self.persistence.library.upsert_record(
            chapter.chapter_id,
            record_type="chapter",
            series_id=chapter.series_id,
            book_id=chapter.book_id,
            title=chapter.title,
            ordinal=chapter.chapter_index,
            payload={
                "chapter_id": chapter.chapter_id,
                "chapter_index": chapter.chapter_index,
                "title": chapter.title,
                "content": chapter.content,
                "source_id": chapter.source_id,
                "source_type": chapter.source_type,
                "word_count": chapter.word_count,
                **dict(chapter.metadata or {}),
            },
        )
        chapter_payload = dict(payload.get("payload") or {})
        return ChapterArtifact(
            chapter_id=payload["record_id"],
            series_id=payload["series_id"],
            book_id=payload["book_id"],
            chapter_index=int(payload.get("ordinal") or chapter_payload.get("chapter_index") or 0),
            title=payload.get("title") or "",
            content=chapter_payload.get("content") or "",
            source_id=chapter_payload.get("source_id") or "",
            source_type=chapter_payload.get("source_type") or "",
            word_count=int(chapter_payload.get("word_count") or 0),
            metadata={k: v for k, v in chapter_payload.items() if k not in {"chapter_id", "chapter_index", "title", "content", "source_id", "source_type", "word_count"}},
        )

    def list_chapters(self, *, book_id: str) -> list[ChapterArtifact]:
        rows = self.persistence.library.list_records(record_type="chapter", book_id=book_id, limit=5000)
        results = []
        for row in rows:
            payload = dict(row.get("payload") or {})
            results.append(
                ChapterArtifact(
                    chapter_id=row["record_id"],
                    series_id=row["series_id"],
                    book_id=row["book_id"],
                    chapter_index=int(row.get("ordinal") or payload.get("chapter_index") or 0),
                    title=row.get("title") or "",
                    content=payload.get("content") or "",
                    source_id=payload.get("source_id") or "",
                    source_type=payload.get("source_type") or "",
                    word_count=int(payload.get("word_count") or 0),
                    metadata={k: v for k, v in payload.items() if k not in {"chapter_id", "chapter_index", "title", "content", "source_id", "source_type", "word_count"}},
                )
            )
        results.sort(key=lambda item: item.chapter_index)
        return results

    def upsert_scene(self, scene: SceneArtifact) -> SceneArtifact:
        payload = self.persistence.library.upsert_scene(
            scene.scene_id,
            book_id=scene.book_id,
            chapter_index=scene.chapter_index,
            scene_index=scene.scene_index,
            summary=scene.summary,
            text=scene.text,
            payload={
                "word_count": scene.word_count,
                "source_chapter_indices": list(scene.source_chapter_indices),
                "end_chapter_index": scene.end_chapter_index,
                **dict(scene.metadata or {}),
            },
        )
        scene_payload = dict(payload.get("payload") or {})
        return SceneArtifact(
            scene_id=payload["scene_id"],
            book_id=payload["book_id"],
            chapter_index=int(payload["chapter_index"]),
            scene_index=int(payload["scene_index"]),
            summary=payload.get("summary") or "",
            text=payload.get("text") or "",
            word_count=int(scene_payload.get("word_count") or 0),
            source_chapter_indices=[int(value) for value in list(scene_payload.get("source_chapter_indices") or [])],
            end_chapter_index=int(scene_payload.get("end_chapter_index") or 0),
            metadata={k: v for k, v in scene_payload.items() if k not in {"word_count", "source_chapter_indices", "end_chapter_index"}},
        )

    def list_scenes(self, *, book_id: str) -> list[SceneArtifact]:
        rows = self.persistence.library.list_scenes(book_id=book_id, limit=10000)
        results = []
        for row in rows:
            payload = dict(row.get("payload") or {})
            results.append(
                SceneArtifact(
                    scene_id=row["scene_id"],
                    book_id=row["book_id"],
                    chapter_index=int(row["chapter_index"]),
                    scene_index=int(row["scene_index"]),
                    summary=row.get("summary") or "",
                    text=row.get("text") or "",
                    word_count=int(payload.get("word_count") or 0),
                    source_chapter_indices=[int(value) for value in list(payload.get("source_chapter_indices") or [])],
                    end_chapter_index=int(payload.get("end_chapter_index") or 0),
                    metadata={k: v for k, v in payload.items() if k not in {"word_count", "source_chapter_indices", "end_chapter_index"}},
                )
            )
        return results

    def save_identity_bundle(self, bundle: CanonicalIdentityBundle) -> CanonicalIdentityBundle:
        payload = bundle.model_dump()
        self.persistence.identity.upsert_identity_series(
            bundle.series_id,
            provider_name=bundle.provider_name,
            payload=payload,
        )
        self.persistence.artifacts.store_json(
            artifact_type="identity_export",
            payload=payload,
            filename=f"{bundle.series_id}-identity-bundle.json",
            series_id=bundle.series_id,
            metadata={"provider_name": bundle.provider_name, "book_ids": list(bundle.book_ids)},
            record_type="identity_bundle",
        )
        return bundle

    def load_identity_bundle(self, *, series_id: str) -> CanonicalIdentityBundle | None:
        row = self.persistence.identity.get_identity_series(series_id)
        if not row:
            return None
        return CanonicalIdentityBundle.model_validate(dict(row.get("payload") or {}))


def _content_type_for_source_type(source_type: str) -> str:
    normalized = str(source_type or "").strip().lower()
    if normalized == "txt":
        return "text/plain; charset=utf-8"
    if normalized == "pdf":
        return "application/pdf"
    if normalized == "epub":
        return "application/epub+zip"
    return "application/octet-stream"
