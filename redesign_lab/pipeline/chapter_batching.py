"""Chapter-first redesign batching stage."""

from __future__ import annotations

from typing import Any, Dict, List

from analysis.scene_extractor import SceneExtractor
from redesign_lab.pipeline.contracts import validate_contract


class ChapterBatcher:
    """Batch ACOTAR chapters for redesign-local processing."""

    def __init__(self, *, target_scene_words: int = 0) -> None:
        self.target_scene_words = int(target_scene_words)

    def build_batches(
        self,
        chapters: List[Dict[str, Any]],
        *,
        series_id: str,
        series_title: str,
    ) -> List[Dict[str, Any]]:
        extractor = SceneExtractor.from_target_words(self.target_scene_words)
        scenes = extractor.extract_many(
            chapters,
            allow_cross_chapter=True,
        )
        if self.target_scene_words > 0:
            scenes = self._apply_overflow_fallback(extractor, scenes)
        batches: List[Dict[str, Any]] = []
        for index, scene in enumerate(scenes, start=1):
            batch = {
                "batch_id": f"{series_id}-batch-{index:04d}",
                "series_id": series_id,
                "series_title": series_title,
                "book_index": int(scene.get("book_index") or 1),
                "chapter_indices": list(scene.get("source_chapter_indices") or [scene.get("chapter_index")]),
                "chapter_titles": [scene.get("chapter_title", "")],
                "source_files": list(scene.get("source_files") or []),
                "text": scene.get("text", ""),
                "word_count": int(scene.get("length") or 0),
                "stage": "chapter_batching",
                "scene_index": int(scene.get("scene_index") or 1),
                "start_chapter_index": int(scene.get("chapter_index") or 1),
                "end_chapter_index": int(scene.get("end_chapter_index") or scene.get("chapter_index") or 1),
            }
            batches.append(validate_contract("chapter_batch", batch))
        return batches

    def _apply_overflow_fallback(self, extractor: SceneExtractor, scenes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        expanded: List[Dict[str, Any]] = []
        overflow_threshold = max(self.target_scene_words * 2, self.target_scene_words + 400)
        for scene in scenes:
            chapter_indices = list(scene.get("source_chapter_indices") or [])
            if len(chapter_indices) <= 1 and int(scene.get("length") or 0) > overflow_threshold:
                expanded.extend(self._split_oversized_scene(scene))
            else:
                expanded.append(scene)
        return expanded

    def _split_oversized_scene(self, scene: Dict[str, Any]) -> List[Dict[str, Any]]:
        text = str(scene.get("text") or "").strip()
        if not text:
            return [scene]
        paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
        if len(paragraphs) <= 1:
            return self._split_scene_by_words(scene)

        min_words = max(100, int(self.target_scene_words * 0.75))
        max_words = max(min_words + 40, int(self.target_scene_words * 1.2))
        chunks: List[Dict[str, Any]] = []
        current: List[str] = []
        current_words = 0
        for paragraph in paragraphs:
            paragraph_words = len(paragraph.split())
            projected = current_words + paragraph_words
            if current and current_words >= min_words and projected > max_words:
                chunks.append(self._scene_from_paragraphs(scene, current))
                current = [paragraph]
                current_words = paragraph_words
            else:
                current.append(paragraph)
                current_words = projected
        if current:
            chunks.append(self._scene_from_paragraphs(scene, current))
        if len(chunks) <= 1:
            return [scene]
        for index, chunk in enumerate(chunks, start=1):
            chunk["scene_index"] = index
        return chunks

    def _scene_from_paragraphs(self, source_scene: Dict[str, Any], paragraphs: List[str]) -> Dict[str, Any]:
        text = "\n\n".join(paragraphs).strip()
        copied = dict(source_scene)
        copied["text"] = text
        copied["length"] = len(text.split())
        return copied

    def _split_scene_by_words(self, source_scene: Dict[str, Any]) -> List[Dict[str, Any]]:
        words = str(source_scene.get("text") or "").split()
        if len(words) <= max(self.target_scene_words * 2, self.target_scene_words + 400):
            return [source_scene]
        chunk_size = max(120, self.target_scene_words)
        overlap = max(0, int(chunk_size * 0.08))
        step = max(80, chunk_size - overlap)
        chunks: List[Dict[str, Any]] = []
        for start in range(0, len(words), step):
            chunk_words = words[start:start + chunk_size]
            if not chunk_words:
                break
            copied = dict(source_scene)
            copied["text"] = " ".join(chunk_words)
            copied["length"] = len(chunk_words)
            copied["scene_index"] = len(chunks) + 1
            chunks.append(copied)
            if start + chunk_size >= len(words):
                break
        return chunks or [source_scene]
