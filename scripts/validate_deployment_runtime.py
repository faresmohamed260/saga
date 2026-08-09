"""Bounded PostgreSQL validation for release integrity and deployment readiness."""

from __future__ import annotations

import argparse
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from packages.deployment_runtime import ReleaseRuntime, check_readiness, create_deployment_persistence_client, create_release_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", default=f"validation-{int(time.time())}")
    args = parser.parse_args()
    persistence = create_deployment_persistence_client()
    runtime = ReleaseRuntime(store=persistence.deployments)
    releases = []
    for index in range(2):
        manifest = create_release_manifest(
            version=f"{args.prefix}.{index}",
            git_sha=f"{index + 1:07x}validation",
            image_digest=f"sha256:{index + 1:064x}",
        )
        runtime.register(manifest)
        runtime.transition(manifest.release_id, "staging")
        releases.append(manifest.release_id)

    barrier = threading.Barrier(2)

    def promote(release_id: str) -> str:
        barrier.wait(timeout=10)
        return str(runtime.transition(release_id, "production")["status"])

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(promote, releases))
    production = persistence.deployments.list_releases(status="production", limit=100)
    selected = [item for item in production if item["release_id"] in releases]
    readiness = check_readiness(persistence=persistence, service="deployment-validation")
    result = {
        "ready": readiness.ready and statuses == ["production", "production"] and len(selected) == 1,
        "schema_revision": readiness.schema_revision,
        "promotion_results": statuses,
        "validation_production_count": len(selected),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
