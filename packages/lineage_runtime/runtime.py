"""Provider-neutral immutable lineage service."""

from __future__ import annotations

import uuid
from typing import Any

from packages.lineage_runtime.canonical import fingerprint, sanitize
from packages.lineage_runtime.contracts import ArtifactVersionStore, LineageRecordStore, StageLineageRecord, StageLineageSpec


class LineageRuntime:
    def __init__(self, *, store: LineageRecordStore, artifact_versions: ArtifactVersionStore | None = None) -> None:
        self.store = store
        self.artifact_versions = artifact_versions

    def fingerprints(
        self, *, spec: StageLineageSpec, parent_fingerprints: dict[str, str], output_payload: Any | None = None,
    ) -> dict[str, str]:
        versions = spec.versions.model_dump()
        input_fingerprint = fingerprint({
            "stage": spec.stage,
            "input": spec.input_payload,
            "versions": versions,
            "parents": parent_fingerprints,
        })
        output_fingerprint = fingerprint(output_payload) if output_payload is not None else ""
        lineage_fingerprint = fingerprint({
            "stage": spec.stage,
            "input_fingerprint": input_fingerprint,
            "output_fingerprint": output_fingerprint,
            "versions": versions,
            "parents": parent_fingerprints,
        })
        return {
            "input_fingerprint": input_fingerprint,
            "output_fingerprint": output_fingerprint,
            "lineage_fingerprint": lineage_fingerprint,
        }

    def find_accepted(
        self, *, series_id: str, stage: str, input_fingerprint: str, output_fingerprint: str,
    ) -> StageLineageRecord | None:
        row = self.store.find_latest_accepted(
            series_id=series_id,
            stage=stage,
            input_fingerprint=input_fingerprint,
            output_fingerprint=output_fingerprint,
        )
        return StageLineageRecord.model_validate(row) if row else None

    def has_output_artifact_version(self, execution_id: str) -> bool:
        row = self.store.get(str(execution_id or "")) if execution_id else None
        payload = dict((row or {}).get("payload") or {})
        artifact = dict(payload.get("output_artifact_version") or {})
        return bool(artifact.get("bucket_name") and artifact.get("object_path"))

    def record(
        self,
        *,
        run_id: str,
        series_id: str,
        spec: StageLineageSpec,
        parent_fingerprints: dict[str, str],
        output_payload: Any,
        status: str,
        attempt: int,
        execution_mode: str,
        payload: dict[str, Any] | None = None,
    ) -> StageLineageRecord:
        digests = self.fingerprints(spec=spec, parent_fingerprints=parent_fingerprints, output_payload=output_payload)
        execution_id = f"lineage-{uuid.uuid4().hex}"
        record_payload = sanitize(payload or {})
        if self.artifact_versions is not None:
            record_payload["output_artifact_version"] = self.artifact_versions.put(
                execution_id=execution_id,
                run_id=run_id,
                series_id=series_id,
                stage=spec.stage,
                output_fingerprint=digests["output_fingerprint"],
                output_payload=sanitize(output_payload),
            )
        row = StageLineageRecord(
            execution_id=execution_id,
            run_id=run_id,
            series_id=series_id,
            stage=spec.stage,
            attempt=max(1, int(attempt)),
            status=status,
            execution_mode=execution_mode,
            parent_fingerprints=parent_fingerprints,
            versions=spec.versions.model_dump(),
            payload=record_payload,
            **digests,
        )
        return StageLineageRecord.model_validate(self.store.append(row.model_dump(exclude={"created_at"})))

    def history(self, *, run_id: str = "", series_id: str = "", stage: str = "") -> list[StageLineageRecord]:
        return [StageLineageRecord.model_validate(item) for item in self.store.list(run_id=run_id, series_id=series_id, stage=stage)]
