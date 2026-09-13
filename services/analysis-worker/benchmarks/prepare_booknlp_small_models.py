#!/usr/bin/env python3
"""Prepare the pinned BookNLP-small artifacts for dedicated Phase-3 benchmarks.

This is benchmark/setup code, not production runtime logic. The production-shaped
runner deliberately refuses to download missing models. This helper makes the
networked preparation step explicit, records exact bytes/digests, and completes
before the subprocess provider is invoked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

MODEL_BASE_URL = "http://people.ischool.berkeley.edu/~dbamman/booknlp_models"
MODEL_FILES = (
    "entities_google_bert_uncased_L-4_H-256_A-4-v1.0.model",
    "coref_google_bert_uncased_L-2_H-256_A-4-v1.0.model",
    "speaker_google_bert_uncased_L-8_H-256_A-4-v1.0.1.model",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--manifest-out", required=True)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    args = parse_args()
    model_dir = Path(args.model_dir).resolve()
    manifest_out = Path(args.manifest_out).resolve()
    model_dir.mkdir(parents=True, exist_ok=True)
    manifest_out.parent.mkdir(parents=True, exist_ok=True)

    artifacts = []
    for name in MODEL_FILES:
        target = model_dir / name
        url = f"{MODEL_BASE_URL}/{name}"
        if not target.is_file():
            partial = target.with_suffix(target.suffix + ".partial")
            partial.unlink(missing_ok=True)
            urllib.request.urlretrieve(url, partial)
            partial.replace(target)
        artifacts.append(
            {
                "name": name,
                "sourceUrl": url,
                "bytes": target.stat().st_size,
                "sha256": sha256_file(target),
            }
        )

    manifest = {
        "schemaVersion": "saga-booknlp-model-manifest-v1",
        "model": "small",
        "artifacts": artifacts,
        "modelArtifactBytes": sum(row["bytes"] for row in artifacts),
    }
    manifest_out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
