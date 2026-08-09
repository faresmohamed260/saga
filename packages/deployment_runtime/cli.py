from __future__ import annotations

import argparse
import json
import os
import time

from packages.deployment_runtime.config import create_deployment_persistence_client
from packages.deployment_runtime.backup import ArtifactBackupRuntime, BackupRuntime
from packages.persistence_runtime.database_url import build_database_url_from_env
from packages.deployment_runtime.health import check_readiness
from packages.deployment_runtime.migrations import MigrationRuntime
from packages.deployment_runtime.release import ReleaseRuntime, create_release_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="S.A.G.A. production deployment control plane.")
    commands = parser.add_subparsers(dest="command", required=True)
    migrate = commands.add_parser("migrate")
    migrate.add_argument("action", choices=("upgrade", "downgrade", "current", "check", "adopt"))
    migrate.add_argument("--revision", default="head")
    health = commands.add_parser("health")
    health.add_argument("--service", default="deployment-runtime")
    process_health = commands.add_parser("process-health")
    process_health.add_argument("--role", required=True, choices=("worker", "scheduler", "observability"))
    process_health.add_argument("--max-age-seconds", type=int, default=60)
    release = commands.add_parser("release")
    release_commands = release.add_subparsers(dest="release_action", required=True)
    create = release_commands.add_parser("create")
    create.add_argument("--version", required=True)
    create.add_argument("--git-sha", required=True)
    create.add_argument("--image-digest", required=True)
    create.add_argument("--component-digest", action="append", default=[], metavar="NAME=SHA256")
    create.add_argument("--source-state", choices=("clean", "dirty"), default=str(os.getenv("SAGA_SOURCE_STATE") or "clean"))
    transition = release_commands.add_parser("transition")
    transition.add_argument("--release-id", required=True)
    transition.add_argument("--status", required=True, choices=("staging", "production", "rolled_back", "failed"))
    backup = commands.add_parser("backup")
    backup_commands = backup.add_subparsers(dest="backup_action", required=True)
    backup_create = backup_commands.add_parser("create")
    backup_create.add_argument("--output", required=True)
    backup_restore = backup_commands.add_parser("restore")
    backup_restore.add_argument("--input", required=True)
    backup_restore.add_argument("--confirm-target", required=True)
    artifacts = commands.add_parser("artifacts")
    artifact_commands = artifacts.add_subparsers(dest="artifact_action", required=True)
    artifact_create = artifact_commands.add_parser("create")
    artifact_create.add_argument("--output", required=True)
    artifact_create.add_argument("--buckets", required=True, help="Comma-separated configured bucket names.")
    artifact_restore = artifact_commands.add_parser("restore")
    artifact_restore.add_argument("--input", required=True)
    artifact_restore.add_argument("--confirm-target", required=True)
    args = parser.parse_args()

    if args.command == "migrate":
        runtime = MigrationRuntime()
        if args.action == "upgrade":
            runtime.upgrade(args.revision)
            payload = {"upgraded": True, "revision": args.revision}
        elif args.action == "downgrade":
            if args.revision == "head":
                raise ValueError("Downgrade requires an explicit target revision.")
            runtime.downgrade(args.revision)
            payload = {"downgraded": True, "revision": args.revision}
        elif args.action == "adopt":
            client = create_deployment_persistence_client(initialize=False)
            payload = runtime.adopt_existing(client.engine)
        else:
            client = create_deployment_persistence_client(initialize=False)
            payload = runtime.check(client.engine)
            if args.action == "current":
                payload = {"current": payload["current"], "head": payload["head"]}
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if payload.get("ready", True) else 2

    if args.command == "backup":
        database_url = build_database_url_from_env()
        if not database_url:
            raise RuntimeError("Backup requires the Supabase database environment.")
        backup_runtime = BackupRuntime(pg_dump=str(os.getenv("SAGA_PG_DUMP") or "pg_dump"), pg_restore=str(os.getenv("SAGA_PG_RESTORE") or "pg_restore"))
        payload = backup_runtime.create(database_url=database_url, output_path=args.output, release_id=str(os.getenv("SAGA_RELEASE_ID") or "")) if args.backup_action == "create" else backup_runtime.restore(database_url=database_url, backup_path=args.input, confirm_target=args.confirm_target)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    client = create_deployment_persistence_client()
    if args.command == "artifacts":
        runtime = ArtifactBackupRuntime(object_store=client.objects)
        if args.artifact_action == "create":
            payload = runtime.create(bucket_names=args.buckets.split(","), output_path=args.output, release_id=str(os.getenv("SAGA_RELEASE_ID") or ""))
        else:
            payload = runtime.restore(backup_path=args.input, confirm_target=args.confirm_target)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    if args.command == "process-health":
        since_ms = int(time.time() * 1000) - max(1, args.max_age_seconds) * 1000
        heartbeats = client.deployments.list_heartbeats(role=args.role, since_ms=since_ms, limit=100)
        ready = any(item.get("status") == "ready" for item in heartbeats)
        print(json.dumps({"ready": ready, "role": args.role, "active_processes": len(heartbeats)}, sort_keys=True))
        return 0 if ready else 2
    if args.command == "health":
        report = check_readiness(persistence=client, service=args.service, release_id=str(os.getenv("SAGA_RELEASE_ID") or ""))
        print(report.model_dump_json(indent=2))
        return 0 if report.ready else 2

    releases = ReleaseRuntime(store=client.deployments)
    if args.release_action == "create":
        components = _parse_component_digests(args.component_digest)
        manifest = create_release_manifest(version=args.version, git_sha=args.git_sha, image_digest=args.image_digest,
            source_state=args.source_state, components=components,
            configuration={"queue_name": str(os.getenv("SAGA_EXECUTION_QUEUE_NAME") or "production-orchestration")})
        payload = releases.register(manifest)
    else:
        payload = releases.transition(args.release_id, args.status)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _parse_component_digests(values: list[str]) -> dict[str, str]:
    components: dict[str, str] = {}
    for value in values:
        name, separator, digest = str(value or "").partition("=")
        if not separator or not name.strip() or not digest.strip():
            raise ValueError("Each --component-digest must use NAME=SHA256 format.")
        if name.strip() in components:
            raise ValueError(f"Duplicate component digest '{name.strip()}'.")
        components[name.strip()] = digest.strip()
    return components


if __name__ == "__main__":
    raise SystemExit(main())
