"""Immutable release-candidate bundle construction."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from packages.deployment_runtime.contracts import ReleaseCandidateBundle
from packages.deployment_runtime.gates import (
    CANARY_REQUIRED_GATES,
    PRODUCTION_REQUIRED_GATES,
)
from packages.deployment_runtime.release import create_release_manifest


def create_release_candidate(
    *,
    version: str,
    git_sha: str,
    runtime_digest: str,
    dashboard_digest: str,
    source_state: str = "clean",
    configuration: dict[str, Any] | None = None,
    created_at_ms: int | None = None,
) -> ReleaseCandidateBundle:
    if source_state != "clean":
        raise ValueError("Release candidates must be created from a clean committed source state.")
    timestamp = int(created_at_ms or time.time() * 1000)
    manifest = create_release_manifest(
        version=version,
        git_sha=git_sha,
        image_digest=runtime_digest,
        components={"runtime": runtime_digest, "dashboard": dashboard_digest},
        configuration=configuration,
        source_state="clean",
        built_at_ms=timestamp,
    )
    payload = {
        "format": "saga-release-candidate-v1",
        "created_at_ms": timestamp,
        "manifest": manifest.model_dump(),
        "canary_required_gates": list(CANARY_REQUIRED_GATES),
        "production_required_gates": list(PRODUCTION_REQUIRED_GATES),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return ReleaseCandidateBundle(candidate_sha256=digest, **payload)


def verify_release_candidate(candidate: ReleaseCandidateBundle | dict[str, Any]) -> ReleaseCandidateBundle:
    bundle = candidate if isinstance(candidate, ReleaseCandidateBundle) else ReleaseCandidateBundle.model_validate(candidate)
    payload = bundle.model_dump(exclude={"candidate_sha256"})
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    if digest != bundle.candidate_sha256:
        raise ValueError("Release candidate integrity check failed.")
    if bundle.manifest.source_state != "clean":
        raise ValueError("Release candidate source state must be clean.")
    if set(bundle.manifest.components) != {"runtime", "dashboard"}:
        raise ValueError("Release candidate must contain exactly runtime and dashboard images.")
    if bundle.manifest.image_digest != bundle.manifest.components["runtime"]:
        raise ValueError("Release candidate primary image must match the runtime component.")
    return bundle
