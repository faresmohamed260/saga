"""Diagnose and acquire protected S.A.G.A. assets from Cloudflare R2.

The script never prints credentials, bucket names, account IDs, object listings, or
protected bytes. It uses the repository manifest as the only source of object keys
and downloads selected objects into a caller-provided temporary directory.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

SUPPORTED_JURISDICTIONS = {"default", "eu", "us", "fedramp"}


def resolve_r2_endpoint(account_id: str, jurisdiction: str) -> str:
    account_id = str(account_id or "").strip()
    jurisdiction = str(jurisdiction or "default").strip().lower()
    if not account_id:
        raise ValueError("R2_ACCOUNT_ID is required")
    if jurisdiction not in SUPPORTED_JURISDICTIONS:
        raise ValueError(
            "unsupported R2 jurisdiction; expected default, eu, us, or fedramp"
        )
    suffix = "" if jurisdiction == "default" else f".{jurisdiction}"
    return f"https://{account_id}{suffix}.r2.cloudflarestorage.com"


def select_manifest_assets(
    manifest: Mapping[str, Any], requested_asset_id: str
) -> list[dict[str, Any]]:
    requested = str(requested_asset_id or "").strip()
    assets = [dict(asset) for asset in manifest.get("assets", [])]
    if requested == "all":
        if not assets:
            raise ValueError("protected asset manifest is empty")
        return assets
    selected = [asset for asset in assets if str(asset.get("id") or "") == requested]
    if not selected:
        raise ValueError(f"unknown protected asset id: {requested or '<empty>'}")
    return selected


def exact_object_visible(listing: Mapping[str, Any], object_key: str) -> bool:
    expected = str(object_key)
    return any(
        str(item.get("Key") or "") == expected
        for item in listing.get("Contents", []) or []
        if isinstance(item, Mapping)
    )


def _run_aws(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["aws", *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("protected asset manifest must contain a JSON object")
    return payload


def acquire_assets(
    *,
    manifest: Mapping[str, Any],
    requested_asset_id: str,
    destination: Path,
    account_id: str,
    bucket_name: str,
    jurisdiction: str,
) -> int:
    endpoint = resolve_r2_endpoint(account_id, jurisdiction)
    bucket_name = str(bucket_name or "").strip()
    if not bucket_name:
        raise ValueError("R2_BUCKET_NAME is required")

    assets = select_manifest_assets(manifest, requested_asset_id)
    destination.mkdir(parents=True, exist_ok=True)

    for asset in assets:
        object_key = str(asset.get("object_key") or "").strip()
        filename = str(asset.get("filename") or "").strip()
        asset_id = str(asset.get("id") or "").strip()
        if not object_key or not filename:
            raise ValueError(f"protected asset manifest entry is incomplete: {asset_id}")

        listed = _run_aws(
            [
                "s3api",
                "list-objects-v2",
                "--bucket",
                bucket_name,
                "--prefix",
                object_key,
                "--max-keys",
                "16",
                "--endpoint-url",
                endpoint,
                "--output",
                "json",
            ]
        )
        if listed.returncode != 0:
            print(
                "R2_DIAGNOSTIC=access_failed: unable to list the protected-asset "
                "prefix. Verify account ID, bucket name, jurisdiction, token bucket "
                "scope, and Object Read permission.",
                file=sys.stderr,
            )
            return 20

        try:
            listing = json.loads(listed.stdout or "{}")
        except json.JSONDecodeError:
            print(
                "R2_DIAGNOSTIC=list_parse_failed: R2 returned an unreadable listing response.",
                file=sys.stderr,
            )
            return 23

        if not isinstance(listing, dict) or not exact_object_visible(listing, object_key):
            print(
                f"R2_DIAGNOSTIC=object_missing: manifest asset '{asset_id}' is not "
                "present at its configured private object key. Migrate/upload the "
                "protected bytes before qualification.",
                file=sys.stderr,
            )
            return 21

        target = destination / filename
        downloaded = _run_aws(
            [
                "s3",
                "cp",
                f"s3://{bucket_name}/{object_key}",
                str(target),
                "--endpoint-url",
                endpoint,
                "--no-progress",
            ]
        )
        if downloaded.returncode != 0:
            print(
                f"R2_DIAGNOSTIC=download_failed: manifest asset '{asset_id}' was "
                "visible in the bucket listing but GetObject/download failed. Verify "
                "object read permission and availability.",
                file=sys.stderr,
            )
            return 22

        print(json.dumps({"asset_id": asset_id, "status": "downloaded"}))

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", default="docs/operations/protected_assets.manifest.json"
    )
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--asset-dir", required=True)
    parser.add_argument(
        "--jurisdiction",
        default="default",
        choices=sorted(SUPPORTED_JURISDICTIONS),
    )
    args = parser.parse_args()

    account_id = os.environ.get("R2_ACCOUNT_ID", "")
    bucket_name = os.environ.get("R2_BUCKET_NAME", "")
    manifest = _load_manifest(Path(args.manifest))
    try:
        return acquire_assets(
            manifest=manifest,
            requested_asset_id=args.asset_id,
            destination=Path(args.asset_dir),
            account_id=account_id,
            bucket_name=bucket_name,
            jurisdiction=args.jurisdiction,
        )
    except ValueError as exc:
        print(f"R2_DIAGNOSTIC=configuration_error: {exc}", file=sys.stderr)
        return 10


if __name__ == "__main__":
    raise SystemExit(main())
