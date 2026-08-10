from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from packages.lineage_runtime import LineageRuntime, LineageVersions, StageLineageSpec, fingerprint, sanitize
from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client
from packages.production_orchestration import OrchestrationRequest
from packages.production_orchestration.lineage import build_stage_spec


def _runtime(tmp_path: Path) -> tuple[object, LineageRuntime]:
    profile = PersistenceProfile(
        name="lineage-test",
        provider="supabase",
        mode="test_harness",
        database_url=f"sqlite:///{tmp_path / 'lineage.sqlite3'}",
        local_storage_root_dir=str(tmp_path / "storage"),
    )
    client = create_persistence_client(profile=profile, config=PersistenceRuntimeConfig(profile=profile))
    client.initialize()
    return client, LineageRuntime(store=client.lineage)


def _spec(**versions: str) -> StageLineageSpec:
    version_payload = {"runtime": "planning-v1", "prompt": "prompt-v1", **versions}
    return StageLineageSpec(
        stage="generation_planning",
        input_payload={"series_id": "series-1", "premise": "A difficult peace."},
        versions=LineageVersions(**version_payload),
    )


def test_fingerprints_are_canonical_and_secret_values_are_excluded():
    left = {"nested": {"b": 2, "a": 1}, "api_token": "first-secret"}
    right = {"api_token": "different-secret", "nested": {"a": 1, "b": 2}}
    assert fingerprint(left) == fingerprint(right)
    assert sanitize(left)["api_token"] == "<redacted>"
    assert sanitize({"usage": {"input_tokens": 12, "output_tokens": 3}})["usage"] == {
        "input_tokens": 12,
        "output_tokens": 3,
    }


def test_source_input_and_version_changes_have_distinct_fingerprints(tmp_path: Path):
    _, runtime = _runtime(tmp_path)
    base = runtime.fingerprints(spec=_spec(), parent_fingerprints={})["input_fingerprint"]
    changed_input = _spec().model_copy(update={"input_payload": {"series_id": "series-1", "premise": "A broken peace."}})
    changed_prompt = _spec(prompt="prompt-v2")
    changed_model = _spec(model="model-v2")
    changed_workflow = _spec(workflow="workflow-v2")
    changed_policy = _spec(quality_policy="policy-v2")
    assert len({
        base,
        runtime.fingerprints(spec=changed_input, parent_fingerprints={})["input_fingerprint"],
        runtime.fingerprints(spec=changed_prompt, parent_fingerprints={})["input_fingerprint"],
        runtime.fingerprints(spec=changed_model, parent_fingerprints={})["input_fingerprint"],
        runtime.fingerprints(spec=changed_workflow, parent_fingerprints={})["input_fingerprint"],
        runtime.fingerprints(spec=changed_policy, parent_fingerprints={})["input_fingerprint"],
    }) == 6


def test_source_content_mutation_invalidates_analysis_at_the_same_path(tmp_path: Path):
    _, runtime = _runtime(tmp_path)
    source = tmp_path / "book.epub"
    source.write_bytes(b"first source version")
    request = OrchestrationRequest(
        run_id="source-run", series_id="series-1", source_paths=[str(source)],
        selected_stages=["analysis_foundation"], include_visuals=False, include_audiobook=False,
    )
    first = runtime.fingerprints(
        spec=build_stage_spec("analysis_foundation", request), parent_fingerprints={},
    )["input_fingerprint"]
    source.write_bytes(b"second source version")
    second = runtime.fingerprints(
        spec=build_stage_spec("analysis_foundation", request), parent_fingerprints={},
    )["input_fingerprint"]
    assert first != second


def test_history_is_append_only_and_matching_requires_current_output(tmp_path: Path):
    client, runtime = _runtime(tmp_path)
    first = runtime.record(
        run_id="run-1", series_id="series-1", spec=_spec(), parent_fingerprints={},
        output_payload={"blueprint_id": "bp-1", "revision": 1}, status="accepted",
        attempt=1, execution_mode="executed",
    )
    second = runtime.record(
        run_id="run-1", series_id="series-1", spec=_spec(), parent_fingerprints={},
        output_payload={"blueprint_id": "bp-1", "revision": 2}, status="accepted",
        attempt=2, execution_mode="executed",
    )
    assert [item.execution_id for item in runtime.history(run_id="run-1")] == [first.execution_id, second.execution_id]
    assert first.output_fingerprint != second.output_fingerprint
    assert runtime.find_accepted(
        series_id="series-1", stage="generation_planning",
        input_fingerprint=first.input_fingerprint, output_fingerprint=first.output_fingerprint,
    ).execution_id == first.execution_id
    with pytest.raises(IntegrityError):
        client.lineage.append(first.model_dump(exclude={"created_at"}))


def test_concurrent_appends_preserve_every_execution(tmp_path: Path):
    _, runtime = _runtime(tmp_path)

    def append(index: int) -> str:
        return runtime.record(
            run_id="run-concurrent", series_id="series-1", spec=_spec(), parent_fingerprints={},
            output_payload={"revision": index}, status="accepted", attempt=index + 1,
            execution_mode="executed",
        ).execution_id

    with ThreadPoolExecutor(max_workers=4) as pool:
        execution_ids = list(pool.map(append, range(8)))
    assert len(set(execution_ids)) == 8
    assert len(runtime.history(run_id="run-concurrent")) == 8
