#!/usr/bin/env python3
"""Benchmark-only BookNLP runner for the pinned LitBank corpus.

This script is intentionally outside the production worker runtime. It executes
BookNLP with the small model, records exact package/model artifact provenance,
and writes raw BookNLP outputs for S.A.G.A.'s TypeScript evaluator.
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
import shutil
import sys
import time
from typing import Any

from booknlp.booknlp import BookNLP

BOOKNLP_BASE_COMMIT = "3d900fc2224e55960c3363826ae28539b77b4204"
BOOKNLP_COMPAT_COMMIT = "8875a1b616d764b7d13d1e30e9949cc21ca303c1"


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


def model_artifacts(model_root: Path) -> list[dict[str, Any]]:
    if not model_root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(candidate for candidate in model_root.rglob("*") if candidate.is_file()):
        rows.append(
            {
                "name": str(path.relative_to(model_root)),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return rows


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

    model_root = Path.home() / "booknlp_models"
    model_params = {
        "pipeline": "entity,quote,event,coref",
        "model": "small",
        "model_path": str(model_root),
    }

    started = time.perf_counter()
    initialization_started = time.perf_counter()
    booknlp = BookNLP("en", model_params)
    initialization_seconds = time.perf_counter() - initialization_started

    documents: list[dict[str, Any]] = []
    completed = 0
    for text_path in texts:
        document_id = text_path.stem
        document_output = output_root / document_id
        if document_output.exists():
            shutil.rmtree(document_output)
        document_output.mkdir(parents=True, exist_ok=True)

        document_started = time.perf_counter()
        try:
            booknlp.process(str(text_path), str(document_output), document_id)
            duration = time.perf_counter() - document_started
            completed += 1
            documents.append(
                {
                    "documentId": document_id,
                    "status": "completed",
                    "wallClockSeconds": duration,
                    "inputBytes": text_path.stat().st_size,
                }
            )
        except Exception as exc:  # benchmark record should preserve provider failures
            documents.append(
                {
                    "documentId": document_id,
                    "status": "failed",
                    "wallClockSeconds": time.perf_counter() - document_started,
                    "inputBytes": text_path.stat().st_size,
                    "errorType": type(exc).__name__,
                    "error": str(exc),
                }
            )

    artifacts = model_artifacts(model_root)
    total_seconds = time.perf_counter() - started
    usage = resource.getrusage(resource.RUSAGE_SELF)
    peak_rss_mb = usage.ru_maxrss / 1024.0  # Linux reports KiB.

    gpu_name = None
    peak_vram_mb = None
    try:
        import torch

        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            peak_vram_mb = torch.cuda.max_memory_allocated(0) / (1024 * 1024)
    except Exception:
        pass

    metadata = {
        "schemaVersion": "saga-booknlp-run-metadata-v1",
        "runner": "services/analysis-worker/benchmarks/run_booknlp_litbank.py",
        "candidateCode": {
            "upstream": "booknlp/booknlp",
            "upstreamCommit": BOOKNLP_BASE_COMMIT,
            "compatibilityPatch": "booknlp/booknlp#25",
            "compatibilityCommit": BOOKNLP_COMPAT_COMMIT,
        },
        "python": sys.version,
        "platform": platform.platform(),
        "cpuCount": os.cpu_count(),
        "packages": {
            "booknlp": package_version("booknlp"),
            "spacy": package_version("spacy"),
            "torch": package_version("torch"),
            "tensorflow": package_version("tensorflow"),
            "transformers": package_version("transformers"),
        },
        "configuration": model_params,
        "initializationSeconds": initialization_seconds,
        "wallClockSeconds": total_seconds,
        "peakResidentMemoryMb": peak_rss_mb,
        "gpu": gpu_name,
        "peakVramMb": peak_vram_mb,
        "attemptedDocumentCount": len(texts),
        "completedDocumentCount": completed,
        "failedDocumentCount": len(texts) - completed,
        "modelArtifactBytes": sum(row["bytes"] for row in artifacts),
        "modelArtifacts": artifacts,
        "documents": documents,
    }
    metadata_out.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: metadata[key] for key in (
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
