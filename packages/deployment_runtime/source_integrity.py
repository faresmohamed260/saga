"""Bounded source-tree credential detection for release gates."""

from __future__ import annotations

import re
from pathlib import Path

SECRET_PATTERNS = {
    "hugging_face_token": re.compile(rb"hf_[A-Za-z0-9]{20,}"),
    "openai_style_key": re.compile(rb"sk-[A-Za-z0-9_-]{20,}"),
    "google_api_key": re.compile(rb"AIza[0-9A-Za-z_-]{30,}"),
    "supabase_secret": re.compile(rb"sb_secret_[A-Za-z0-9_-]{20,}"),
    "private_key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}
MAX_SCANNED_FILE_BYTES = 5 * 1024 * 1024


def scan_source_files(root: str | Path, relative_paths: list[str]) -> list[dict[str, object]]:
    base = Path(root).resolve()
    findings: list[dict[str, object]] = []
    for relative in sorted(set(relative_paths)):
        path = (base / relative).resolve()
        if not path.is_relative_to(base) or not path.is_file() or path.stat().st_size > MAX_SCANNED_FILE_BYTES:
            continue
        data = path.read_bytes()
        if b"\x00" in data[:4096]:
            continue
        for name, pattern in SECRET_PATTERNS.items():
            for match in pattern.finditer(data):
                findings.append({
                    "path": path.relative_to(base).as_posix(),
                    "line": data.count(b"\n", 0, match.start()) + 1,
                    "kind": name,
                })
    return findings
