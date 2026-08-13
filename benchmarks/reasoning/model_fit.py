"""Deterministic pre-download hardware-fit checks for local model candidates."""

from __future__ import annotations

from typing import Any


def evaluate_candidate_fit(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    host = dict(manifest["host"])
    policy = dict(manifest["fit_policy"])
    multiplier = float(policy["estimated_runtime_multiplier"])
    runtime_overhead = float(policy["estimated_kv_and_compute_gib"])
    desktop = float(host["desktop_baseline_vram_gib"])
    maximum = float(host["max_total_vram_gib"])

    results = []
    for candidate in list(manifest["candidates"]):
        projected = desktop + float(candidate["artifact_gib"]) * multiplier + runtime_overhead
        fits = projected <= maximum
        results.append({
            "model": str(candidate["model"]),
            "projected_total_vram_gib": round(projected, 2),
            "interactive_fit": fits,
            "decision": str(candidate["decision"]),
            "decision_consistent": fits == str(candidate["decision"]).startswith("qualify"),
        })
    return results
