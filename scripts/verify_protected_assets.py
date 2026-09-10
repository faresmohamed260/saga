"""Verify protected validation assets against the repository manifest.

The script intentionally verifies local files only. CI workflows are responsible for
downloading protected bytes into a temporary directory and deleting them afterward.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify protected asset hashes.")
    parser.add_argument("--manifest", default="docs/operations/protected_assets.manifest.json")
    parser.add_argument("--asset-dir", required=True)
    parser.add_argument("--asset-id", action="append", default=[])
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    asset_dir = Path(args.asset_dir)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    requested = set(args.asset_id or [])
    assets = manifest.get("assets", [])
    if requested:
        assets = [asset for asset in assets if asset.get("id") in requested]
        missing_ids = requested.difference(str(asset.get("id")) for asset in assets)
        if missing_ids:
            raise SystemExit(f"unknown protected asset ids: {', '.join(sorted(missing_ids))}")

    if not assets:
        raise SystemExit("no protected assets selected")

    verified: list[dict[str, str | int]] = []
    for asset in assets:
        filename = str(asset["filename"])
        expected = str(asset["sha256"]).upper()
        path = asset_dir / filename
        if not path.is_file():
            raise SystemExit(f"missing protected asset: {filename}")
        actual = _sha256(path)
        if actual != expected:
            raise SystemExit(f"hash mismatch for protected asset {filename}")
        verified.append({"id": str(asset["id"]), "filename": filename, "bytes": path.stat().st_size})

    print(json.dumps({"verified": verified}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
