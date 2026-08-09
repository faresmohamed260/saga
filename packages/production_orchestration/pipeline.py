"""LangGraph-native production orchestration with resumable stage policy."""

from __future__ import annotations

import hashlib
import time
from typing import Any, Callable, TypedDict, cast

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from packages.agent_runtime import SqlCheckpointSaver
from packages.lineage_runtime import LineageRuntime, StageLineageSpec
from packages.persistence_runtime import PersistenceRuntimeClient
from packages.production_orchestration.contracts import (
    DeliverableManifestArtifact,
    DeliverablePackager,
    OrchestrationDecisionArtifact,
    OrchestrationRequest,
    OrchestrationResult,
    OrchestrationStage,
    StageName,
    StageOutcomeArtifact,
)
from packages.production_orchestration.policy import STAGE_DEPENDENCIES, STAGE_ORDER, resolve_stage_plan
from packages.production_orchestration.lineage import PersistenceArtifactVersionStore, build_stage_spec, normalized_outcome_payload, parent_fingerprints
from packages.production_orchestration.store import OrchestrationStore
from packages.runtime_common import RuntimeCancelledError, UsageGovernor, usage_scope


class OrchestrationState(TypedDict, total=False):
    request: dict[str, Any]
    planned_stages: list[str]
    outcomes: dict[str, dict[str, Any]]
    manifest: dict[str, Any] | None
    decision: dict[str, Any]
    run_metadata: dict[str, Any]


