#!/usr/bin/env python3
"""Prepare the pinned BookNLP-small artifacts for dedicated Phase-3 benchmarks.

This is benchmark/setup code, not production runtime logic. The production-shaped
runner deliberately refuses to download missing BookNLP model files and runs its
transformer stack in offline mode. This helper makes every networked preparation
step explicit before the provider boundary is invoked and records exact artifact
and cache fingerprints for the experiment.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import urllib.request

BOOKNLP_MODEL_BASE_URL = "http://people.ischool.berkeley.edu/~dbamman/booknlp_models"
BOOKNLP_MODEL_FILES = (
    "entities_google_bert_uncased_L-4_H-256_A-4-v1.0.model",
    "coref_google_bert_uncased_L-2_H-256_A-4-v1.0.model",
    "speaker_google_bert_uncased_L-8_H-256_A-4-v1.0.1.model",
)
TRANSFORMER_MODEL_IDS = (
    "google/bert_uncased_L-4_H-256_A-4",
    "google/bert_uncased_L-2_H-256_A-4",
    "google/bert_uncased_L-8_H-256_A-4",
)
SPACY_MODEL = "en_core_web_sm"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--hf-home", required=True)
    parser.add_argument("--manifest-out", required=True)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def directory_manifest(root: Path) -> dict[str, object]:
    files: list[dict[str, object]] = []
    if root.exists():
        for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
            relative = path.relative_to(root).as_posix()
            files.append(
                {
                    "path": relative,
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )

    canonical_rows = json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "fileCount": len(files),
        "bytes": sum(int(row["bytes"]) for row in files),
        "manifestSha256": hashlib.sha256(canonical_rows).hexdigest(),
    }


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def main() -> int:
    args = parse_args()
    model_dir = Path(args.model_dir).resolve()
    hf_home = Path(args.hf_home).resolve()
    manifest_out = Path(args.manifest_out).resolve()
    model_dir.mkdir(parents=True, exist_ok=True)
    hf_home.mkdir(parents=True, exist_ok=True)
    manifest_out.parent.mkdir(parents=True, exist_ok=True)

    booknlp_artifacts = []
    for name in BOOKNLP_MODEL_FILES:
        target = model_dir / name
        url = f"{BOOKNLP_MODEL_BASE_URL}/{name}"
        if not target.is_file():
            partial = target.with_suffix(target.suffix + ".partial")
            partial.unlink(missing_ok=True)
            urllib.request.urlretrieve(url, partial)
            partial.replace(target)
        booknlp_artifacts.append(
            {
                "name": name,
                "sourceUrl": url,
                "bytes": target.stat().st_size,
                "sha256": sha256_file(target),
            }
        )

    # The pinned BookNLP implementation constructs these BERT bases through
    # transformers.from_pretrained(). Populate the exact cache before the real
    # runner is placed into HF/Transformers offline mode.
    os.environ["HF_HOME"] = str(hf_home)
    os.environ.pop("HF_HUB_OFFLINE", None)
    os.environ.pop("TRANSFORMERS_OFFLINE", None)

    from transformers import BertModel, BertTokenizer

    transformer_models = []
    for model_id in TRANSFORMER_MODEL_IDS:
        tokenizer = BertTokenizer.from_pretrained(
            model_id,
            do_lower_case=False,
            do_basic_tokenize=False,
            cache_dir=str(hf_home),
        )
        model = BertModel.from_pretrained(model_id, cache_dir=str(hf_home))
        transformer_models.append(
            {
                "modelId": model_id,
                "tokenizerClass": type(tokenizer).__name__,
                "modelClass": type(model).__name__,
            }
        )
        del tokenizer
        del model
        gc.collect()

    import spacy

    spacy_pipeline = spacy.load(SPACY_MODEL, disable=["ner"])
    del spacy_pipeline
    gc.collect()

    booknlp_total = sum(int(row["bytes"]) for row in booknlp_artifacts)
    hf_cache = directory_manifest(hf_home)
    spacy_path = Path(spacy.util.get_package_path(SPACY_MODEL)).resolve()
    spacy_cache = directory_manifest(spacy_path)

    manifest = {
        "schemaVersion": "saga-booknlp-runtime-manifest-v1",
        "model": "small",
        "packages": {
            "booknlp": package_version("booknlp"),
            "spacy": package_version("spacy"),
            "spacyModel": package_version(SPACY_MODEL),
            "torch": package_version("torch"),
            "transformers": package_version("transformers"),
        },
        "booknlpArtifacts": booknlp_artifacts,
        "booknlpArtifactBytes": booknlp_total,
        "transformerModels": transformer_models,
        "transformerCache": hf_cache,
        "spacyModel": {
            "name": SPACY_MODEL,
            "fileCount": spacy_cache["fileCount"],
            "bytes": spacy_cache["bytes"],
            "manifestSha256": spacy_cache["manifestSha256"],
        },
        "totalPreparedArtifactBytes": booknlp_total + int(hf_cache["bytes"]) + int(spacy_cache["bytes"]),
    }
    manifest_out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
