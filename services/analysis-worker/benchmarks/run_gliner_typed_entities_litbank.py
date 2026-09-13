#!/usr/bin/env python3
"""Run pinned GLiNER typed-entity inference over the public LitBank corpus.

This benchmark runner is intentionally GLiNER-only. It emits provider evidence for
S.A.G.A.'s current typed-entity contract and does not run coreference or change
canonical identity state.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import resource
import sys
import time
from typing import Any

from gliner import GLiNER
from huggingface_hub import snapshot_download

GLINER_CODE_REPOSITORY = "urchade/GLiNER"
GLINER_CODE_COMMIT = "cf9e5f7d9fb99158b592132a9ec7cbfabb43a9a0"
GLINER_PACKAGE_VERSION = "0.2.29"
GLINER_MODEL_ID = "urchade/gliner_small-v2.1"
GLINER_MODEL_REVISION = "f23104c107e3c57f5c7aa36d53a9667c67b4b866"
GLINER_LABELS = [
    "person",
    "location",
    "facility",
    "geopolitical entity",
    "organization",
    "vehicle",
]
GLINER_THRESHOLD = 0.5
GLINER_WINDOW_CODE_POINTS = 1400
GLINER_OVERLAP_CODE_POINTS = 180
GLINER_BATCH_SIZE = 12
RAW_SCHEMA = "saga-gliner-raw-entity-output-v1"
RUN_SCHEMA = "saga-gliner-typed-entity-litbank-run-v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--litbank-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--metadata-out", required=True)
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_artifacts(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        rows.append(
            {
                "name": str(path.relative_to(root)),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return rows


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def deterministic_chunks(text: str) -> list[tuple[int, int]]:
    if not text:
        return []
    chunks: list[tuple[int, int]] = []
    start = 0
    minimum_window = int(GLINER_WINDOW_CODE_POINTS * 0.65)
    while start < len(text):
        target = min(len(text), start + GLINER_WINDOW_CODE_POINTS)
        end = target
        if target < len(text):
            candidate = max(
                text.rfind("\n", start + minimum_window, target),
                text.rfind(" ", start + minimum_window, target),
            )
            if candidate > start:
                end = candidate + 1
        if end <= start:
            end = target
        chunks.append((start, end))
        if end >= len(text):
            break
        next_start = max(start + 1, end - GLINER_OVERLAP_CODE_POINTS)
        while next_start > start and not text[next_start - 1].isspace():
            next_start -= 1
        start = next_start
    return chunks


def infer_entities(model: GLiNER, text: str) -> list[dict[str, Any]]:
    dedup: dict[tuple[int, int, str], dict[str, Any]] = {}
    for chunk_start, chunk_end in deterministic_chunks(text):
        chunk = text[chunk_start:chunk_end]
        predictions = model.predict_entities(chunk, GLINER_LABELS, threshold=GLINER_THRESHOLD)
        for prediction in predictions:
            start = chunk_start + int(prediction["start"])
            end = chunk_start + int(prediction["end"])
            label = str(prediction["label"]).strip().lower()
            surface = str(prediction["text"])
            score = float(prediction["score"])
            if label not in GLINER_LABELS:
                raise ValueError(f"gliner_unknown_label:{label}")
            if start < 0 or end <= start or end > len(text):
                raise ValueError(f"gliner_span_out_of_range:{start}:{end}")
            if not 0.0 <= score <= 1.0:
                raise ValueError(f"gliner_score_out_of_range:{score}")
            observed = text[start:end]
            if observed != surface:
                raise ValueError(
                    "gliner_surface_mismatch:"
                    + json.dumps({"predicted": surface, "observed": observed}, ensure_ascii=False)
                )
            row = {
                "startOffset": start,
                "endOffset": end,
                "surfaceText": surface,
                "label": label,
                "score": score,
            }
            key = (start, end, label)
            previous = dedup.get(key)
            if previous is None or score > float(previous["score"]):
                dedup[key] = row
    return sorted(
        dedup.values(),
        key=lambda row: (row["startOffset"], row["endOffset"], row["label"], -row["score"]),
    )


def pinned_configuration() -> dict[str, Any]:
    return {
        "package": "gliner",
        "packageVersion": GLINER_PACKAGE_VERSION,
        "model": GLINER_MODEL_ID,
        "modelRevision": GLINER_MODEL_REVISION,
        "labels": GLINER_LABELS,
        "threshold": GLINER_THRESHOLD,
        "windowCodePoints": GLINER_WINDOW_CODE_POINTS,
        "overlapCodePoints": GLINER_OVERLAP_CODE_POINTS,
        "batchSize": GLINER_BATCH_SIZE,
    }


def main() -> int:
    args = parse_args()
    litbank_root = Path(args.litbank_root).resolve()
    annotation_dir = litbank_root / "coref" / "tsv"
    output_root = Path(args.output_root).resolve()
    metadata_out = Path(args.metadata_out).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    metadata_out.parent.mkdir(parents=True, exist_ok=True)

    texts = sorted(annotation_dir.glob("*.txt"))
    if args.limit is not None:
        if args.limit <= 0:
            raise ValueError("--limit must be positive")
        texts = texts[: args.limit]
    if not texts:
        raise RuntimeError("no LitBank coref/tsv text files found")

    installed_gliner = package_version("gliner")
    if installed_gliner != GLINER_PACKAGE_VERSION:
        raise RuntimeError(
            f"gliner_package_version_mismatch:expected={GLINER_PACKAGE_VERSION}:actual={installed_gliner}"
        )

    cache_root = Path.home() / ".cache" / "saga-phase3-gliner-typed-entities"
    cache_root.mkdir(parents=True, exist_ok=True)
    download_started = time.perf_counter()
    model_snapshot = Path(
        snapshot_download(
            repo_id=GLINER_MODEL_ID,
            revision=GLINER_MODEL_REVISION,
            cache_dir=str(cache_root / "huggingface"),
        )
    )
    download_seconds = time.perf_counter() - download_started

    initialization_started = time.perf_counter()
    model = GLiNER.from_pretrained(str(model_snapshot))
    initialization_seconds = time.perf_counter() - initialization_started

    inference_started = time.perf_counter()
    completed = 0
    documents: list[dict[str, Any]] = []
    label_counts = {label: 0 for label in GLINER_LABELS}
    for text_path in texts:
        document_id = text_path.stem
        text = normalize_newlines(text_path.read_text(encoding="utf-8"))
        document_started = time.perf_counter()
        try:
            detections = infer_entities(model, text)
            for detection in detections:
                label_counts[detection["label"]] += 1
            normalized_input_fingerprint = hashlib.sha256(text.encode("utf-8")).hexdigest()
            output = {
                "schemaVersion": RAW_SCHEMA,
                "configuration": pinned_configuration(),
                "normalizedInputFingerprint": normalized_input_fingerprint,
                "detections": detections,
            }
            output_path = output_root / f"{document_id}.json"
            output_path.write_text(
                json.dumps(output, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            completed += 1
            documents.append(
                {
                    "documentId": document_id,
                    "status": "completed",
                    "wallClockSeconds": time.perf_counter() - document_started,
                    "inputBytes": text_path.stat().st_size,
                    "inputCodePoints": len(text),
                    "detectionCount": len(detections),
                    "outputSha256": sha256_file(output_path),
                }
            )
        except Exception as exc:  # benchmark record must preserve per-document failure evidence
            documents.append(
                {
                    "documentId": document_id,
                    "status": "failed",
                    "wallClockSeconds": time.perf_counter() - document_started,
                    "inputBytes": text_path.stat().st_size,
                    "inputCodePoints": len(text),
                    "errorType": type(exc).__name__,
                    "error": str(exc),
                }
            )

    inference_seconds = time.perf_counter() - inference_started
    usage = resource.getrusage(resource.RUSAGE_SELF)
    self_peak_rss_mb = usage.ru_maxrss / 1024.0
    model_artifacts = snapshot_artifacts(model_snapshot)
    model_artifact_bytes = sum(row["bytes"] for row in model_artifacts)
    metadata = {
        "schemaVersion": RUN_SCHEMA,
        "runner": "services/analysis-worker/benchmarks/run_gliner_typed_entities_litbank.py",
        "candidateCode": {
            "repository": GLINER_CODE_REPOSITORY,
            "commit": GLINER_CODE_COMMIT,
            "license": "Apache-2.0",
        },
        "model": {
            "repository": GLINER_MODEL_ID,
            "revision": GLINER_MODEL_REVISION,
            "license": "Apache-2.0",
        },
        "configuration": pinned_configuration(),
        "python": sys.version,
        "platform": platform.platform(),
        "cpuCount": os.cpu_count(),
        "packages": {
            "gliner": installed_gliner,
            "huggingface_hub": package_version("huggingface_hub"),
            "numpy": package_version("numpy"),
            "safetensors": package_version("safetensors"),
            "sentencepiece": package_version("sentencepiece"),
            "torch": package_version("torch"),
            "transformers": package_version("transformers"),
        },
        "downloadSeconds": download_seconds,
        "initializationSeconds": initialization_seconds,
        "inferenceWallClockSeconds": inference_seconds,
        "selfPeakResidentMemoryMb": self_peak_rss_mb,
        "gpu": None,
        "peakVramMb": None,
        "attemptedDocumentCount": len(texts),
        "completedDocumentCount": completed,
        "failedDocumentCount": len(texts) - completed,
        "modelArtifactBytes": model_artifact_bytes,
        "modelArtifacts": model_artifacts,
        "labelCounts": label_counts,
        "documents": documents,
    }
    metadata_out.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: metadata[key]
                for key in (
                    "downloadSeconds",
                    "initializationSeconds",
                    "inferenceWallClockSeconds",
                    "selfPeakResidentMemoryMb",
                    "attemptedDocumentCount",
                    "completedDocumentCount",
                    "failedDocumentCount",
                    "modelArtifactBytes",
                    "labelCounts",
                )
            },
            indent=2,
        )
    )
    return 0 if completed == len(texts) else 2


if __name__ == "__main__":
    raise SystemExit(main())
