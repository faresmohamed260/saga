from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from packages.execution_runtime import ExecutionRuntimeService
from packages.production_orchestration import OrchestrationRequest


def main() -> int:
    parser = argparse.ArgumentParser(description="Submit, inspect, cancel, or execute durable production work.")
    sub = parser.add_subparsers(dest="command", required=True)
    submit = sub.add_parser("submit")
    submit.add_argument("--request-json", required=True)
    submit.add_argument("--priority", type=int, default=0)
    submit.add_argument("--max-attempts", type=int, default=3)
    submit.add_argument("--backoff-seconds", type=int, default=10)
    cancel = sub.add_parser("cancel")
    cancel.add_argument("--queue-id", required=True)
    cancel.add_argument("--reason", default="")
    retry = sub.add_parser("retry")
    retry.add_argument("--request-json", required=True)
    retry.add_argument("--priority", type=int, default=0)
    retry.add_argument("--max-attempts", type=int, default=3)
    status = sub.add_parser("status")
    status.add_argument("--queue-id", required=True)
    worker = sub.add_parser("worker")
    worker.add_argument("--worker-id", default="")
    worker.add_argument("--poll", action="store_true")
    worker.add_argument("--poll-seconds", type=float, default=2.0)
    args = parser.parse_args()
    service = ExecutionRuntimeService.from_env()
    if args.command == "submit":
        request = OrchestrationRequest.model_validate_json(Path(args.request_json).read_text(encoding="utf-8"))
        payload = service.submit(request, priority=args.priority, max_attempts=args.max_attempts, backoff_seconds=args.backoff_seconds)
    elif args.command == "cancel":
        payload = service.cancel(args.queue_id, reason=args.reason)
    elif args.command == "retry":
        request = OrchestrationRequest.model_validate_json(Path(args.request_json).read_text(encoding="utf-8"))
        payload = service.retry(request, priority=args.priority, max_attempts=args.max_attempts)
    elif args.command == "status":
        payload = service.queue.get(args.queue_id)
    else:
        while True:
            result = service.run_worker_once(worker_id=args.worker_id)
            print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
            if not args.poll:
                return 0 if result.status not in {"dead_letter", "lease_lost"} else 2
            if result.status == "idle":
                time.sleep(max(0.2, args.poll_seconds))
        return 0
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
