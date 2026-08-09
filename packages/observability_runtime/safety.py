"""Low-cardinality and secret-safe observation normalization."""

from __future__ import annotations

from typing import Any


SECRET_FRAGMENTS = ("token", "secret", "password", "authorization", "api_key", "apikey", "credential", "cookie")
ALLOWED_DIMENSIONS = frozenset({"attempt", "execution_mode", "queue_name", "retryable", "severity", "model", "outcome"})


def sanitize(value: Any, *, key: str = "", depth: int = 0) -> Any:
    if key and any(fragment in key.lower() for fragment in SECRET_FRAGMENTS):
        return "<redacted>"
    if depth >= 8:
        return "<truncated>"
    if isinstance(value, dict):
        return {str(k)[:120]: sanitize(v, key=str(k), depth=depth + 1) for k, v in list(value.items())[:100]}
    if isinstance(value, (list, tuple)):
        return [sanitize(item, depth=depth + 1) for item in list(value)[:100]]
    if isinstance(value, str):
        return value[:2000]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:2000]


def bounded_dimensions(dimensions: dict[str, Any] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in dict(dimensions or {}).items():
        normalized_key = str(key).strip().lower()
        if normalized_key not in ALLOWED_DIMENSIONS or len(result) >= 8:
            continue
        result[normalized_key] = str(sanitize(value, key=normalized_key))[:120]
    return result
