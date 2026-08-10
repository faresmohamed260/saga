"""Record fresh staging evidence from a persisted real-book qualification."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from packages.deployment_runtime import (
    check_readiness,
    create_deployment_persistence_client,
)
from packages.deployment_runtime.evidence import record_staging_runtime_evidence
from packages.execution_runtime.service import default_execution_slos
from packages.observability_runtime import ObservabilityRuntime, UsageGovernanceRuntime
from packages.qualification_runtime import ProductionQualificationReport


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--qualification-file", required=True)
    args = parser.parse_args()

    report = ProductionQualificationReport.model_validate_json(
        Path(args.qualification_file).resolve().read_text(encoding="utf-8")
    )
    persistence = create_deployment_persistence_client()
    try:
        readiness = check_readiness(
            persistence=persistence, service="staging-release-evidence", release_id=args.release_id,
        )
        usage = UsageGovernanceRuntime(store=persistence.usage).summary(run_id=report.run_id)
        cohort_run_ids = {
            str(item.get("run_id") or "")
            for item in persistence.execution_queue.list(limit=10000)
            if item.get("status") in {"succeeded", "cancelled", "dead_letter"}
            and str(
                dict(
                    dict(item.get("payload") or {}).get("orchestration_request") or {}
                ).get("metadata", {}).get("release_id")
                or ""
            )
            == args.release_id
        }
        slo = ObservabilityRuntime(store=persistence.observability).evaluate_slos(
            default_execution_slos(), persist_alerts=False, run_ids=cohort_run_ids,
        )
        evidence = record_staging_runtime_evidence(
            store=persistence.deployments,
            release_id=args.release_id,
            qualification=report,
            readiness=readiness,
            usage_summary=usage,
            slo_evaluations=[item.model_dump() for item in slo],
        )
        decision = persistence.deployments.list_release_gate_evidence(release_id=args.release_id, limit=1000)
        print(json.dumps({"recorded": evidence, "evidence_count": len(decision)}, indent=2, sort_keys=True))
        return 0 if all(item["status"] == "passed" for item in evidence) else 2
    finally:
        persistence.close()


if __name__ == "__main__":
    raise SystemExit(main())
