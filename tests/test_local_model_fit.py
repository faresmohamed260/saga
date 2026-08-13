import json
from pathlib import Path

from benchmarks.reasoning.model_fit import evaluate_candidate_fit


def test_candidate_decisions_match_resource_fit_policy():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "benchmarks/reasoning/local_model_candidates.json").read_text(encoding="utf-8"))
    results = evaluate_candidate_fit(manifest)

    assert all(item["decision_consistent"] for item in results)
    assert next(item for item in results if item["model"] == "qwen3.5:9b-q4_K_M")["interactive_fit"]
    assert not next(item for item in results if item["model"] == "gpt-oss:20b")["interactive_fit"]
