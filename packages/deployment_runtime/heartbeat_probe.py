"""Bounded process-heartbeat probe for container health checks."""

from __future__ import annotations

import argparse
import json
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlalchemy.engine import make_url

from packages.persistence_runtime.database_url import build_database_url_from_env


def process_heartbeat_ready(
    *,
    role: str,
    release_id: str = "",
    max_age_seconds: int = 180,
    database_url: str = "",
    now_ms: int | None = None,
    connector: Callable[..., Any] | None = None,
) -> bool:
    resolved_url = str(database_url or build_database_url_from_env()).strip()
    if not resolved_url:
        raise RuntimeError("Process heartbeat probe requires the Supabase database environment.")
    url = make_url(resolved_url)
    if url.get_backend_name() != "postgresql":
        raise ValueError("Process heartbeat probe requires PostgreSQL.")
    if connector is None:
        import psycopg

        connector = psycopg.connect
    query = """
        SELECT EXISTS (
            SELECT 1
            FROM deployment_process_heartbeats
            WHERE role = %s
              AND status = 'ready'
              AND last_seen_ms >= %s
              AND (%s = '' OR release_id = %s)
        )
    """
    threshold = int(now_ms or time.time() * 1000) - max(1, int(max_age_seconds)) * 1000
    options = dict(url.query)
    with connector(
        host=url.host,
        port=url.port or 5432,
        dbname=url.database,
        user=url.username,
        password=url.password,
        sslmode=str(options.get("sslmode") or "prefer"),
        connect_timeout=3,
        application_name="saga-heartbeat-probe",
        prepare_threshold=None,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (role, threshold, release_id, release_id))
            row = cursor.fetchone()
    return bool(row and row[0])


def local_heartbeat_ready(
    *,
    role: str,
    release_id: str = "",
    max_age_seconds: int = 180,
    heartbeat_dir: str = "",
    now_ms: int | None = None,
) -> bool:
    root = str(heartbeat_dir or os.getenv("SAGA_LOCAL_HEARTBEAT_DIR") or "").strip()
    if not root:
        raise RuntimeError("Local heartbeat probe requires SAGA_LOCAL_HEARTBEAT_DIR.")
    payload = json.loads((Path(root) / f"{role}.json").read_text(encoding="utf-8"))
    threshold = int(now_ms or time.time() * 1000) - max(1, int(max_age_seconds)) * 1000
    return bool(
        payload.get("role") == role
        and payload.get("status") == "ready"
        and int(payload.get("last_seen_ms") or 0) >= threshold
        and (not release_id or payload.get("release_id") == release_id)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", required=True, choices=("worker", "scheduler", "observability"))
    parser.add_argument("--release-id", default=str(os.getenv("SAGA_RELEASE_ID") or ""))
    parser.add_argument("--max-age-seconds", type=int, default=180)
    args = parser.parse_args()
    started = time.perf_counter()
    try:
        local_dir = str(os.getenv("SAGA_LOCAL_HEARTBEAT_DIR") or "").strip()
        ready = (
            local_heartbeat_ready(
                role=args.role,
                release_id=args.release_id,
                max_age_seconds=args.max_age_seconds,
                heartbeat_dir=local_dir,
            )
            if local_dir
            else process_heartbeat_ready(
                role=args.role,
                release_id=args.release_id,
                max_age_seconds=args.max_age_seconds,
            )
        )
        payload = {"ready": ready, "role": args.role, "elapsed_seconds": round(time.perf_counter() - started, 4)}
    except Exception as exc:
        payload = {
            "ready": False,
            "role": args.role,
            "elapsed_seconds": round(time.perf_counter() - started, 4),
            "error": type(exc).__name__,
        }
    print(json.dumps(payload, sort_keys=True))
    return 0 if payload["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
