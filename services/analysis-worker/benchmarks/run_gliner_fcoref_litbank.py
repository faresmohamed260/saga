#!/usr/bin/env python3
"""Benchmark-only GLiNER + F-Coref runner over pinned LitBank texts."""

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

from fastcoref import FCoref
from gliner import GLiNER
from huggingface_hub import snapshot_download

GLINER_CODE_COMMIT = "cf9e5f7d9fb99158b592132a9ec7cbfabb43a9a0"
GLINER_MODEL_ID = "urchade/gliner_small-v2.1"
GLINER_MODEL_REVISION = "f23104c107e3c57f5c7aa36d53a9667c67b4b866"
FCOREF_CODE_COMMIT = "8888e51d97d4818a25dd5f5d8b541d397fad9362"
FCOREF_MODEL_ID = "biu-nlp/f-coref"
FCOREF_MODEL_REVISION = "d5a382c8bfe1105cee1a73007525ee08ab693d9a"
GLINER_LABELS = ["person", "location", "geopolitical entity", "facility", "organization", "vehicle"]
GLINER_THRESHOLD = 0.5
GLINER_CHUNK_CHARS = 1400
GLINER_CHUNK_OVERLAP = 180
FCOREF_MAX_TOKENS_IN_BATCH = 3500


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
        rows.append({
            "name": str(path.relative_to(root)),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    return rows


def deterministic_chunks(text: str) -> list[tuple[int, int]]:
    if not text:
        return []
    chunks: list[tuple[int, int]] = []
    start = 0
    minimum_window = int(GLINER_CHUNK_CHARS * 0.65)
    while start < len(text):
        target = min(len(text), start + GLINER_CHUNK_CHARS)
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
        next_start = max(start + 1, end - GLINER_CHUNK_OVERLAP)
        while next_start > start and not text[next_start - 1].isspace():
            next_start -= 1
        start = next_start
    return chunks


def gliner_entities(model: GLiNER, text: str) -> list[dict[str, Any]]:
    dedup: dict[tuple[int, int, str], dict[str, Any]] = {}
    for chunk_start, chunk_end in deterministic_chunks(text):
        chunk = text[chunk_start:chunk_end]
        predictions = model.predict_entities(chunk, GLINER_LABELS, threshold=GLINER_THRESHOLD)
        for prediction in predictions:
            start = chunk_start + int(prediction["start"])
            end = chunk_start + int(prediction["end"])
            label = str(prediction["label"]).strip().lower()
            surface = str(prediction["text"])
            if start < 0 or end <= start or end > len(text):
                raise ValueError(f"gliner_span_out_of_range:{start}:{end}")
            observed = text[start:end]
            if observed != surface:
                raise ValueError(
                    f"gliner_surface_mismatch:{json.dumps({'predicted': surface, 'observed': observed}, ensure_ascii=False)}"
                )
            row = {
                "start": start,
                "end": end,
                "text": surface,
                "label": label,
                "score": float(prediction["score"]),
            }
            key = (start, end, label)
            previous = dedup.get(key)
            if previous is None or row["score"] > previous["score"]:
                dedup[key] = row
    return sorted(dedup.values(), key=lambda row: (row["start"], row["end"], row["label"], -row["score"]))


def fcoref_clusters(model: FCoref, text: str) -> list[list[dict[str, Any]]]:
    prediction = model.predict(texts=[text], max_tokens_in_batch=FCOREF_MAX_TOKENS_IN_BATCH)[0]
    clusters: list[list[dict[str, Any]]] = []
    for raw_cluster in prediction.get_clusters(as_strings=False):
        cluster: list[dict[str, Any]] = []
        for raw_start, raw_end in raw_cluster:
            start = int(raw_start)
            end = int(raw_end)
            if start < 0 or end <= start or end > len(text):
                raise ValueError(f"fcoref_span_out_of_range:{start}:{end}")
            cluster.append({"start": start, "end": end, "text": text[start:end]})
        cluster.sort(key=lambda row: (row["start"], row["end"], row["text"]))
        clusters.append(cluster)
    clusters.sort(key=lambda cluster: (
        cluster[0]["start"] if cluster else sys.maxsize,
        cluster[0]["end"] if cluster else sys.maxsize,
        json.dumps(cluster, sort_keys=True, ensure_ascii=False),
    ))
    return clusters


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

    cache_root = Path.home() / ".cache" / "saga-phase3-models"
    cache_root.mkdir(parents=True, exist_ok=True)
    download_started = time.perf_counter()
    gliner_snapshot = Path(snapshot_download(
        repo_id=GLINER_MODEL_ID,
        revision=GLINER_MODEL_REVISION,
        cache_dir=str(cache_root / "huggingface"),
    ))
    fcoref_snapshot = Path(snapshot_download(
        repo_id=FCOREF_MODEL_ID,
        revision=FCOREF_MODEL_REVISION,
        cache_dir=str(cache_root / "huggingface"),
    ))
    download_seconds = time.perf_counter() - download_started

    initialization_started = time.perf_counter()
    gliner_model = GLiNER.from_pretrained(str(gliner_snapshot))
    fcoref_model = FCoref(model_name_or_path=str(fcoref_snapshot), device="cpu")
    initialization_seconds = time.perf_counter() - initialization_started

    started = time.perf_counter()
    documents: list[dict[str, Any]] = []
    completed = 0
    for text_path in texts:
        document_id = text_path.stem
        text = text_path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
        document_started = time.perf_counter()
        try:
            entities = gliner_entities(gliner_model, text)
            clusters = fcoref_clusters(fcoref_model, text)
            output = {
                "schemaVersion": "saga-gliner-fcoref-raw-v1",
                "documentId": document_id,
                "textSha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "configuration": {
                    "glinerLabels": GLINER_LABELS,
                    "glinerThreshold": GLINER_THRESHOLD,
                    "glinerChunkChars": GLINER_CHUNK_CHARS,
                    "glinerChunkOverlap": GLINER_CHUNK_OVERLAP,
                    "fcorefMaxTokensInBatch": FCOREF_MAX_TOKENS_IN_BATCH,
                },
                "glinerEntities": entities,
                "fcorefClusters": clusters,
            }
            (output_root / f"{document_id}.json").write_text(
                json.dumps(output, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            completed += 1
            documents.append({
                "documentId": document_id,
                "status": "completed",
                "wallClockSeconds": time.perf_counter() - document_started,
                "inputBytes": text_path.stat().st_size,
                "glinerEntityCount": len(entities),
                "fcorefClusterCount": len(clusters),
                "fcorefMentionCount": sum(len(cluster) for cluster in clusters),
            })
        except Exception as exc:
            documents.append({
                "documentId": document_id,
                "status": "failed",
                "wallClockSeconds": time.perf_counter() - document_started,
                "inputBytes": text_path.stat().st_size,
                "errorType": type(exc).__name__,
                "error": str(exc),
            })

    usage = resource.getrusage(resource.RUSAGE_SELF)
    peak_rss_mb = usage.ru_maxrss / 1024.0
    model_artifacts = {
        "gliner": snapshot_artifacts(gliner_snapshot),
        "fcoref": snapshot_artifacts(fcoref_snapshot),
    }
    model_bytes = sum(row["bytes"] for rows in model_artifacts.values() for row in rows)
    wall_seconds = time.perf_counter() - started

    metadata = {
        "schemaVersion": "saga-gliner-fcoref-run-metadata-v1",
        "runner": "services/analysis-worker/benchmarks/run_gliner_fcoref_litbank.py",
        "candidateCode": {
            "gliner": {"repository": "urchade/GLiNER", "commit": GLINER_CODE_COMMIT},
            "fastcoref": {"repository": "Digital-Insight-Technologies-Ltd/fastcoref", "commit": FCOREF_CODE_COMMIT},
        },
        "models": {
            "gliner": {"repository": GLINER_MODEL_ID, "revision": GLINER_MODEL_REVISION, "license": "Apache-2.0"},
            "fcoref": {"repository": FCOREF_MODEL_ID, "revision": FCOREF_MODEL_REVISION, "license": "MIT"},
        },
        "configuration": {
            "glinerLabels": GLINER_LABELS,
            "glinerThreshold": GLINER_THRESHOLD,
            "glinerChunkChars": GLINER_CHUNK_CHARS,
            "glinerChunkOverlap": GLINER_CHUNK_OVERLAP,
            "fcorefMaxTokensInBatch": FCOREF_MAX_TOKENS_IN_BATCH,
        },
        "python": sys.version,
        "platform": platform.platform(),
        "cpuCount": os.cpu_count(),
        "packages": {
            "gliner": package_version("gliner"),
            "fastcoref": package_version("fastcoref"),
            "huggingface_hub": package_version("huggingface_hub"),
            "spacy": package_version("spacy"),
            "torch": package_version("torch"),
            "transformers": package_version("transformers"),
        },
        "downloadSeconds": download_seconds,
        "initializationSeconds": initialization_seconds,
        "wallClockSeconds": wall_seconds,
        "peakResidentMemoryMb": peak_rss_mb,
        "gpu": None,
        "peakVramMb": None,
        "attemptedDocumentCount": len(texts),
        "completedDocumentCount": completed,
        "failedDocumentCount": len(texts) - completed,
        "modelArtifactBytes": model_bytes,
        "modelArtifacts": model_artifacts,
        "documents": documents,
    }
    metadata_out.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: metadata[key] for key in (
        "downloadSeconds",
        "initializationSeconds",
        "wallClockSeconds",
        "peakResidentMemoryMb",
        "attemptedDocumentCount",
        "completedDocumentCount",
        "failedDocumentCount",
        "modelArtifactBytes",
    )}, indent=2))
    return 0 if completed > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