class StageAgent:
    def __init__(
        self, *, stage: StageName, binding: OrchestrationStage, store: OrchestrationStore,
        lineage: LineageRuntime, version_overrides: dict[str, dict[str, Any]], cancellation_checker: Callable[[str], bool],
        usage_governor: UsageGovernor | None = None, release_id: str = "",
    ) -> None:
        self.stage = stage
        self.binding = binding
        self.store = store
        self.lineage = lineage
        self.version_overrides = version_overrides
        self.cancellation_checker = cancellation_checker
        self.usage_governor = usage_governor
        self.release_id = str(release_id or "")

    def run(self, state: OrchestrationState) -> dict[str, Any]:
        request = OrchestrationRequest.model_validate(state["request"])
        planned = list(state.get("planned_stages") or [])
        if self.stage not in planned:
            return {}
        outcomes = _outcomes(state)
        current = outcomes.get(self.stage)
        stage_context = _upstream_outcomes(outcomes, self.stage)
        if self.cancellation_checker(request.run_id):
            outcome = StageOutcomeArtifact(
                stage=self.stage,
                status="cancelled",
                accepted=False,
                attempt=(current.attempt if current else 0) + 1,
                started_at=int(time.time()),
                completed_at=int(time.time()),
                reasons=["Execution cancellation was requested."],
            )
            return self._persist(state, request, planned, outcomes, outcome)
        unmet = [name for name in STAGE_DEPENDENCIES[self.stage] if name in planned and not (outcomes.get(name) and outcomes[name].accepted)]
        if unmet:
            outcome = _failure(self.stage, current, "DependencyRejected", f"Unaccepted dependencies: {', '.join(unmet)}")
            return self._persist(state, request, planned, outcomes, outcome)
        started = time.perf_counter()
        started_at = int(time.time())
        parents = parent_fingerprints(self.stage, request, planned, stage_context)
        spec = self._spec(request, stage_context)
        expected = self.lineage.fingerprints(spec=spec, parent_fingerprints=parents)
        try:
            inspected = self.binding.inspect(request=request, outcomes=stage_context)
            inspected_output = self._output(request, stage_context, inspected) if inspected and inspected.accepted else None
            inspected_digests = self.lineage.fingerprints(
                spec=spec, parent_fingerprints=parents, output_payload=inspected_output,
            ) if inspected_output is not None else None
            current_lineage = dict((current.metadata if current else {}).get("lineage") or {})
            if current and current.accepted and inspected_digests and self._matches(current_lineage, inspected_digests):
                return {}
            matching = self.lineage.find_accepted(
                series_id=request.series_id,
                stage=self.stage,
                input_fingerprint=expected["input_fingerprint"],
                output_fingerprint=inspected_digests["output_fingerprint"] if inspected_digests else "",
            ) if inspected_digests else None
            if inspected and inspected.accepted and (matching or (current and current.accepted and not current_lineage)):
                mode = "reused" if matching else "adopted"
                outcome = inspected.model_copy(update={
                    "stage": self.stage,
                    "reused": True,
                    "attempt": max(1, current.attempt if current else 1),
                    "started_at": started_at,
                    "completed_at": int(time.time()),
                    "elapsed_seconds": round(time.perf_counter() - started, 4),
                })
                outcome = self._with_lineage(
                    request=request, spec=spec, parents=parents, output_payload=inspected_output,
                    outcome=outcome, execution_mode=mode,
                )
            else:
                previous_attempt = current.attempt if current and not current.accepted else 0
                if current and not current.accepted and previous_attempt >= max(1, request.max_attempts):
                    return {}
                with usage_scope(
                    governor=self.usage_governor, release_id=self.release_id, run_id=request.run_id,
                    series_id=request.series_id, stage=self.stage, agent=f"{self.stage}_agent",
                ):
                    outcome = self.binding.execute(request=request, outcomes=stage_context)
                outcome = outcome.model_copy(update={
                    "stage": self.stage,
                    "attempt": (current.attempt if current else 0) + 1,
                    "started_at": started_at,
                    "completed_at": int(time.time()),
                    "elapsed_seconds": round(time.perf_counter() - started, 4),
                })
                outcome = self._with_lineage(
                    request=request, spec=spec, parents=parents,
                    output_payload=self._output(request, stage_context, outcome), outcome=outcome, execution_mode="executed",
                )
        except RuntimeCancelledError as exc:
            outcome = StageOutcomeArtifact(
                stage=self.stage, status="cancelled", accepted=False,
                attempt=(current.attempt if current else 0) + 1,
                started_at=started_at, completed_at=int(time.time()),
                elapsed_seconds=round(time.perf_counter() - started, 4), reasons=[str(exc)],
            )
            outcome = self._with_lineage(
                request=request, spec=spec, parents=parents,
                output_payload=normalized_outcome_payload(outcome), outcome=outcome, execution_mode="executed",
            )
        except Exception as exc:
            outcome = _failure(self.stage, current, type(exc).__name__, str(exc), started_at=started_at, started=started)
            outcome = self._with_lineage(
                request=request, spec=spec, parents=parents,
                output_payload=normalized_outcome_payload(outcome), outcome=outcome, execution_mode="executed",
            )
        return self._persist(state, request, planned, outcomes, outcome)

    def _spec(self, request: OrchestrationRequest, outcomes: dict[str, StageOutcomeArtifact]) -> StageLineageSpec:
        builder = getattr(self.binding, "lineage_spec", None)
        return builder(request=request, outcomes=outcomes) if builder else build_stage_spec(
            self.stage, request, version_overrides=self.version_overrides,
        )

    def _output(
        self, request: OrchestrationRequest, outcomes: dict[str, StageOutcomeArtifact], outcome: StageOutcomeArtifact,
    ) -> Any:
        builder = getattr(self.binding, "lineage_output", None)
        return builder(request=request, outcomes=outcomes, outcome=outcome) if builder else normalized_outcome_payload(outcome)

    def _matches(self, current: dict[str, Any], expected: dict[str, str]) -> bool:
        fingerprints_match = all(str(current.get(key) or "") == expected[key] for key in (
            "input_fingerprint", "output_fingerprint", "lineage_fingerprint",
        ))
        return fingerprints_match and self.lineage.has_output_artifact_version(str(current.get("execution_id") or ""))

    def _with_lineage(
        self, *, request: OrchestrationRequest, spec: StageLineageSpec, parents: dict[str, str],
        output_payload: Any, outcome: StageOutcomeArtifact, execution_mode: str,
    ) -> StageOutcomeArtifact:
        record = self.lineage.record(
            run_id=request.run_id,
            series_id=request.series_id,
            spec=spec,
            parent_fingerprints=parents,
            output_payload=output_payload,
            status="accepted" if outcome.accepted else outcome.status,
            attempt=outcome.attempt,
            execution_mode=execution_mode,
            payload={"outcome": normalized_outcome_payload(outcome)},
        )
        metadata = dict(outcome.metadata or {})
        metadata["lineage"] = record.model_dump(exclude={"payload", "created_at", "versions", "parent_fingerprints"})
        metadata["lineage"]["parent_fingerprints"] = record.parent_fingerprints
        metadata["lineage"]["versions"] = record.versions
        return outcome.model_copy(update={"metadata": metadata})

    def _persist(
        self,
        state: OrchestrationState,
        request: OrchestrationRequest,
        planned: list[str],
        outcomes: dict[str, StageOutcomeArtifact],
        outcome: StageOutcomeArtifact,
    ) -> dict[str, Any]:
        persisted = self.store.save_outcome(request, planned, outcome)
        outcomes[self.stage] = persisted
        result: dict[str, Any] = {
            "outcomes": {name: item.model_dump() for name, item in outcomes.items()},
            "run_metadata": _stage_metadata(state, persisted),
        }
        if self.stage == "artifact_packaging" and persisted.accepted and persisted.output_context.get("manifest"):
            result["manifest"] = persisted.output_context["manifest"]
        return result


