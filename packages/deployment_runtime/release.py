"""Immutable release identity and controlled status transitions."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from packages.deployment_runtime.contracts import ReleaseManifest
from packages.persistence_runtime import EXPECTED_SCHEMA_REVISION


ALLOWED_TRANSITIONS = {
    "candidate": {"staging", "failed"},
    "staging": {"production", "failed", "rolled_back"},
    "production": {"rolled_back"},
    "failed": set(),
    "rolled_back": set(),
}


def create_release_manifest(*, version: str, git_sha: str, image_digest: str = "", components: dict[str, str] | None = None, configuration: dict[str, Any] | None = None, built_at_ms: int | None = None) -> ReleaseManifest:
    normalized_version = str(version or "").strip()
    normalized_sha = str(git_sha or "").strip().lower()
    if not normalized_version or len(normalized_sha) < 7:
        raise ValueError("version and a git SHA of at least seven characters are required.")
    safe_configuration = {str(key): str(value) for key, value in sorted(dict(configuration or {}).items()) if not _secret_key(str(key))}
    fingerprint = hashlib.sha256(json.dumps(safe_configuration, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    timestamp = int(built_at_ms or time.time() * 1000)
    release_id = f"release-{normalized_version}-{normalized_sha[:12]}"
    return ReleaseManifest(release_id=release_id, version=normalized_version, git_sha=normalized_sha, image_digest=str(image_digest or ""), schema_revision=EXPECTED_SCHEMA_REVISION, built_at_ms=timestamp, configuration_fingerprint=fingerprint, components=dict(components or {}))


class ReleaseRuntime:
    def __init__(self, *, store) -> None:
        self.store = store

    def register(self, manifest: ReleaseManifest) -> dict[str, Any]:
        return self.store.record_release({
            "release_id": manifest.release_id, "version": manifest.version, "git_sha": manifest.git_sha,
            "image_digest": manifest.image_digest, "status": manifest.status,
            "manifest": manifest.model_dump(),
        })

    def transition(self, release_id: str, status: str) -> dict[str, Any]:
        current = self.store.get_release(release_id)
        if current is None:
            raise ValueError(f"Unknown release '{release_id}'.")
        if status not in ALLOWED_TRANSITIONS.get(str(current["status"]), set()):
            raise ValueError(f"Invalid release transition {current['status']} -> {status}.")
        if status == "production":
            return self.store.promote_release(release_id, expected_status=str(current["status"]))
        updated = self.store.set_release_status(release_id, status=status)
        if updated is None:
            raise RuntimeError("Release disappeared during transition.")
        return updated


def _secret_key(key: str) -> bool:
    folded = key.lower()
    return any(fragment in folded for fragment in ("token", "secret", "password", "credential", "api_key", "apikey", "authorization"))
