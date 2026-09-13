#!/usr/bin/env python3
"""Persistent pinned BookNLP-small runner for S.A.G.A. Phase 3B experiments.

The process loads BookNLP once, then handles sequential NDJSON requests over
stdin/stdout. It contains no installation/download logic and exposes no network
listener. Provider-neutral evidence normalization remains owned by TypeScript.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.metadata
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

EXPECTED_PACKAGE_VERSION = "1.0.7"
MODEL = "small"
PIPELINE = "entity,quote,event,coref"
PROTOCOL_VERSION = "saga-booknlp-persistent-runner-v1"
REQUEST_SCHEMA_VERSION = "saga-booknlp-persistent-request-v1"
RESPONSE_SCHEMA_VERSION = "saga-booknlp-persistent-response-v1"
BOOK_ID = "saga"
REQUIRED_MODEL_FILES = (
    "entities_google_bert_uncased_L-4_H-256_A-4-v1.0.model",
    "coref_google_bert_uncased_L-2_H-256_A-4-v1.0.model",
    "speaker_google_bert_uncased_L-8_H-256_A-4-v1.0.1.model",
)


def booknlp_version() -> str:
    return importlib.metadata.version("booknlp")


def validate_model_path(model_path: Path) -> None:
    if not model_path.is_dir():
        raise RuntimeError("booknlp_model_directory_missing")
    missing = [name for name in REQUIRED_MODEL_FILES if not (model_path / name).is_file()]
    if missing:
        raise RuntimeError("booknlp_model_directory_incomplete")


def load_runtime(model_path: Path):
    validate_model_path(model_path)
    version = booknlp_version()
    if version != EXPECTED_PACKAGE_VERSION:
        raise RuntimeError("booknlp_runner_version_mismatch")

    # Keep stdout reserved for one machine-readable JSON response per line.
    with contextlib.redirect_stdout(sys.stderr):
        from booknlp.booknlp import BookNLP

        runtime = BookNLP(
            "en",
            {
                "pipeline": PIPELINE,
                "model": MODEL,
                "model_path": str(model_path),
            },
        )
    return runtime, version


def response(request_id: str, configuration_fingerprint: str, kind: str, **fields: Any) -> dict[str, Any]:
    return {
        "schemaVersion": RESPONSE_SCHEMA_VERSION,
        "protocolVersion": PROTOCOL_VERSION,
        "requestId": request_id,
        "configurationFingerprint": configuration_fingerprint,
        "kind": kind,
        **fields,
    }


def error_response(
    request_id: str,
    configuration_fingerprint: str,
    code: str,
    retryable: bool = False,
) -> dict[str, Any]:
    return response(
        request_id,
        configuration_fingerprint,
        "error",
        error={"code": code, "retryable": retryable},
    )


def write_response(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n")
    sys.stdout.flush()


def require_request(value: Any, expected_configuration_fingerprint: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("booknlp_persistent_invalid_request")
    if value.get("schemaVersion") != REQUEST_SCHEMA_VERSION:
        raise ValueError("booknlp_persistent_invalid_request")
    if value.get("protocolVersion") != PROTOCOL_VERSION:
        raise ValueError("booknlp_persistent_protocol_mismatch")
    request_id = value.get("requestId")
    if not isinstance(request_id, str) or not request_id:
        raise ValueError("booknlp_persistent_invalid_request_id")
    configuration_fingerprint = value.get("configurationFingerprint")
    if configuration_fingerprint != expected_configuration_fingerprint:
        raise ValueError("booknlp_persistent_configuration_fingerprint_mismatch")
    if value.get("kind") not in {"health", "analyze", "shutdown"}:
        raise ValueError("booknlp_persistent_invalid_request_kind")
    return value


def analyze(runtime: Any, request: dict[str, Any], version: str, configuration_fingerprint: str) -> dict[str, Any]:
    normalized_input_fingerprint = request.get("normalizedInputFingerprint")
    normalized_text = request.get("normalizedText")
    if (
        not isinstance(normalized_input_fingerprint, str)
        or len(normalized_input_fingerprint) != 64
        or not isinstance(normalized_text, str)
    ):
        return error_response(
            request["requestId"],
            configuration_fingerprint,
            "booknlp_persistent_invalid_analyze_request",
        )

    workspace = Path(tempfile.mkdtemp(prefix="saga-booknlp-persistent-"))
    input_path = workspace / "input.txt"
    output_dir = workspace / "output"
    try:
        input_path.write_text(normalized_text, encoding="utf-8")
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            with contextlib.redirect_stdout(sys.stderr):
                runtime.process(str(input_path), str(output_dir), BOOK_ID)
        except Exception as exc:  # provider failure should stay explicit and bounded by caller
            print(f"BookNLP persistent analysis failed: {type(exc).__name__}", file=sys.stderr)
            return error_response(
                request["requestId"],
                configuration_fingerprint,
                "booknlp_persistent_analysis_failed",
                True,
            )

        paths = {
            "tokensTsv": output_dir / f"{BOOK_ID}.tokens",
            "entitiesTsv": output_dir / f"{BOOK_ID}.entities",
            "quotesTsv": output_dir / f"{BOOK_ID}.quotes",
        }
        if any(not path.is_file() for path in paths.values()):
            return error_response(
                request["requestId"],
                configuration_fingerprint,
                "booknlp_persistent_missing_outputs",
            )

        return response(
            request["requestId"],
            configuration_fingerprint,
            "analyze",
            booknlpVersion=version,
            normalizedInputFingerprint=normalized_input_fingerprint,
            tokensTsv=paths["tokensTsv"].read_text(encoding="utf-8"),
            entitiesTsv=paths["entitiesTsv"].read_text(encoding="utf-8"),
            quotesTsv=paths["quotesTsv"].read_text(encoding="utf-8"),
        )
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--configuration-fingerprint", required=True)
    args = parser.parse_args()
    if len(args.configuration_fingerprint) != 64:
        parser.error("--configuration-fingerprint must be 64 characters")
    return args


def main() -> int:
    args = parse_args()
    configuration_fingerprint = args.configuration_fingerprint
    try:
        runtime, version = load_runtime(Path(args.model_path))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2

    for raw_line in sys.stdin:
        line = raw_line.rstrip("\r\n")
        if not line:
            write_response(error_response("invalid", configuration_fingerprint, "booknlp_persistent_invalid_json"))
            continue

        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            write_response(error_response("invalid", configuration_fingerprint, "booknlp_persistent_invalid_json"))
            continue

        request_id = parsed.get("requestId") if isinstance(parsed, dict) else None
        if not isinstance(request_id, str) or not request_id:
            request_id = "invalid"

        try:
            request = require_request(parsed, configuration_fingerprint)
        except ValueError as exc:
            write_response(error_response(request_id, configuration_fingerprint, str(exc)))
            continue

        kind = request["kind"]
        if kind == "health":
            write_response(
                response(
                    request["requestId"],
                    configuration_fingerprint,
                    "health",
                    status="ok",
                    booknlpVersion=version,
                )
            )
            continue

        if kind == "shutdown":
            write_response(
                response(
                    request["requestId"],
                    configuration_fingerprint,
                    "shutdown",
                    status="ok",
                    booknlpVersion=version,
                )
            )
            return 0

        write_response(analyze(runtime, request, version, configuration_fingerprint))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
