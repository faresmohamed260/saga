from __future__ import annotations

from packages.reasoning_runtime import QualificationEvaluation, QualificationTrial
from benchmarks.reasoning.scorecard import build_scorecard


def _trial(model: str, family: str, repetition: int, accepted: bool, wall: float) -> QualificationTrial:
    return QualificationTrial(
        trial_id=f"{model}-{family}-{repetition}", suite_id="suite", corpus_version="1",
        model=model, provider="ollama_local", run_variant="tasks-1.1.0-full-ollama-ctx4096",
        task_id=f"{family}:case", repetition=repetition,
        status="accepted" if accepted else "rejected", wall_seconds=wall,
        evaluation=QualificationEvaluation(accepted=accepted), created_at_ms=1,
    )


def test_scorecard_routes_only_fully_reliable_models_and_prefers_latency():
    trials = []
    for repetition in range(1, 4):
        trials.append(_trial("fast", "tool_use", repetition, True, 1.0))
        trials.append(_trial("slow", "tool_use", repetition, True, 2.0))
        trials.append(_trial("partial", "canon_events", repetition, repetition < 3, 1.0))

    scorecard = build_scorecard(trials, minimum_sources=0, required_families=["narrative_generation"])

    assert scorecard["routes"]["tool_use"]["model"] == "fast"
    assert scorecard["routes"]["canon_events"] == {"status": "unqualified", "model": None}
    assert scorecard["routes"]["narrative_generation"] == {"status": "unqualified", "model": None}
    assert scorecard["policy"]["allow_unqualified_fallback"] is False
