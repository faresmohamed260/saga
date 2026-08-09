"""Scan tracked release source without printing credential values."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from packages.deployment_runtime.source_integrity import scan_source_files


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True,
    )
    paths = [item.decode("utf-8") for item in completed.stdout.split(b"\0") if item]
    findings = scan_source_files(root, paths)
    print(json.dumps({"ready": not findings, "files_scanned": len(paths), "findings": findings}, indent=2))
    return 0 if not findings else 2


if __name__ == "__main__":
    raise SystemExit(main())
