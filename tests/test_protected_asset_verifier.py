from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


def test_protected_asset_verifier_accepts_matching_hash(tmp_path: Path) -> None:
    asset_dir = tmp_path / "assets"
    asset_dir.mkdir()
    asset = asset_dir / "sample.epub"
    asset.write_bytes(b"sample protected fixture bytes")

    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "version": 1,
                "assets": [
                    {
                        "id": "sample",
                        "filename": asset.name,
                        "sha256": hashlib.sha256(asset.read_bytes()).hexdigest().upper(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/verify_protected_assets.py",
            "--manifest",
            str(manifest),
            "--asset-dir",
            str(asset_dir),
            "--asset-id",
            "sample",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "sample.epub" in result.stdout


def test_protected_asset_verifier_rejects_mismatched_hash(tmp_path: Path) -> None:
    asset_dir = tmp_path / "assets"
    asset_dir.mkdir()
    (asset_dir / "sample.epub").write_bytes(b"changed bytes")

    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "version": 1,
                "assets": [
                    {
                        "id": "sample",
                        "filename": "sample.epub",
                        "sha256": "0" * 64,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/verify_protected_assets.py",
            "--manifest",
            str(manifest),
            "--asset-dir",
            str(asset_dir),
            "--asset-id",
            "sample",
        ],
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "hash mismatch" in result.stderr
