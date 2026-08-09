"""Deterministic canonicalization and secret-safe hashing."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any


_SECRET_FRAGMENTS = ("token", "secret", "password", "authorization", "api_key", "apikey", "credential")


def sanitize(value: Any, *, key: str = "") -> Any:
    if key and any(fragment in key.lower() for fragment in _SECRET_FRAGMENTS):
        return "<redacted>"
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, dict):
        return {str(item_key): sanitize(item, key=str(item_key)) for item_key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if isinstance(value, set):
        return sorted((sanitize(item) for item in value), key=lambda item: canonical_json(item))
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Lineage payloads cannot contain non-finite floats.")
        return value
    if value is None or isinstance(value, (str, int, bool)):
        return value
    return str(value)


def canonical_json(value: Any) -> str:
    return json.dumps(sanitize(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
