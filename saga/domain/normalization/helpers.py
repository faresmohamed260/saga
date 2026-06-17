"""Shared normalization helpers for core artifact building."""

from __future__ import annotations

from typing import Iterable, List


def normalize_key(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def stable_slug(prefix: str, value: str) -> str:
    normalized = normalize_key(value).replace(" ", "_").replace("-", "_")
    return f"{prefix}_{normalized}" if normalized else f"{prefix}_unknown"


def stable_pair_slug(prefix: str, first: str, second: str) -> str:
    ordered = sorted([normalize_key(first), normalize_key(second)])
    return f"{prefix}_{ordered[0].replace(' ', '_')}_{ordered[1].replace(' ', '_')}"


def dedupe_strings(values: Iterable[str]) -> List[str]:
    output: List[str] = []
    seen = set()
    for value in values:
        cleaned = str(value or "").strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        output.append(cleaned)
    return output
