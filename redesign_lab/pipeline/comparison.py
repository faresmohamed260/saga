"""Baseline vs redesign comparison reporting."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def generate_comparison_report(
    *,
    baseline_root: str | Path,
    redesign_root: str | Path,
    output_path: str | Path,
) -> Dict[str, Any]:
    baseline_root = Path(baseline_root)
    redesign_root = Path(redesign_root)
    redesign_report = _load_optional_json(redesign_root / "end_to_end" / "run_report.json") or {}
    baseline_status = _load_optional_json(Path("analysis_outputs/pipeline_runtime/acotar/latest_status.json"))
    payload = {
        "status": "completed",
        "baseline": {
            "root": str(baseline_root),
            "available": baseline_root.exists(),
            "latest_status": baseline_status,
        },
        "redesign": {
            "root": str(redesign_root),
            "available": redesign_root.exists(),
            "run_report": redesign_report,
        },
        "comparison": {
            "encoder_reliability": _status_score(baseline_status),
            "identity_quality": "pending_manual_audit",
            "duplicate_rate": "pending_manual_audit",
            "stable_state_richness": _stable_state_count(redesign_report),
            "retrieval_quality": "pending_manual_audit",
            "decoder_completion_reliability": bool(redesign_report.get("sequel_output_dir")),
            "prose_quality_and_canon_adherence": "pending_manual_audit",
            "runtime_and_cost_summary": {
                "baseline_runtime": (baseline_status or {}).get("elapsed_seconds"),
                "redesign_runtime": redesign_report.get("elapsed_seconds"),
            },
        },
    }
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_optional_json(path: Path) -> Dict[str, Any] | None:
    if not path.exists():
        return None
    return _load_json(path)


def _status_score(status: Dict[str, Any] | None) -> str:
    if not status:
        return "baseline_status_missing"
    if status.get("status") == "completed":
        return "completed"
    if status.get("status") == "running":
        return "running"
    return str(status.get("status") or "unknown")


def _stable_state_count(report: Dict[str, Any]) -> int:
    return int(report.get("stable_state_count") or 0)
