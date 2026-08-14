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

    baseline_ram = float(host["desktop_baseline_ram_gib"])
    maximum_ram = float(host["max_host_ram_gib"])
    hybrid_allowed = bool(policy["controlled_hybrid_allowed"])
    minimum_gpu_fraction = float(policy["minimum_gpu_fraction"])

    results = []
    for candidate in list(manifest["candidates"]):
        for artifact in list(candidate["artifacts"]):
            artifact_gib = float(artifact["artifact_gib"])
            gpu_fraction = float(artifact["gpu_fraction"])
            if not 0.0 <= gpu_fraction <= 1.0:
                raise ValueError("Candidate gpu_fraction must be between zero and one.")
            full_gpu_projection = desktop + artifact_gib * multiplier + runtime_overhead
            projected_vram = desktop + artifact_gib * multiplier * gpu_fraction + runtime_overhead
            projected_ram = baseline_ram + artifact_gib * multiplier * (1.0 - gpu_fraction)
            full_gpu_fit = full_gpu_projection <= maximum
            controlled_hybrid_fit = (
                hybrid_allowed
                and minimum_gpu_fraction <= gpu_fraction < 1.0
                and projected_vram <= maximum
                and projected_ram <= maximum_ram
            )
            resource_fit = full_gpu_fit or controlled_hybrid_fit
            engine_supported = str(artifact["engine_status"]) == "supported"
            eligible = resource_fit and engine_supported
            decision = str(artifact["decision"])
            results.append({
                "model_id": str(candidate["model_id"]),
                "engine": str(artifact["engine"]),
                "provider": str(artifact["provider"]),
                "engine_model": str(artifact["engine_model"]),
                "gpu_fraction": gpu_fraction,
                "projected_total_vram_gib": round(projected_vram, 2),
                "projected_total_host_ram_gib": round(projected_ram, 2),
                "full_gpu_fit": full_gpu_fit,
                "controlled_hybrid_fit": controlled_hybrid_fit,
                "resource_fit": resource_fit,
                "engine_supported": engine_supported,
                "qualification_eligible": eligible,
                "decision": decision,
                "execution_status": str(artifact.get("execution_status", "scheduled")),
                "decision_consistent": eligible == decision.startswith("qualify"),
            })
    return results


def qualification_artifacts(manifest: dict[str, Any]) -> set[tuple[str, str]]:
    """Return the exact provider/model pairs allowed to enter a scorecard."""

    return {
        (row["provider"], row["engine_model"])
        for row in evaluate_candidate_fit(manifest)
        if row["qualification_eligible"]
    }