class PackagingStage:
    def __init__(self, packager: DeliverablePackager) -> None:
        self.packager = packager

    def inspect(self, *, request: OrchestrationRequest, outcomes: dict[str, StageOutcomeArtifact]) -> StageOutcomeArtifact | None:
        del request
        current = outcomes.get("artifact_packaging")
        return current if current and current.accepted and current.output_context.get("manifest") else None

    def execute(self, *, request: OrchestrationRequest, outcomes: dict[str, StageOutcomeArtifact]) -> StageOutcomeArtifact:
        manifest = self.packager.package(request=request, outcomes=outcomes)
        return StageOutcomeArtifact(
            stage="artifact_packaging",
            status="accepted" if manifest.status == "accepted" else "rejected",
            accepted=manifest.status == "accepted",
            artifact_refs=list(manifest.artifacts),
            output_context={"manifest": manifest.model_dump(), "manifest_id": manifest.manifest_id},
            metrics={"artifact_count": len(manifest.artifacts), "manifest_version": manifest.version},
        )


class OrchestrationDecisionAgent:
    def __init__(self, store: OrchestrationStore) -> None:
        self.store = store

    def run(self, state: OrchestrationState) -> dict[str, Any]:
        request = OrchestrationRequest.model_validate(state["request"])
        planned = cast(list[StageName], list(state.get("planned_stages") or []))
        outcomes = _outcomes(state)
        failed = next((stage for stage in planned if stage not in outcomes or not outcomes[stage].accepted), None)
        accepted = failed is None and bool(planned)
        failed_outcome = outcomes.get(failed) if failed else None
        status = "accepted" if accepted else (
            "cancelled" if failed_outcome and failed_outcome.status == "cancelled"
            else "failed" if failed_outcome and failed_outcome.status == "failed"
            else "rejected"
        )
        decision = OrchestrationDecisionArtifact(
            decision_id=_stable_id("orchestration-decision", request.run_id),
            run_id=request.run_id,
            series_id=request.series_id,
            accepted=accepted,
            status=status,
            completed_stages=[stage for stage in planned if outcomes.get(stage) and outcomes[stage].accepted],
            failed_stage=failed,
            reasons=[] if accepted else list((failed_outcome.reasons if failed_outcome else [f"Stage '{failed}' did not complete."])),
        )
        manifest = DeliverableManifestArtifact.model_validate(state["manifest"]) if state.get("manifest") else None
        self.store.finalize(request, planned, decision, manifest)
        return {"decision": decision.model_dump()}


class ProductionOrchestrationRuntime:
    def __init__(
        self,
        *,
        persistence: PersistenceRuntimeClient,
        stages: dict[StageName, OrchestrationStage],
        packager: DeliverablePackager,
        checkpointer: BaseCheckpointSaver | None = None,
        allow_in_memory_checkpointer: bool = False,
        cancellation_checker: Callable[[str], bool] | None = None,
        lineage_version_overrides: dict[str, dict[str, Any]] | None = None,
        usage_governor: UsageGovernor | None = None,
        release_id: str = "",
    ) -> None:
        missing = [stage for stage in STAGE_ORDER if stage != "artifact_packaging" and stage not in stages]
        if missing:
            raise ValueError(f"Missing orchestration stage bindings: {', '.join(missing)}")
        self.store = OrchestrationStore(persistence)
        self.lineage = LineageRuntime(
            store=persistence.lineage,
            artifact_versions=PersistenceArtifactVersionStore(persistence.artifacts),
        )
        resolved_cancellation_checker = cancellation_checker or (lambda run_id: False)
        bindings = dict(stages)
        bindings["artifact_packaging"] = PackagingStage(packager)
        self.graph = build_production_orchestration_graph(
            store=self.store,
            stages=bindings,
            checkpointer=_resolve_checkpointer(persistence, checkpointer, allow_in_memory_checkpointer),
            cancellation_checker=resolved_cancellation_checker,
            lineage=self.lineage,
            version_overrides=dict(lineage_version_overrides or {}),
            usage_governor=usage_governor,
            release_id=release_id,
        )

    def invoke(self, request: OrchestrationRequest, *, thread_id: str = "") -> OrchestrationResult:
        planned = resolve_stage_plan(request)
        row = self.store.create_or_load(request, planned)
        persisted_payload = dict(row.get("payload") or {})
        persisted_plan = list(persisted_payload.get("planned_stages") or [])
        planned = [stage for stage in STAGE_ORDER if stage in set(planned) | set(persisted_plan)]
        outcomes = self.store.load_outcomes(request.run_id)
        added_stages = [stage for stage in planned if stage not in persisted_plan]
        if added_stages:
            invalidate_from = min(STAGE_ORDER.index(stage) for stage in added_stages)
            outcomes = {stage: item for stage, item in outcomes.items() if STAGE_ORDER.index(stage) < invalidate_from}
            self.store.replace_outcomes(request, planned, outcomes)
        persisted_manifest = persisted_payload.get("manifest") if not added_stages else None
        state = self.graph.invoke(
            {
                "request": request.model_dump(),
                "planned_stages": planned,
                "outcomes": {name: item.model_dump() for name, item in outcomes.items()},
                "manifest": persisted_manifest,
                "run_metadata": {},
            },
            config={"configurable": {"thread_id": thread_id or request.run_id}},
        )
        return _result(state)


