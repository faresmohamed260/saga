from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from packages.execution_runtime import ExecutionQueuePolicy, ExecutionQueueRuntime
from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client


def _client(label: str):
    profile = PersistenceProfile(
        name=f"execution-validation-{label}",
        provider="supabase",
        mode="supabase_postgres",
        application_name=f"saga-execution-validation-{label}",
    )
    client = create_persistence_client(profile=profile, config=PersistenceRuntimeConfig(profile=profile))
    client.initialize()
    return client


def run_validation() -> dict[str, object]:
    started = time.perf_counter()
    suffix = uuid4().hex[:10]
    queue_name = f"execution-validation-{suffix}"
    first_runtime = ExecutionQueueRuntime(persistence=_client("first"), queue_name=queue_name)
    second_runtime = ExecutionQueueRuntime(persistence=_client("second"), queue_name=queue_name)
    first_runtime.configure(ExecutionQueuePolicy(global_limit=1, per_series_limit=1))

    for index in range(2):
        first_runtime.store.enqueue(
            f"queue-{suffix}-{index}",
            run_id=f"run-{suffix}-{index}",
            queue_name=queue_name,
            series_id=f"series-{suffix}-{index}",
            capabilities=["reasoning"],
            payload={"validation": True},
            backoff_seconds=0,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda args: args[0].claim(worker_id=args[1], lease_seconds=1), [
            (first_runtime, "worker-a"),
            (second_runtime, "worker-b"),
        ]))
    claimed = [item for item in claims if item is not None]
    if len(claimed) != 1:
        raise AssertionError(f"Expected one atomic claim under global_limit=1; received {len(claimed)}.")

    stale = claimed[0]
    expiry = int(stale["lease_expires_at_ms"])
    if first_runtime.store.complete(
        stale["queue_id"], worker_id=stale["lease_owner"], lease_token=stale["lease_token"], now_ms=expiry + 1,
    ) is not None:
        raise AssertionError("An expired lease was allowed to complete work.")

    recovered = first_runtime.recover(now_ms=expiry + 1)
    replacement = second_runtime.claim(worker_id="worker-recovery", lease_seconds=30, now_ms=expiry + 1)
    if replacement is None or replacement["queue_id"] != stale["queue_id"]:
        raise AssertionError("Expired work was not recovered and reclaimed deterministically.")
    completed = second_runtime.store.complete(
        replacement["queue_id"], worker_id="worker-recovery", lease_token=replacement["lease_token"],
        payload={"validated": True}, now_ms=expiry + 2,
    )
    next_item = first_runtime.claim(worker_id="worker-next", lease_seconds=30, now_ms=expiry + 2)
    if next_item is None:
        raise AssertionError("The second queued item was not admitted after capacity was released.")
    first_runtime.store.complete(
        next_item["queue_id"], worker_id="worker-next", lease_token=next_item["lease_token"],
        payload={"validated": True}, now_ms=expiry + 3,
    )

    events = first_runtime.events(stale["run_id"])
    return {
        "queue_name": queue_name,
        "concurrent_claim_count": len(claimed),
        "stale_completion_rejected": True,
        "recovered_count": len(recovered),
        "reclaimed_queue_id": replacement["queue_id"],
        "completed_status": completed["status"],
        "telemetry_event_count": len(events),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }


if __name__ == "__main__":
    print(json.dumps(run_validation(), indent=2, sort_keys=True))
