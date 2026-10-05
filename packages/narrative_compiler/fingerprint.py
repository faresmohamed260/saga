"""Deterministic fingerprints for compiler configuration and artifacts."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
import hashlib
import json
from typing import Any, Mapping, Sequence


def _canonicalize(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        # Avoid dataclasses.asdict(): it deep-copies values and cannot safely
        # traverse immutable MappingProxyType fields used by Narrative IR.
        return {field.name: _canonicalize(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _canonicalize(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    if isinstance(value, set):
        canonical_items = [_canonicalize(item) for item in value]
        return sorted(canonical_items, key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported fingerprint value: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    """Return a stable JSON representation suitable for hashing."""

    return json.dumps(
        _canonicalize(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def config_fingerprint(config: Mapping[str, Any]) -> str:
    return sha256_text(canonical_json(config))


def stable_id(namespace: str, *parts: Any, prefix: str | None = None) -> str:
    payload = {"namespace": namespace, "parts": parts}
    digest = sha256_text(canonical_json(payload))
    return f"{prefix}:{digest}" if prefix else digest


def artifact_fingerprint(
    *,
    source_fingerprint: str,
    stage_name: str,
    stage_version: str,
    config: Mapping[str, Any],
    upstream_fingerprints: Sequence[str] = (),
    model: Mapping[str, Any] | None = None,
) -> str:
    """Bind a compiler artifact to every input that can change its semantics."""

    if not source_fingerprint:
        raise ValueError("source_fingerprint is required")
    if not stage_name or not stage_version:
        raise ValueError("stage_name and stage_version are required")

    payload = {
        "source_fingerprint": source_fingerprint,
        "stage": {"name": stage_name, "version": stage_version},
        "config_fingerprint": config_fingerprint(config),
        "upstream_fingerprints": sorted(upstream_fingerprints),
        "model": model,
    }
    return sha256_text(canonical_json(payload))
