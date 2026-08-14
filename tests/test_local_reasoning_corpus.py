from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.build_local_reasoning_corpus import build_corpus, corpus_fingerprint, select_segment


def test_segment_selection_is_deterministic_and_bounded():
    text = "0123456789"
    assert select_segment(text, segment="opening", max_chars=4) == "0123"
    assert select_segment(text, segment="middle", max_chars=4) == "3456"
    assert select_segment(text, segment="closing", max_chars=4) == "6789"


def test_corpus_builder_validates_source_identity_and_materializes_no_more_than_the_bound(tmp_path: Path):
    source = tmp_path / "book.txt"
    source.write_text("Chapter 1\n" + "story " * 100, encoding="utf-8")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "suite_id": "suite", "corpus_version": "1",
        "sampling": {"max_chars_per_case": 40},
        "task_families": ["structured_json"],
        "sources": [{
            "source_id": "book", "path": str(source), "sha256": digest,
            "chapter_count": 1,
            "cases": [{"chapter_index": 1, "segment": "opening"}],
        }],
    }), encoding="utf-8")

    payload = build_corpus(manifest)

    assert len(payload["cases"]) == 1
    assert payload["cases"][0]["char_count"] <= 40
    assert payload["cases"][0]["text_sha256"] == hashlib.sha256(
        payload["cases"][0]["text"].encode("utf-8")
    ).hexdigest()

    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    manifest_payload["sources"][0]["sha256"] = "0" * 64
    manifest.write_text(json.dumps(manifest_payload), encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        build_corpus(manifest)


def test_corpus_fingerprint_ignores_serialization_but_detects_content_change():
    corpus = {
        "suite_id": "suite", "corpus_version": "1", "manifest_sha256": "a" * 64,
        "cases": [{
            "case_id": "case", "source_id": "book", "source_sha256": "b" * 64,
            "chapter_index": 1, "segment": "opening", "text_sha256": "c" * 64,
            "char_count": 42,
        }],
    }
    assert corpus_fingerprint(corpus) == corpus_fingerprint(json.loads(json.dumps(corpus, indent=4)))
    changed = json.loads(json.dumps(corpus))
    changed["cases"][0]["text_sha256"] = "d" * 64
    assert corpus_fingerprint(changed) != corpus_fingerprint(corpus)