def build_production_orchestration_graph(
    *, store: OrchestrationStore, stages: dict[StageName, OrchestrationStage], checkpointer: BaseCheckpointSaver | None = None,
    cancellation_checker: Callable[[str], bool] | None = None, lineage: LineageRuntime,
    version_overrides: dict[str, dict[str, Any]] | None = None,
    usage_governor: UsageGovernor | None = None, release_id: str = "",
):
    resolved_cancellation_checker = cancellation_checker or (lambda run_id: False)
    graph = StateGraph(OrchestrationState)
    for stage in STAGE_ORDER:
        graph.add_node(stage, StageAgent(
            stage=stage, binding=stages[stage], store=store, lineage=lineage,
            version_overrides=dict(version_overrides or {}), cancellation_checker=resolved_cancellation_checker,
            usage_governor=usage_governor, release_id=release_id,
        ).run)
    graph.add_node("orchestration_decision", OrchestrationDecisionAgent(store).run)
    graph.add_edge(START, STAGE_ORDER[0])
    for index, stage in enumerate(STAGE_ORDER):
        next_node = STAGE_ORDER[index + 1] if index + 1 < len(STAGE_ORDER) else "orchestration_decision"
        graph.add_conditional_edges(stage, lambda state, current=stage: _route(state, current), {"continue": next_node, "decide": "orchestration_decision"})
    graph.add_edge("orchestration_decision", END)
    return graph.compile(checkpointer=checkpointer)


def _route(state: OrchestrationState, stage: StageName) -> str:
    if stage not in set(state.get("planned_stages") or []):
        return "continue"
    outcome = _outcomes(state).get(stage)
    return "continue" if outcome and outcome.accepted else "decide"


def _outcomes(state: OrchestrationState) -> dict[str, StageOutcomeArtifact]:
    return {name: StageOutcomeArtifact.model_validate(item) for name, item in dict(state.get("outcomes") or {}).items()}


def _upstream_outcomes(
    outcomes: dict[str, StageOutcomeArtifact], stage: StageName,
) -> dict[str, StageOutcomeArtifact]:
    boundary = STAGE_ORDER.index(stage)
    return {
        name: outcome for name, outcome in outcomes.items()
        if name in STAGE_ORDER and (
            STAGE_ORDER.index(name) < boundary
            or (stage == "artifact_packaging" and name == stage)
        )
    }


def _failure(
    stage: StageName,
    previous: StageOutcomeArtifact | None,
    error_type: str,
    message: str,
    *,
    started_at: int | None = None,
    started: float | None = None,
) -> StageOutcomeArtifact:
    return StageOutcomeArtifact(
        stage=stage,
        status="failed",
        accepted=False,
        attempt=(previous.attempt if previous else 0) + 1,
        started_at=started_at or int(time.time()),
        completed_at=int(time.time()),
        elapsed_seconds=round(time.perf_counter() - started, 4) if started is not None else 0.0,
        reasons=[message],
        error_type=error_type,
        error_message=message,
    )


def _stage_metadata(state: OrchestrationState, outcome: StageOutcomeArtifact) -> dict[str, Any]:
    metadata = dict(state.get("run_metadata") or {})
    timings = dict(metadata.get("stage_timings") or {})
    timings[outcome.stage] = outcome.elapsed_seconds
    metadata["stage_timings"] = timings
    return metadata


def _result(state: OrchestrationState) -> OrchestrationResult:
    outcomes = _outcomes(state)
    return OrchestrationResult(
        request=OrchestrationRequest.model_validate(state["request"]),
        planned_stages=list(state.get("planned_stages") or []),
        outcomes=[outcomes[stage] for stage in STAGE_ORDER if stage in outcomes],
        manifest=DeliverableManifestArtifact.model_validate(state["manifest"]) if state.get("manifest") else None,
        decision=OrchestrationDecisionArtifact.model_validate(state["decision"]),
        run_metadata=dict(state.get("run_metadata") or {}),
    )


def _resolve_checkpointer(persistence: PersistenceRuntimeClient, checkpointer: BaseCheckpointSaver | None, allow_memory: bool) -> BaseCheckpointSaver:
    if checkpointer is not None:
        return checkpointer
    if getattr(persistence, "engine", None) is not None:
        return SqlCheckpointSaver(engine=persistence.engine)
    if allow_memory:
        return InMemorySaver()
    raise ValueError("ProductionOrchestrationRuntime requires a durable checkpointer or initialized persistence engine.")


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:20]}"
