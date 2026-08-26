"""Materialize authorized local book samples from a versioned corpus manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import unicodedata
from pathlib import Path
from typing import Any

from packages.analysis_foundation import parse_source_document


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="benchmarks/reasoning/local_books_v1.json")
    parser.add_argument("--output", default="analysis_outputs/local_reasoning/corpus_v1.json")
    args = parser.parse_args()
    payload = build_corpus(Path(args.manifest))
    target = Path(args.output).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "suite_id": payload["suite_id"],
        "corpus_version": payload["corpus_version"],
        "case_count": len(payload["cases"]),
        "output": str(target),
    }, indent=2))
    return 0


def build_corpus(manifest_path: Path) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    max_chars = max(1, int((manifest.get("sampling") or {}).get("max_chars_per_case") or 12000))
    cases: list[dict[str, Any]] = []
    for source in list(manifest.get("sources") or []):
        path = Path(str(source.get("path") or "")).resolve()
        raw_bytes = path.read_bytes()
        actual_sha256 = hashlib.sha256(raw_bytes).hexdigest()
        expected_sha256 = str(source.get("sha256") or "")
        if actual_sha256 != expected_sha256:
            raise ValueError(f"Source hash mismatch for '{source.get('source_id')}'.")
        source_type = path.suffix.lstrip(".").lower() or "txt"
        parsed = parse_source_document(path, source_type=source_type, raw_bytes=raw_bytes)
        chapters = list(parsed.get("chapters") or [])
        if len(chapters) != int(source.get("chapter_count") or 0):
            raise ValueError(f"Chapter count mismatch for '{source.get('source_id')}'.")
        for selection in list(source.get("cases") or []):
            chapter_index = int(selection["chapter_index"])
            if chapter_index < 1 or chapter_index > len(chapters):
                raise ValueError(f"Invalid chapter index {chapter_index} for '{source.get('source_id')}'.")
            chapter = chapters[chapter_index - 1]
            segment = str(selection.get("segment") or "opening")
            text = select_segment(str(chapter.get("content") or ""), segment=segment, max_chars=max_chars)
            cases.append({
                "case_id": f"{source['source_id']}-chapter-{chapter_index:03d}-{segment}",
                "source_id": source["source_id"],
                "source_sha256": actual_sha256,
                "chapter_index": chapter_index,
                "chapter_title": str(chapter.get("title") or f"Chapter {chapter_index}"),
                "segment": segment,
                "text": text,
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "char_count": len(text),
            })
    return {
        "suite_id": manifest["suite_id"],
        "corpus_version": manifest["corpus_version"],
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "task_families": list(manifest.get("task_families") or []),
        "cases": cases,
    }


def corpus_fingerprint(corpus: dict[str, Any]) -> str:
    """Identify sampled content independently of JSON formatting."""

    identity = {
        "suite_id": str(corpus.get("suite_id") or ""),
        "corpus_version": str(corpus.get("corpus_version") or ""),
        "manifest_sha256": str(corpus.get("manifest_sha256") or ""),
        "cases": [{
            "case_id": str(case.get("case_id") or ""),
            "source_id": str(case.get("source_id") or ""),
            "source_sha256": str(case.get("source_sha256") or ""),
            "chapter_index": int(case.get("chapter_index") or 0),
            "segment": str(case.get("segment") or ""),
            "text_sha256": str(case.get("text_sha256") or ""),
            "char_count": int(case.get("char_count") or 0),
        } for case in list(corpus.get("cases") or [])],
    }
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def select_segment(value: str, *, segment: str, max_chars: int) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(text) <= max_chars:
        return text
    if segment == "opening":
        start = 0
    elif segment == "middle":
        start = max(0, (len(text) - max_chars) // 2)
    elif segment == "closing":
        start = len(text) - max_chars
    else:
        raise ValueError(f"Unsupported segment '{segment}'.")
    return text[start:start + max_chars].strip()


if __name__ == "__main__":
    raise SystemExit(main())
