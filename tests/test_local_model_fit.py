import json
from pathlib import Path

from benchmarks.reasoning.model_fit import evaluate_candidate_fit, qualification_artifacts


def test_candidate_decisions_match_resource_fit_policy():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "benchmarks/reasoning/local_model_candidates.json").read_text(encoding="utf-8"))
    results = evaluate_candidate_fit(manifest)

    assert all(item["decision_consistent"] for item in results)
    qwen_ollama = next(
        item for item in results
        if item["model_id"] == "qwen3.5-9b" and item["engine"] == "ollama"
    )
    qwen_lm_studio = next(
        item for item in results
        if item["model_id"] == "qwen3.5-9b" and item["engine"] == "lm_studio"
    )
    gpt_oss = next(item for item in results if item["model_id"] == "gpt-oss-20b")

    assert qwen_ollama["full_gpu_fit"] is True
    assert qwen_ollama["qualification_eligible"] is True
    assert qwen_lm_studio["resource_fit"] is True
    assert qwen_lm_studio["qualification_eligible"] is False
    assert gpt_oss["full_gpu_fit"] is False
    assert gpt_oss["controlled_hybrid_fit"] is True
    assert gpt_oss["qualification_eligible"] is True

    allowed = qualification_artifacts(manifest)
    assert ("lm_studio_local", "openai/gpt-oss-20b") in allowed
    assert (
        "lm_studio_local",
        "openai-gpt-oss-20b-abliterated-uncensored-neo-imatrix",
    ) not in allowed


def test_invalid_gpu_fraction_is_rejected():
    manifest = {
        "host": {
            "desktop_baseline_vram_gib": 1.0,
            "max_total_vram_gib": 10.0,
            "desktop_baseline_ram_gib": 10.0,
            "max_host_ram_gib": 20.0,
        },
        "fit_policy": {
            "estimated_runtime_multiplier": 1.0,
            "estimated_kv_and_compute_gib": 0.5,
            "controlled_hybrid_allowed": True,
            "minimum_gpu_fraction": 0.4,
        },
        "candidates": [{
            "model_id": "invalid",
            "artifacts": [{
                "engine": "lm_studio",
                "provider": "lm_studio_local",
                "engine_model": "invalid",
                "artifact_gib": 1.0,
                "gpu_fraction": 1.1,
                "engine_status": "supported",
                "decision": "exclude_resource_fit",
            }],
        }],
    }

    import pytest

    with pytest.raises(ValueError, match="gpu_fraction"):
        evaluate_candidate_fit(manifest)
