from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from packages.reasoning_runtime import QualificationEvaluation, QualificationTrial
from benchmarks.reasoning.scorecard import build_scorecard


def _trial(
    model: str, family: str, repetition: int, accepted: bool, wall: float,
    *, provider: str = "ollama_local", peak_vram_bytes: int | None = None,
    gold_reviewed: bool = False,
) -> QualificationTrial:
    request_metadata = {}
    if peak_vram_bytes is not None:
        request_metadata["resource_metrics"] = {
            "peak_vram_used_bytes": peak_vram_bytes,
            "peak_host_used_bytes": 64 * 1024 ** 3,
        }
    return QualificationTrial(
        trial_id=f"{model}-{family}-{repetition}", suite_id="suite", corpus_version="1",
        model=model, provider=provider, run_variant="tasks-1.1.0-full-local-ctx4096",
        task_id=f"{family}:case", repetition=repetition,
        status="accepted" if accepted else "rejected", wall_seconds=wall,
        request_metadata=request_metadata,
        evaluation=QualificationEvaluation(
            accepted=accepted,
            metrics={"gold_available": True, "gold_reviewed": True} if gold_reviewed else {},
        ),
        created_at_ms=1,
    )


def test_scorecard_routes_only_fully_reliable_models_and_prefers_latency():
    trials = []
    for repetition in range(1, 4):
        trials.append(_trial("fast", "tool_use", repetition, True, 1.0))
        trials.append(_trial("slow", "tool_use", repetition, True, 2.0))
        trials.append(_trial("partial", "canon_events", repetition, repetition < 3, 1.0))

    scorecard = build_scorecard(trials, minimum_sources=0, required_families=["narrative_generation"])

    assert scorecard["routes"]["tool_use"]["model"] == "fast"
    assert scorecard["routes"]["tool_use"]["provider"] == "ollama_local"
    assert scorecard["routes"]["canon_events"] == {"status": "unqualified", "model": None}
    assert scorecard["routes"]["narrative_generation"] == {"status": "unqualified", "model": None}
    assert scorecard["policy"]["allow_unqualified_fallback"] is False


def test_scorecard_requires_complete_resource_evidence_for_production_routes():
    limit = 10 * 1024 ** 3
    trials = [
        _trial("safe", "tool_use", repetition, True, 1.0, peak_vram_bytes=8 * 1024 ** 3)
        for repetition in range(1, 4)
    ]
    trials.extend([
        _trial("unknown", "tool_use", repetition, True, 0.5)
        for repetition in range(1, 4)
    ])
    trials.extend([
        _trial("oversized", "tool_use", repetition, True, 0.5, peak_vram_bytes=11 * 1024 ** 3)
        for repetition in range(1, 4)
    ])

    scorecard = build_scorecard(
        trials,
        minimum_sources=0,
        require_resource_metrics=True,
        max_peak_vram_bytes=limit,
        max_peak_host_ram_bytes=112 * 1024 ** 3,
    )

    assert scorecard["routes"]["tool_use"]["model"] == "safe"
    by_model = {row["model"]: row for row in scorecard["results"]}
    assert by_model["unknown"]["resource_evidence_complete"] is False
    assert by_model["oversized"]["resource_limits_met"] is False


def test_scorecard_cli_is_directly_executable():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "scripts/build_local_reasoning_scorecard.py"), "--help"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=15,
    )

    assert result.returncode == 0, result.stderr
    assert "max-peak-vram-gib" in result.stdout


def test_scorecard_requires_reviewed_gold_for_extraction_routes():
    trials = [
        _trial("model", "canon_entities", repetition, True, 1.0)
        for repetition in range(1, 4)
    ]
    scorecard = build_scorecard(
        trials,
        minimum_sources=0,
        require_gold_for_families={"canon_entities"},
    )

    assert scorecard["routes"]["canon_entities"]["status"] == "unqualified"
    assert scorecard["results"][0]["gold_evidence_complete"] is False

    reviewed_trials = [
        _trial("model", "canon_entities", repetition, True, 1.0, gold_reviewed=True)
        for repetition in range(1, 4)
    ]
    reviewed_scorecard = build_scorecard(
        reviewed_trials,
        minimum_sources=0,
        require_gold_for_families={"canon_entities"},
    )

    assert reviewed_scorecard["routes"]["canon_entities"]["status"] == "qualified"

    combined_scorecard = build_scorecard(
        [*trials, *reviewed_trials],
        minimum_sources=0,
        require_gold_for_families={"canon_entities"},
    )
    assert combined_scorecard["routes"]["canon_entities"]["status"] == "qualified"
    assert combined_scorecard["results"][0]["trials"] == 3
    assert combined_scorecard["superseded_trial_count"] == 3


def test_scorecard_never_merges_same_model_across_engines():
    trials = [
        _trial(
            "shared-model", "tool_use", repetition, True, 1.0,
            provider="ollama_local",
        )
        for repetition in range(1, 3)
    ]
    trials.append(_trial(
        "shared-model", "tool_use", 3, True, 0.5,
        provider="lm_studio_local",
    ))

    scorecard = build_scorecard(trials, minimum_sources=0)

    assert len(scorecard["results"]) == 2
    assert scorecard["routes"]["tool_use"] == {"status": "unqualified", "model": None}


def test_scorecard_never_qualifies_mixed_execution_profiles():
    trials = [
        _trial("model", "tool_use", repetition, True, 1.0)
        for repetition in range(1, 4)
    ]
    trials[-1].run_variant = "tasks-1.1.0-full-local-ctx8192"

    scorecard = build_scorecard(trials, minimum_sources=0)

    assert scorecard["routes"]["tool_use"] == {
        "status": "unqualified", "model": None,
    }
    assert scorecard["results"][0]["execution_profile_consistent"] is False


def test_scorecard_excludes_trials_outside_artifact_allowlist():
    trials = [
        _trial(
            "unapproved-derivative", "structured_json", repetition, True, 0.5,
            provider="lm_studio_local",
        )
        for repetition in range(1, 4)
    ]

    scorecard = build_scorecard(
        trials,
        minimum_sources=0,
        allowed_provider_models={("lm_studio_local", "approved-model")},
    )

    assert scorecard["results"] == []
    assert scorecard["excluded_trial_count"] == 3
    assert scorecard["routes"] == {}
    assert scorecard["policy"]["artifact_allowlist_enforced"] is True


def test_scorecard_preserves_quality_performance_and_failure_evidence():
    accepted = _trial("model", "continuity_grounding", 1, True, 2.0)
    accepted.run_variant = "tasks-1.2.0-full-ollama-ctx4096"
    accepted.evaluation.metrics = {
        "classification_accuracy": 1.0,
        "hallucination_rate": 0.0,
    }
    accepted.request_metadata["provider_metrics"] = {
        "ttft_seconds": 0.5,
        "tokens_per_second": 20.0,
    }
    rejected = _trial("model", "continuity_grounding", 2, False, 3.0)
    rejected.run_variant = "tasks-1.2.0-full-ollama-ctx4096"
    rejected.evaluation.metrics = {
        "classification_accuracy": 0.5,
        "hallucination_rate": 0.5,
    }

    row = build_scorecard(
        [accepted, rejected], minimum_trials=2, minimum_sources=0,
    )["results"][0]

    assert row["quality_metrics"]["hallucination_rate"]["median"] == 0.25
    assert row["quality_metrics"]["contradiction_error_rate"]["median"] == 0.25
    assert row["provider_metrics"]["ttft_seconds"]["median"] == 0.5
    assert row["failure_modes"] == {"rejected": 1}
    assert row["context_windows_tested"] == [4096]
