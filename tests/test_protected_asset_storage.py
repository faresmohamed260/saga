from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import check_protected_asset_storage as storage


def test_resolve_r2_endpoint_default() -> None:
    assert (
        storage.resolve_r2_endpoint("abc123", "default")
        == "https://abc123.r2.cloudflarestorage.com"
    )


@pytest.mark.parametrize("jurisdiction", ["eu", "us", "fedramp"])
def test_resolve_r2_endpoint_jurisdiction(jurisdiction: str) -> None:
    assert storage.resolve_r2_endpoint("abc123", jurisdiction) == (
        f"https://abc123.{jurisdiction}.r2.cloudflarestorage.com"
    )


def test_resolve_r2_endpoint_rejects_unknown_jurisdiction() -> None:
    with pytest.raises(ValueError, match="unsupported R2 jurisdiction"):
        storage.resolve_r2_endpoint("abc123", "moon")


def test_select_manifest_assets_one_and_all() -> None:
    manifest = {
        "assets": [
            {"id": "one", "object_key": "protected/one.epub", "filename": "one.epub"},
            {"id": "two", "object_key": "protected/two.epub", "filename": "two.epub"},
        ]
    }
    assert [item["id"] for item in storage.select_manifest_assets(manifest, "one")] == [
        "one"
    ]
    assert [item["id"] for item in storage.select_manifest_assets(manifest, "all")] == [
        "one",
        "two",
    ]


def test_select_manifest_assets_rejects_unknown_id() -> None:
    with pytest.raises(ValueError, match="unknown protected asset id"):
        storage.select_manifest_assets({"assets": []}, "missing")


def test_exact_object_visible_requires_exact_key() -> None:
    listing = {
        "Contents": [
            {"Key": "protected/saga/book.epub.bak"},
            {"Key": "protected/saga/book.epub"},
        ]
    }
    assert storage.exact_object_visible(listing, "protected/saga/book.epub") is True
    assert storage.exact_object_visible(listing, "protected/saga/other.epub") is False


def test_acquire_assets_classifies_missing_object(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    manifest = {
        "assets": [
            {
                "id": "book",
                "object_key": "protected/saga/book.epub",
                "filename": "book.epub",
            }
        ]
    }

    def fake_run(args: list[str]):
        assert args[:2] == ["s3api", "list-objects-v2"]
        return storage.subprocess.CompletedProcess(
            args=["aws", *args],
            returncode=0,
            stdout=json.dumps({"Contents": []}),
            stderr="",
        )

    monkeypatch.setattr(storage, "_run_aws", fake_run)
    assert (
        storage.acquire_assets(
            manifest=manifest,
            requested_asset_id="book",
            destination=tmp_path,
            account_id="abc123",
            bucket_name="private-bucket",
            jurisdiction="default",
        )
        == 21
    )


def test_acquire_assets_downloads_visible_object(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    object_key = "protected/saga/book.epub"
    manifest = {
        "assets": [
            {"id": "book", "object_key": object_key, "filename": "book.epub"}
        ]
    }
    calls: list[list[str]] = []

    def fake_run(args: list[str]):
        calls.append(args)
        if args[0] == "s3api":
            return storage.subprocess.CompletedProcess(
                args=["aws", *args],
                returncode=0,
                stdout=json.dumps({"Contents": [{"Key": object_key}]}),
                stderr="",
            )
        target = Path(args[3])
        target.write_bytes(b"protected-test-bytes")
        return storage.subprocess.CompletedProcess(
            args=["aws", *args], returncode=0, stdout="", stderr=""
        )

    monkeypatch.setattr(storage, "_run_aws", fake_run)
    assert (
        storage.acquire_assets(
            manifest=manifest,
            requested_asset_id="book",
            destination=tmp_path,
            account_id="abc123",
            bucket_name="private-bucket",
            jurisdiction="default",
        )
        == 0
    )
    assert (tmp_path / "book.epub").read_bytes() == b"protected-test-bytes"
    assert [call[0] for call in calls] == ["s3api", "s3"]
