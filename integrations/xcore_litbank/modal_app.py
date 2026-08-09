"""Modal application for the xcore-litbank literary coreference service."""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

import modal
from pydantic import BaseModel, Field, model_validator


APP_NAME = os.environ.get("MODAL_XCORE_LITBANK_APP_NAME", "saga-coref-runtime")
MODAL_VERSION = "1.4.2"
PYTHON_VERSION = "3.11"
GPU_TYPE = os.environ.get("MODAL_XCORE_LITBANK_GPU", "A10")
FUNCTION_TIMEOUT_SECONDS = int(os.environ.get("MODAL_XCORE_LITBANK_TIMEOUT_SECONDS", "1800"))
CONTAINER_IDLE_SECONDS = int(os.environ.get("MODAL_XCORE_LITBANK_IDLE_SECONDS", "60"))
CACHE_DIR = "/cache"
MODEL_NAME = os.environ.get("MODAL_XCORE_LITBANK_MODEL", "sapienzanlp/xcore-litbank")

cache_volume = modal.Volume.from_name("graduation-xcore-litbank-cache", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version=PYTHON_VERSION)
    .apt_install("git")
    .run_commands(
        "python -m pip install --index-url https://download.pytorch.org/whl/cu124 torch==2.5.1",
    )
    .pip_install(
        f"modal=={MODAL_VERSION}",
        "fastapi[standard]==0.121.0",
        "numpy<2",
        "spacy>=3.8,<3.9",
        "transformers==4.48.3",
        "pytorch-lightning==2.6.5",
        "sentencepiece==0.2.0",
        "xcore-coref==0.1.2",
    )
    .env(
        {
            "HF_HOME": CACHE_DIR,
            "TRANSFORMERS_CACHE": CACHE_DIR,
            "HF_HUB_CACHE": CACHE_DIR,
            "PIP_PREFER_BINARY": "1",
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "USE_TF": "0",
            "TRANSFORMERS_NO_TF": "1",
        }
    )
)

app = modal.App(name=APP_NAME, image=image)


PRONOUNS = {
    "i",
    "me",
    "my",
    "mine",
    "myself",
    "you",
    "your",
    "yours",
    "yourself",
    "he",
    "him",
    "his",
    "himself",
    "she",
    "her",
    "hers",
    "herself",
    "it",
    "its",
    "itself",
    "we",
    "us",
    "our",
    "ours",
    "ourselves",
    "they",
    "them",
    "their",
    "theirs",
    "themselves",
}

GENERIC_CHARACTERISH = {
    "father",
    "mother",
    "sister",
    "brother",
    "king",
    "queen",
    "prince",
    "princess",
    "lord",
    "lady",
}


class ChapterInput(BaseModel):
    book_index: int = 1
    chapter_index: int = Field(ge=1)
    chapter_title: str = ""
    content: str = Field(min_length=1)
    source_file: str = ""


class AnalyzeRequest(BaseModel):
    text: str = ""
    chapters: list[ChapterInput] = Field(default_factory=list)
    use_chunking: bool = True
    allow_cross_chapter: bool = True
    chunk_target_words: int = 900
    chunk_min_words: int = 650
    chunk_max_words: int = 1200
    chunk_min_scene_words: int = 350

    @model_validator(mode="after")
    def validate_inputs(self) -> "AnalyzeRequest":
        if not str(self.text or "").strip() and not self.chapters:
            raise ValueError("Either text or chapters is required")
        return self


def flatten_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        cleaned = str(value or "").strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        output.append(cleaned)
    return output


