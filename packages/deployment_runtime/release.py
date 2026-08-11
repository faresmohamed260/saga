"""Immutable release identity and controlled status transitions."""

from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any

from packages.deployment_runtime.contracts import ReleaseManifest
from packages.deployment_runtime.gates import ReleaseGateRuntime
from packages.schema_revision import EXPECTED_SCHEMA_REVISION


ALLOWED_TRANSITIONS = {
    "candidate": {"staging", "failed"},
    "staging": {"canary", "failed", "rolled_back"},
    "canary": {"production", "failed", "rolled_back"},
    "production": {"rolled_back"},
    "failed": set(),
    "rolled_back": set(),
}

SEMVER_PATTERN = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$")
GIT_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
IMAGE_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def create_release_manifest(*, version: str, git_sha: str, image_digest: str = "", source_state: str = "clean", components: dict[str, str] | None = None, configuration: dict[str, Any] | None = None, built_at_ms: int | None = None) -> ReleaseManifest:
    normalized_version = str(version or "").strip()
    normalized_sha = str(git_sha or "").strip().lower()
    normalized_digest = str(image_digest or "").strip().lower()
    normalized_source_state = str(source_state or "").strip().lower()
    normalized_components = {str(key).strip(): str(value).strip().lower() for key, value in dict(components or {}).items()}
    if not SEMVER_PATTERN.fullmatch(normalized_version):
        raise ValueError("version must be valid semantic versioning without a leading 'v'.")
    if not GIT_SHA_PATTERN.fullmatch(normalized_sha):
        raise ValueError("git_sha must be a full 40-character hexadecimal commit SHA.")
    if normalized_digest and not IMAGE_DIGEST_PATTERN.fullmatch(normalized_digest):
        raise ValueError("image_digest must be an immutable sha256 digest.")
    if normalized_source_state not in {"clean", "dirty"}:
        raise ValueError("source_state must be 'clean' or 'dirty'.")
    invalid_components = [name for name, digest in normalized_components.items() if not name or not IMAGE_DIGEST_PATTERN.fullmatch(digest)]
    if invalid_components:
        raise ValueError("component image values must be immutable sha256 digests.")
    safe_configuration = {str(key): str(value) for key, value in sorted(dict(configuration or {}).items()) if not _secret_key(str(key))}
    fingerprint = hashlib.sha256(json.dumps(safe_configuration, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    timestamp = int(built_at_ms or time.time() * 1000)
    release_id = f"release-{normalized_version}-{normalized_sha[:12]}"
    return ReleaseManifest(release_id=release_id, version=normalized_version, git_sha=normalized_sha, image_digest=normalized_digest, schema_revision=EXPECTED_SCHEMA_REVISION, built_at_ms=timestamp, configuration_fingerprint=fingerprint, source_state=normalized_source_state, components=normalized_components)


class ReleaseRuntime:
    def __init__(self, *, store) -> None:
        self.store = store
        self.gates = ReleaseGateRuntime(store=store)

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
        if status in {"canary", "production"}:
            self._assert_promotable(ReleaseManifest.model_validate(current.get("manifest") or {}))
            self.gates.assert_eligible(release_id=release_id, target=status)
        if status == "production":
            return self.store.promote_release(release_id, expected_status=str(current["status"]))
        updated = self.store.set_release_status(release_id, status=status)
        if updated is None:
            raise RuntimeError("Release disappeared during transition.")
        return updated

    @staticmethod
    def _assert_promotable(manifest: ReleaseManifest) -> None:
        if manifest.source_state != "clean":
            raise ValueError("Production promotion requires a clean committed source state.")
        if not GIT_SHA_PATTERN.fullmatch(manifest.git_sha):
            raise ValueError("Production promotion requires a full immutable Git SHA.")
        if not IMAGE_DIGEST_PATTERN.fullmatch(manifest.image_digest):
            raise ValueError("Production promotion requires an immutable primary image digest.")
        missing_components = sorted({"runtime", "dashboard"} - set(manifest.components))
        if missing_components:
            raise ValueError("Production promotion requires runtime and dashboard component image digests.")
        if any(not IMAGE_DIGEST_PATTERN.fullmatch(digest) for digest in manifest.components.values()):
            raise ValueError("Production promotion requires immutable component image digests.")


def _secret_key(key: str) -> bool:
    folded = key.lower()
    return any(fragment in folded for fragment in ("token", "secret", "password", "credential", "api_key", "apikey", "authorization"))
