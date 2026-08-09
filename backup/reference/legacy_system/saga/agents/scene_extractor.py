"""Deterministic text chunking utilities for scene-sized narrative segments."""

import re
from typing import Dict, List


class SceneExtractor:
    """Split chapter text into ordered chunks without using an LLM.

    The extractor now targets an approximate word count instead of a small set
    of presets. When the target size is larger than an individual chapter, the
    extractor can continue accumulating paragraphs from subsequent chapters so a
    single scene chunk may span chapter boundaries.
    """

    def __init__(
        self,
        target_words: int = 700,
        target_min_words: int | None = None,
        target_max_words: int | None = None,
        min_scene_words: int | None = None,
    ):
        target_words = max(0, int(target_words))
        self.target_words = target_words
        if self.target_words == 0:
            self.target_min_words = 0
            self.target_max_words = 0
            self.min_scene_words = 0
        else:
            self.target_min_words = target_min_words or max(100, int(target_words * 0.75))
            self.target_max_words = target_max_words or max(self.target_min_words + 40, int(target_words * 1.2))
            self.min_scene_words = min_scene_words or max(90, int(target_words * 0.45))

    @classmethod
    def from_target_words(cls, target_words: int) -> "SceneExtractor":
        return cls(target_words=target_words)

    def extract(self, chapter: Dict) -> List[Dict]:
        if self.target_words == 0:
            paragraphs = self._split_paragraphs(chapter.get("content", ""))
            if not paragraphs:
                return []

            chapter_text = "\n\n".join(paragraphs).strip()
            chapter_length = self._word_count(chapter_text)
            if not chapter_length:
                return []

            source_file = chapter.get("source_file", "")
            return [{
                "book_index": chapter["book_index"],
                "chapter_index": chapter["chapter_index"],
                "chapter_title": chapter.get("chapter_title", ""),
                "scene_index": 1,
                "text": chapter_text,
                "length": chapter_length,
                "target_words": self.target_words,
                "source_chapter_indices": [chapter["chapter_index"]],
                "end_chapter_index": chapter["chapter_index"],
                "source_files": [source_file] if source_file else [],
            }]
        return self.extract_many([chapter], allow_cross_chapter=False)

    def extract_many(self, chapters: List[Dict], allow_cross_chapter: bool = True) -> List[Dict]:
        if self.target_words == 0:
            return self._extract_chapter_batches(chapters)

        paragraph_records: List[Dict] = []
        for chapter in chapters:
            chapter_paragraphs = self._split_paragraphs(chapter.get("content", ""))
            for paragraph in chapter_paragraphs:
                paragraph_records.append({
                    "book_index": chapter["book_index"],
                    "chapter_index": chapter["chapter_index"],
                    "chapter_title": chapter.get("chapter_title", ""),
                    "source_file": chapter.get("source_file", ""),
                    "paragraph": paragraph,
                    "word_count": self._word_count(paragraph),
                })

        return self._build_scene_records(paragraph_records, allow_cross_chapter=allow_cross_chapter)

    def split_scene(self, scene: Dict, target_words: int) -> List[Dict]:
        extractor = SceneExtractor.from_target_words(target_words)
        paragraphs = extractor._split_paragraphs(scene.get("text", ""))
        paragraph_records = []
        source_chapters = scene.get("source_chapter_indices") or [scene.get("chapter_index")]
        source_files = scene.get("source_files") or ([scene.get("source_file")] if scene.get("source_file") else [])
        for paragraph in paragraphs:
            paragraph_records.append({
                "book_index": scene["book_index"],
                "chapter_index": scene["chapter_index"],
                "chapter_title": scene.get("chapter_title", ""),
                "source_file": source_files[0] if source_files else "",
                "paragraph": paragraph,
                "word_count": extractor._word_count(paragraph),
            })

        split_records = extractor._build_scene_records(paragraph_records, allow_cross_chapter=False)
        for index, item in enumerate(split_records, start=1):
            item["book_index"] = scene["book_index"]
            item["chapter_index"] = scene["chapter_index"]
            item["scene_index"] = index
            item["source_chapter_indices"] = source_chapters
            item["end_chapter_index"] = scene.get("end_chapter_index", scene["chapter_index"])
            item["source_files"] = source_files
        return split_records

    def _extract_chapter_batches(self, chapters: List[Dict]) -> List[Dict]:
        batches: List[Dict] = []
        current_batch: List[Dict] = []
        current_words = 0

        for chapter in chapters:
            chapter_scene = self.extract(chapter)
            if not chapter_scene:
                continue
            chapter_record = chapter_scene[0]
            chapter_words = int(chapter_record.get("length") or 0)
            if not current_batch:
                current_batch = [chapter_record]
                current_words = chapter_words
                continue

            same_book = current_batch[-1]["book_index"] == chapter_record["book_index"]
            if same_book and current_words < self.CHAPTER_BATCH_MIN_WORDS:
                current_batch.append(chapter_record)
                current_words += chapter_words
                continue

            batches.append(self._combine_chapter_batch(current_batch))
            current_batch = [chapter_record]
            current_words = chapter_words

        if current_batch:
            if batches and current_words < self.CHAPTER_BATCH_MIN_WORDS and batches[-1]["book_index"] == current_batch[0]["book_index"]:
                combined = self._combine_chapter_batch(current_batch)
                batches[-1] = self._combine_scenes(batches[-1], combined)
            else:
                batches.append(self._combine_chapter_batch(current_batch))

        return self._reindex_scenes(batches)

    def _combine_chapter_batch(self, records: List[Dict]) -> Dict:
        if len(records) == 1:
            return dict(records[0])
        combined = dict(records[0])
        for record in records[1:]:
            combined = self._combine_scenes(combined, record)
        combined["chapter_title"] = records[0].get("chapter_title", "")
        combined["chapter_index"] = records[0]["chapter_index"]
        return combined

    def _build_scene_records(self, paragraph_records: List[Dict], allow_cross_chapter: bool) -> List[Dict]:
        if not paragraph_records:
            return []

        scenes: List[Dict] = []
        current_records: List[Dict] = []
        current_words = 0

        for record in paragraph_records:
            if not allow_cross_chapter and current_records:
                previous_chapter = current_records[-1]["chapter_index"]
                if record["chapter_index"] != previous_chapter:
                    scenes.append(self._records_to_scene(current_records))
                    current_records = []
                    current_words = 0

            projected_words = current_words + record["word_count"]
            if current_records and current_words >= self.target_min_words and projected_words > self.target_max_words:
                scenes.append(self._records_to_scene(current_records))
                current_records = [record]
                current_words = record["word_count"]
                continue

            current_records.append(record)
            current_words = projected_words

        if current_records:
            scenes.append(self._records_to_scene(current_records))

        scenes = self._merge_small_scenes(scenes, allow_cross_chapter=allow_cross_chapter)
        return self._reindex_scenes(scenes)

    def _records_to_scene(self, records: List[Dict]) -> Dict:
        text = "\n\n".join(record["paragraph"] for record in records).strip()
        chapter_indices = [record["chapter_index"] for record in records]
        source_files = sorted({record.get("source_file", "") for record in records if record.get("source_file")})
        return {
            "book_index": records[0]["book_index"],
            "chapter_index": records[0]["chapter_index"],
            "chapter_title": records[0].get("chapter_title", ""),
            "scene_index": 1,
            "text": text,
            "length": self._word_count(text),
            "target_words": self.target_words,
            "source_chapter_indices": sorted(set(chapter_indices)),
            "end_chapter_index": chapter_indices[-1],
            "source_files": source_files,
        }

    def _merge_small_scenes(self, scenes: List[Dict], allow_cross_chapter: bool) -> List[Dict]:
        if not scenes:
            return []

        merged: List[Dict] = []
        for scene in scenes:
            if not merged:
                merged.append(scene)
                continue

            same_book = merged[-1]["book_index"] == scene["book_index"]
            cross_ok = allow_cross_chapter or merged[-1]["chapter_index"] == scene["chapter_index"]
            if scene["length"] < self.min_scene_words and same_book and cross_ok:
                merged[-1] = self._combine_scenes(merged[-1], scene)
            else:
                merged.append(scene)

        if len(merged) > 1 and merged[0]["length"] < self.min_scene_words:
            merged[1] = self._combine_scenes(merged[0], merged[1])
            merged = merged[1:]

        return merged

    def _combine_scenes(self, left: Dict, right: Dict) -> Dict:
        combined_text = f"{left['text']}\n\n{right['text']}".strip()
        return {
            **left,
            "text": combined_text,
            "length": self._word_count(combined_text),
            "target_words": self.target_words,
            "end_chapter_index": right.get("end_chapter_index", right["chapter_index"]),
            "source_chapter_indices": sorted(set((left.get("source_chapter_indices") or [left["chapter_index"]]) + (right.get("source_chapter_indices") or [right["chapter_index"]]))),
            "source_files": sorted(set((left.get("source_files") or []) + (right.get("source_files") or []))),
        }

    def _reindex_scenes(self, scenes: List[Dict]) -> List[Dict]:
        by_anchor: dict[tuple[int, int], int] = {}
        reindexed = []
        for scene in scenes:
            key = (scene["book_index"], scene["chapter_index"])
            by_anchor[key] = by_anchor.get(key, 0) + 1
            reindexed.append({
                **scene,
                "scene_index": by_anchor[key],
            })
        return reindexed

    def _split_paragraphs(self, text: str) -> List[str]:
        text = (text or "").strip()
        if not text:
            return []

        parts = re.split(r"\n+", text)
        paragraphs = [self._clean(paragraph) for paragraph in parts if self._clean(paragraph)]

        merged = []
        for paragraph in paragraphs:
            if merged and self._word_count(paragraph) < 12:
                merged[-1] = f"{merged[-1]} {paragraph}".strip()
            else:
                merged.append(paragraph)

        return merged

    def _word_count(self, text: str) -> int:
        return len((text or "").split())

    def _clean(self, text: str) -> str:
        text = re.sub(r"\r\n|\r", "\n", text or "")
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()
    CHAPTER_BATCH_MIN_WORDS = 1600