def normalize_title(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def is_pronoun(text: str) -> bool:
    return normalize_title(text) in PRONOUNS


def looks_name_like(text: str) -> bool:
    value = str(text or "").strip()
    if not value or is_pronoun(value):
        return False
    tokens = re.findall(r"[A-Za-z][A-Za-z'’-]*", value)
    if not tokens or len(tokens) > 5:
        return False
    if any(token[0].isupper() for token in tokens):
        return True
    return normalize_title(value) in GENERIC_CHARACTERISH


def choose_display_name(mentions: list[str]) -> str:
    cleaned = flatten_unique(mentions)
    non_pronouns = [item for item in cleaned if not is_pronoun(item)]
    strong = [item for item in non_pronouns if looks_name_like(item)]
    if strong:
        strong.sort(key=lambda item: (len(item.split()), len(item), item), reverse=True)
        return strong[0]
    if non_pronouns:
        non_pronouns.sort(key=lambda item: (len(item.split()), len(item), item), reverse=True)
        return non_pronouns[0]
    return cleaned[0] if cleaned else ""


def normalize_cluster(cluster_id: int, mentions: list[str], offsets: list[Any] | None = None) -> dict[str, Any] | None:
    mention_list = [str(item).strip() for item in mentions if str(item).strip()]
    if not mention_list:
        return None
    display_name = choose_display_name(mention_list)
    if not display_name or is_pronoun(display_name):
        return None
    aliases = [item for item in flatten_unique(mention_list) if not is_pronoun(item) and item != display_name]
    proper_mentions = [item for item in flatten_unique(mention_list) if looks_name_like(item) and not is_pronoun(item)]
    pronoun_mentions = [item for item in flatten_unique(mention_list) if is_pronoun(item)]
    return {
        "cluster_id": cluster_id,
        "display_name": display_name,
        "aliases": aliases,
        "mentions": mention_list,
        "mention_count": len(mention_list),
        "proper_mentions": proper_mentions,
        "pronoun_mentions": pronoun_mentions,
        "offsets": offsets or [],
    }


class SceneExtractor:
    CHAPTER_BATCH_MIN_WORDS = 1600

    def __init__(
        self,
        target_words: int = 700,
        target_min_words: int | None = None,
        target_max_words: int | None = None,
        min_scene_words: int | None = None,
    ) -> None:
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

    def extract_many(self, chapters: list[dict[str, Any]], allow_cross_chapter: bool = True) -> list[dict[str, Any]]:
        if self.target_words == 0:
            return []
        paragraph_records: list[dict[str, Any]] = []
        for chapter in chapters:
            chapter_paragraphs = self._split_paragraphs(chapter.get("content", ""))
            for paragraph in chapter_paragraphs:
                paragraph_records.append(
                    {
                        "book_index": int(chapter.get("book_index", 1) or 1),
                        "chapter_index": int(chapter["chapter_index"]),
                        "chapter_title": str(chapter.get("chapter_title", "")),
                        "source_file": str(chapter.get("source_file", "")),
                        "paragraph": paragraph,
                        "word_count": self._word_count(paragraph),
                    }
                )
        return self._build_scene_records(paragraph_records, allow_cross_chapter=allow_cross_chapter)

    def _build_scene_records(self, paragraph_records: list[dict[str, Any]], allow_cross_chapter: bool) -> list[dict[str, Any]]:
        if not paragraph_records:
            return []
        scenes: list[dict[str, Any]] = []
        current_records: list[dict[str, Any]] = []
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

    def _records_to_scene(self, records: list[dict[str, Any]]) -> dict[str, Any]:
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

    def _merge_small_scenes(self, scenes: list[dict[str, Any]], allow_cross_chapter: bool) -> list[dict[str, Any]]:
        if not scenes:
            return []
        merged: list[dict[str, Any]] = []
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

    def _combine_scenes(self, left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
        combined_text = f"{left['text']}\n\n{right['text']}".strip()
        return {
            **left,
            "text": combined_text,
            "length": self._word_count(combined_text),
            "target_words": self.target_words,
            "end_chapter_index": right.get("end_chapter_index", right["chapter_index"]),
            "source_chapter_indices": sorted(
                set((left.get("source_chapter_indices") or [left["chapter_index"]]) + (right.get("source_chapter_indices") or [right["chapter_index"]]))
            ),
            "source_files": sorted(set((left.get("source_files") or []) + (right.get("source_files") or []))),
        }

    def _reindex_scenes(self, scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_anchor: dict[tuple[int, int], int] = {}
        reindexed = []
        for scene in scenes:
            key = (scene["book_index"], scene["chapter_index"])
            by_anchor[key] = by_anchor.get(key, 0) + 1
            reindexed.append({**scene, "scene_index": by_anchor[key]})
        return reindexed

    def _split_paragraphs(self, text: str) -> list[str]:
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


def merge_cluster_rows(clusters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    next_id = 1
    for cluster in clusters:
        display_name = str(cluster.get("display_name") or "").strip()
        if not display_name:
            continue
        key = display_name.casefold()
        current = merged.get(key)
        if current is None:
            merged[key] = {
                "cluster_id": next_id,
                "display_name": display_name,
                "aliases": list(cluster.get("aliases") or []),
                "mentions": list(cluster.get("mentions") or []),
                "mention_count": int(cluster.get("mention_count", 0) or 0),
                "proper_mentions": list(cluster.get("proper_mentions") or []),
                "pronoun_mentions": list(cluster.get("pronoun_mentions") or []),
            }
            next_id += 1
            continue
        current["aliases"] = flatten_unique(list(current.get("aliases") or []) + list(cluster.get("aliases") or []))
        current["mentions"] = list(current.get("mentions") or []) + list(cluster.get("mentions") or [])
        current["mention_count"] = int(current.get("mention_count", 0) or 0) + int(cluster.get("mention_count", 0) or 0)
        current["proper_mentions"] = flatten_unique(list(current.get("proper_mentions") or []) + list(cluster.get("proper_mentions") or []))
        current["pronoun_mentions"] = flatten_unique(list(current.get("pronoun_mentions") or []) + list(cluster.get("pronoun_mentions") or []))
    rows = list(merged.values())
    rows.sort(key=lambda item: (-int(item.get("mention_count", 0) or 0), str(item.get("display_name") or "").lower()))
    for index, row in enumerate(rows, start=1):
        row["cluster_id"] = index
    return rows


def _request_log(event: str, **fields: Any) -> None:
    print({"event": event, **fields}, flush=True)


@app.cls(
    image=image,
    gpu=GPU_TYPE,
    timeout=FUNCTION_TIMEOUT_SECONDS,
    scaledown_window=CONTAINER_IDLE_SECONDS,
    volumes={CACHE_DIR: cache_volume},
)
@modal.concurrent(max_inputs=1)
class XCoreLitbankService:
    @modal.enter()
    def load_model(self) -> None:
        import torch

        def patched(*args, **kwargs):
            kwargs["weights_only"] = False
            return self._torch_load(*args, **kwargs)

        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._torch_load = torch.load
        torch.load = patched
        try:
            from xcore import xCoRe

            self._model = xCoRe(hf_name_or_path=MODEL_NAME, device=self._device)
        finally:
            torch.load = self._torch_load

    @modal.method()
    def status(self) -> dict[str, Any]:
        return {
            "ready": True,
            "provider": "xcore_litbank",
            "app_name": APP_NAME,
            "model_name": MODEL_NAME,
            "device": self._device,
            "gpu": GPU_TYPE,
            "container_idle_seconds": CONTAINER_IDLE_SECONDS,
        }

    def _normalize_input(self, text: str, chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows = []
        if chapters:
            for index, chapter in enumerate(chapters, start=1):
                content = str(chapter.get("content") or "").strip()
                if not content:
                    continue
                rows.append(
                    {
                        "book_index": int(chapter.get("book_index", 1) or 1),
                        "chapter_index": int(chapter.get("chapter_index", index) or index),
                        "chapter_title": str(chapter.get("chapter_title") or ""),
                        "content": content,
                        "source_file": str(chapter.get("source_file") or ""),
                    }
                )
        elif str(text or "").strip():
            rows.append(
                {
                    "book_index": 1,
                    "chapter_index": 1,
                    "chapter_title": "",
                    "content": str(text).strip(),
                    "source_file": "",
                }
            )
        return rows

    def _run_chunked(
        self,
        chapters: list[dict[str, Any]],
        *,
        allow_cross_chapter: bool,
        chunk_target_words: int,
        chunk_min_words: int,
        chunk_max_words: int,
        chunk_min_scene_words: int,
    ) -> tuple[list[dict[str, Any]], int]:
        chunker = SceneExtractor(
            target_words=chunk_target_words,
            target_min_words=chunk_min_words,
            target_max_words=chunk_max_words,
            min_scene_words=chunk_min_scene_words,
        )
        scene_chunks = chunker.extract_many(chapters, allow_cross_chapter=allow_cross_chapter)
        merged: list[dict[str, Any]] = []
        for scene in scene_chunks:
            payload = self._model.predict(scene["text"])
            cluster_text = payload.get("clusters_token_text") or []
            cluster_offsets = payload.get("clusters_token_offsets") or []
            for index, mentions in enumerate(cluster_text, start=1):
                offsets = list(cluster_offsets[index - 1]) if index - 1 < len(cluster_offsets) else []
                row = normalize_cluster(index, list(mentions), offsets)
                if row:
                    merged.append(row)
        return merge_cluster_rows(merged), len(scene_chunks)

    def _run_unchunked(self, text: str) -> list[dict[str, Any]]:
        payload = self._model.predict(text)
        cluster_text = payload.get("clusters_token_text") or []
        cluster_offsets = payload.get("clusters_token_offsets") or []
        rows = []
        for index, mentions in enumerate(cluster_text, start=1):
            offsets = list(cluster_offsets[index - 1]) if index - 1 < len(cluster_offsets) else []
            row = normalize_cluster(index, list(mentions), offsets)
            if row:
                rows.append(row)
        return rows

    def _should_use_chunking(
        self,
        *,
        normalized_chapters: list[dict[str, Any]],
        requested_use_chunking: bool,
        chunk_min_words: int,
    ) -> bool:
        if not requested_use_chunking:
            return False
        if len(normalized_chapters) > 1:
            return True
        if not normalized_chapters:
            return False
        word_count = len(str(normalized_chapters[0].get("content") or "").split())
        return word_count > max(1, int(chunk_min_words or 650))

    @modal.method()
    def analyze(
        self,
        *,
        text: str = "",
        chapters: list[dict[str, Any]] | None = None,
        use_chunking: bool = True,
        allow_cross_chapter: bool = True,
        chunk_target_words: int = 900,
        chunk_min_words: int = 650,
        chunk_max_words: int = 1200,
        chunk_min_scene_words: int = 350,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        normalized_chapters = self._normalize_input(text, list(chapters or []))
        if not normalized_chapters:
            raise ValueError("No usable text or chapters were provided.")
        full_text = "\n\n".join(row["content"] for row in normalized_chapters).strip()
        resolved_use_chunking = self._should_use_chunking(
            normalized_chapters=normalized_chapters,
            requested_use_chunking=bool(use_chunking),
            chunk_min_words=chunk_min_words,
        )
        _request_log(
            "xcore_request_started",
            chapter_count=len(normalized_chapters),
            char_count=len(full_text),
            use_chunking=resolved_use_chunking,
            allow_cross_chapter=bool(allow_cross_chapter),
            chunk_target_words=int(chunk_target_words or 0),
        )
        if resolved_use_chunking:
            clusters, chunk_count = self._run_chunked(
                normalized_chapters,
                allow_cross_chapter=allow_cross_chapter,
                chunk_target_words=chunk_target_words,
                chunk_min_words=chunk_min_words,
                chunk_max_words=chunk_max_words,
                chunk_min_scene_words=chunk_min_scene_words,
            )
        else:
            clusters = self._run_unchunked(full_text)
            chunk_count = 1
        elapsed = round(time.perf_counter() - started, 2)
        payload = {
            "system": "xcore_litbank",
            "app_name": APP_NAME,
            "model_name": MODEL_NAME,
            "device": self._device,
            "runtime_seconds": elapsed,
            "chunk_count": chunk_count,
            "clusters": clusters,
            "input_stats": {
                "chapter_count": len(normalized_chapters),
                "word_count": len(full_text.split()),
                "char_count": len(full_text),
            },
        }
        _request_log(
            "xcore_request_completed",
            runtime_seconds=elapsed,
            chunk_count=chunk_count,
            cluster_count=len(clusters),
        )
        return payload

    @modal.fastapi_endpoint(method="POST", docs=True)
    def api(self, request: AnalyzeRequest):
        return self.analyze.local(
            text=request.text,
            chapters=[row.model_dump() for row in request.chapters],
            use_chunking=request.use_chunking,
            allow_cross_chapter=request.allow_cross_chapter,
            chunk_target_words=request.chunk_target_words,
            chunk_min_words=request.chunk_min_words,
            chunk_max_words=request.chunk_max_words,
            chunk_min_scene_words=request.chunk_min_scene_words,
        )

    @modal.fastapi_endpoint(method="GET", docs=True)
    def health(self):
        return self.status.local()


@app.local_entrypoint()
def entrypoint(
    input_path: str = "",
    chapters_path: str = "",
    use_chunking: bool = True,
    allow_cross_chapter: bool = True,
    chunk_target_words: int = 900,
    chunk_min_words: int = 650,
    chunk_max_words: int = 1200,
    chunk_min_scene_words: int = 350,
) -> None:
    service = XCoreLitbankService()
    text = ""
    chapters: list[dict[str, Any]] = []
    if chapters_path:
        chapters = json.loads(Path(chapters_path).read_text(encoding="utf-8"))
    elif input_path:
        text = Path(input_path).read_text(encoding="utf-8")
    else:
        raise SystemExit("Provide either --input-path or --chapters-path.")
    payload = service.analyze.remote(
        text=text,
        chapters=chapters,
        use_chunking=use_chunking,
        allow_cross_chapter=allow_cross_chapter,
        chunk_target_words=chunk_target_words,
        chunk_min_words=chunk_min_words,
        chunk_max_words=chunk_max_words,
        chunk_min_scene_words=chunk_min_scene_words,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
