"""Resolve chapter-level POV anchors from deterministic chapter metadata."""

from __future__ import annotations

import re
from typing import Dict


CHAPTER_POV_PATTERN = re.compile(r"^chapter\s+\d+\s*:\s*(.+)$", re.IGNORECASE)


def resolve_pov_anchor(scene: Dict) -> str:
    """Return a likely POV anchor name from the chapter title, if present."""
    chapter_title = (scene.get("chapter_title") or "").strip()
    if not chapter_title:
        return ""
    match = CHAPTER_POV_PATTERN.match(chapter_title)
    if not match:
        return ""
    candidate = match.group(1).strip()
    if not candidate:
        return ""
    if any(ch.isdigit() for ch in candidate):
        return ""
    return candidate
