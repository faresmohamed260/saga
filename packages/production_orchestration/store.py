"""Run-scoped persistence for orchestration state and lineage."""

from __future__ import annotations

from packages.persistence_runtime import PersistenceRuntimeClient
from packages.production_orchestration.contracts import (
    DeliverableManifestArtifact,
    OrchestrationDecisionArtifact,
    OrchestrationRequest,
    StageOutcomeArtifact,
)


class OrchestrationStore:
    JOB_TYPE = "production_orchestration"

    def __init__(self, persistence: PersistenceRuntimeClient) -> None:
        self.persistence = persistence

    def create_or_load(self, request: OrchestrationRequest, planned_stages: list[str]) -> dict:
        current = self.persistence.jobs.get_job(request.run_id)
        if current:
            payload = dict(current.get("payload") or {})
            persisted = OrchestrationRequest.model_validate(payload.get("request") or {})
            if persisted.series_id != request.series_id:
                raise ValueError(f"Run '{request.run_id}' belongs to series '{persisted.series_id}'.")
            for field in ("story_id", "blueprint_id", "audiobook_run_id"):
                previous = str(getattr(persisted, field) or "")
                current_value = str(getattr(request, field) or "")
                if previous and current_value and previous != current_value:
                    raise ValueError(f"Run '{request.run_id}' cannot change {field} from '{previous}' to '{current_value}'.")
            for field in ("include_visuals", "include_audiobook"):
                if getattr(persisted, field) != getattr(request, field):
                    raise ValueError(f"Run '{request.run_id}' cannot change {field} after creation.")
            return current
        return self.persistence.jobs.create_job(
            request.run_id,
            job_type=self.JOB_TYPE,
            status="running",
            payload={"request": request.model_dump(), "planned_stages": planned_stages, "outcomes": {}},
        )

    def load_outcomes(self, run_id: str) -> dict[str, StageOutcomeArtifact]:
        row = self.persistence.jobs.get_job(run_id) or {}
        payload = dict(row.get("payload") or {})
        return {
            str(name): StageOutcomeArtifact.model_validate(item)
            for name, item in dict(payload.get("outcomes") or {}).items()
        }

    def save_outcome(self, request: OrchestrationRequest, planned_stages: list[str], outcome: StageOutcomeArtifact) -> StageOutcomeArtifact:
        row = self.persistence.jobs.get_job(request.run_id) or {}
        payload = dict(row.get("payload") or {})
        outcomes = dict(payload.get("outcomes") or {})
        outcomes[outcome.stage] = outcome.model_dump()
        payload.update(request=request.model_dump(), planned_stages=planned_stages, outcomes=outcomes)
        self.persistence.jobs.update_job(
            request.run_id,
            status="running" if outcome.accepted or outcome.status == "skipped" else outcome.status,
            payload=payload,
        )
        self.persistence.jobs.add_job_log(
            request.run_id,
            stage=outcome.stage,
            message=f"stage_{outcome.status}",
            payload={"accepted": outcome.accepted, "reused": outcome.reused, "attempt": outcome.attempt, "elapsed_seconds": outcome.elapsed_seconds},
        )
        return outcome

    def replace_outcomes(self, request: OrchestrationRequest, planned_stages: list[str], outcomes: dict[str, StageOutcomeArtifact]) -> None:
        row = self.persistence.jobs.get_job(request.run_id) or {}
        payload = dict(row.get("payload") or {})
        payload.update(
            request=request.model_dump(),
            planned_stages=planned_stages,
            outcomes={name: item.model_dump() for name, item in outcomes.items()},
            manifest=None,
            decision=None,
        )
        self.persistence.jobs.update_job(request.run_id, status="running", payload=payload)

    def finalize(self, request: OrchestrationRequest, planned_stages: list[str], decision: OrchestrationDecisionArtifact, manifest: DeliverableManifestArtifact | None) -> None:
        row = self.persistence.jobs.get_job(request.run_id) or {}
        payload = dict(row.get("payload") or {})
        payload.update(
            request=request.model_dump(),
            planned_stages=planned_stages,
            decision=decision.model_dump(),
            manifest=manifest.model_dump() if manifest else None,
        )
        self.persistence.jobs.update_job(request.run_id, status=decision.status, payload=payload)
        self.persistence.jobs.add_job_log(request.run_id, stage="orchestration", message=f"run_{decision.status}", payload=decision.model_dump())
