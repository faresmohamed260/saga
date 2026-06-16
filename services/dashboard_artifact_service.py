"""Helpers for browsing dashboard artifacts on local disk."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_OUTPUTS_DIR = PROJECT_ROOT / "analysis_outputs"
PIPELINE_RUNTIME_DIR = ANALYSIS_OUTPUTS_DIR / "pipeline_runtime"
CONTRACT_EXPORTS_DIR = ANALYSIS_OUTPUTS_DIR / "contract_exports"
IDENTITY_SERIES_DIR = ANALYSIS_OUTPUTS_DIR / "identity_series"
STATE_SNAPSHOTS_DIR = ANALYSIS_OUTPUTS_DIR / "state_snapshots"
VISUAL_STATE_DIR = ANALYSIS_OUTPUTS_DIR / "visual_state"
RETRIEVAL_VALIDATION_DIR = ANALYSIS_OUTPUTS_DIR / "retrieval_validation"
ENCODER_VALIDATION_DIR = ANALYSIS_OUTPUTS_DIR / "encoder_validation"


def to_display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path.resolve())


def read_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _parse_timestamp(value: str) -> datetime:
    text = str(value or "").replace("Z", "+00:00")
    return datetime.fromisoformat(text)


def _artifact_record(path: Path, category: str) -> dict[str, Any]:
    return {
        "name": path.name,
        "path": path.resolve(),
        "display_path": to_display_path(path),
        "category": category,
        "size_bytes": path.stat().st_size,
        "modified_at": datetime.fromtimestamp(path.stat().st_mtime),
    }


def discover_encode_runs(base_dir: Path | None = None) -> list[dict[str, Any]]:
    root = base_dir or PIPELINE_RUNTIME_DIR
    if not root.exists():
        return []

    results: list[dict[str, Any]] = []
    for series_dir in sorted((item for item in root.iterdir() if item.is_dir()), key=lambda item: item.name.lower()):
        latest_status_path = series_dir / "latest_status.json"
        latest_status = read_json_file(latest_status_path) if latest_status_path.exists() else {}
        run_dirs = [
            item for item in series_dir.iterdir()
            if item.is_dir() and item.name[:4].isdigit() and (item / "status.json").exists()
        ]
        run_dirs.sort(key=lambda item: item.name, reverse=True)
        for run_dir in run_dirs:
            status_path = run_dir / "status.json"
            status_data = read_json_file(status_path)
            contracts_dir = CONTRACT_EXPORTS_DIR / series_dir.name / run_dir.name / "contracts"
            reports_dir = run_dir / "reports"
            contract_paths = sorted(contracts_dir.glob("*.json")) if contracts_dir.exists() else []
            report_paths = sorted(reports_dir.iterdir()) if reports_dir.exists() else []
            summary = status_data.get("summary") or {}
            results.append({
                "series_id": series_dir.name,
                "run_id": run_dir.name,
                "path": run_dir.resolve(),
                "display_path": to_display_path(run_dir),
                "status": status_data.get("status") or latest_status.get("status") or "unknown",
                "started_at": status_data.get("started_at_utc"),
                "updated_at": status_data.get("updated_at_utc"),
                "book_count": len(status_data.get("books") or []),
                "completed_books": summary.get("completed", 0),
                "failed_books": summary.get("failed", 0),
                "remaining_books": summary.get("remaining", 0),
                "total_requested": summary.get("total_requested", len(status_data.get("books") or [])),
                "contract_count": len(contract_paths),
                "report_count": len(report_paths),
                "contract_paths": contract_paths,
                "report_paths": report_paths,
                "status_path": status_path.resolve(),
                "log_path": (run_dir / "encode.log").resolve() if (run_dir / "encode.log").exists() else None,
                "latest_status": latest_status,
                "status_data": status_data,
            })
    results.sort(
        key=lambda item: (
            _parse_timestamp(item["started_at"]) if item.get("started_at") else datetime.min,
            item["series_id"],
            item["run_id"],
        ),
        reverse=True,
    )
    return results


def discover_contract_files(base_dir: Path | None = None) -> list[dict[str, Any]]:
    root = base_dir or CONTRACT_EXPORTS_DIR
    if not root.exists():
        return []

    items: list[dict[str, Any]] = []
    for contract_path in root.glob("*/*/contracts/*.json"):
        record = _artifact_record(contract_path, "contract")
        record["series_id"] = contract_path.parents[2].name
        record["run_id"] = contract_path.parents[1].name
        items.append(record)
    return sorted(items, key=lambda item: item["modified_at"], reverse=True)


def discover_identity_files(base_dir: Path | None = None) -> list[dict[str, Any]]:
    root = base_dir or IDENTITY_SERIES_DIR
    if not root.exists():
        return []

    items: list[dict[str, Any]] = []
    for path in root.rglob("*.json"):
        items.append(_artifact_record(path, "identity"))
    return sorted(items, key=lambda item: item["modified_at"], reverse=True)


def discover_state_snapshot_files(base_dir: Path | None = None) -> list[dict[str, Any]]:
    root = base_dir or STATE_SNAPSHOTS_DIR
    if not root.exists():
        return []
    return sorted(
        (_artifact_record(path, "state_snapshot") for path in root.glob("*.json")),
        key=lambda item: item["modified_at"],
        reverse=True,
    )


def discover_visual_world_state_files(base_dir: Path | None = None) -> list[dict[str, Any]]:
    root = base_dir or VISUAL_STATE_DIR
    if not root.exists():
        return []
    items = []
    for path in root.glob("*visual_world_state*.json"):
        items.append(_artifact_record(path, "visual_world_state"))
    return sorted(items, key=lambda item: item["modified_at"], reverse=True)


def discover_prompt_pack_files(base_dir: Path | None = None) -> list[dict[str, Any]]:
    root = base_dir or VISUAL_STATE_DIR
    if not root.exists():
        return []
    items = []
    for path in root.glob("*prompt_pack*.json"):
        items.append(_artifact_record(path, "prompt_pack"))
    return sorted(items, key=lambda item: item["modified_at"], reverse=True)


def discover_retrieval_context_files(base_dir: Path | None = None) -> list[dict[str, Any]]:
    root = base_dir or RETRIEVAL_VALIDATION_DIR
    if not root.exists():
        return []
    items = []
    for path in root.glob("*.json"):
        items.append(_artifact_record(path, "retrieval_context"))
    return sorted(items, key=lambda item: item["modified_at"], reverse=True)


def discover_report_files(base_dir: Path | None = None) -> list[dict[str, Any]]:
    root = base_dir or ANALYSIS_OUTPUTS_DIR
    if not root.exists():
        return []

    encoder_validation_dir = root / "encoder_validation"
    retrieval_validation_dir = root / "retrieval_validation"
    visual_state_dir = root / "visual_state"
    state_snapshots_dir = root / "state_snapshots"
    identity_series_dir = root / "identity_series"
    pipeline_runtime_dir = root / "pipeline_runtime"

    items: list[dict[str, Any]] = []
    report_globs = [
        encoder_validation_dir.glob("*.md"),
        encoder_validation_dir.glob("*.json"),
        retrieval_validation_dir.glob("*.md"),
        retrieval_validation_dir.glob("*.json"),
        visual_state_dir.glob("*.md"),
        visual_state_dir.glob("*.json"),
        state_snapshots_dir.glob("*.md"),
        identity_series_dir.rglob("*audit*.md"),
        identity_series_dir.rglob("*audit*.json"),
        pipeline_runtime_dir.glob("*/*/reports/*"),
    ]
    seen: set[Path] = set()
    for iterator in report_globs:
        for path in iterator:
            if not path.is_file():
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            items.append(_artifact_record(path, "report"))
    return sorted(items, key=lambda item: item["modified_at"], reverse=True)


def build_contract_summary(contract: dict[str, Any]) -> dict[str, Any]:
    outputs = contract.get("outputs") or {}
    diagnostics = contract.get("diagnostics") or {}
    identity = contract.get("identity") or contract.get("identity_result") or {}
    return {
        "series_id": ((contract.get("inputs") or {}).get("series") or {}).get("series_id", ""),
        "book_title": (((contract.get("inputs") or {}).get("books") or [{}])[0]).get("title", ""),
        "chapter_count": len(outputs.get("chapters") or []),
        "scene_count": len(outputs.get("scene_analyses") or outputs.get("scenes") or []),
        "timeline_count": len(outputs.get("timeline") or []),
        "event_ledger_count": len(outputs.get("event_ledger") or []),
        "character_profile_count": len(outputs.get("character_profiles") or []),
        "reference_entity_count": diagnostics.get("reference_entity_count", 0),
        "alias_count": len(identity.get("alias_map") or {}),
        "generated_at_utc": contract.get("generated_at_utc", ""),
        "analysis_model": ((contract.get("configuration") or {}).get("analysis_model_resolved")
                           or (contract.get("configuration") or {}).get("analysis_model")
                           or ""),
        "identity_provider": (contract.get("configuration") or {}).get("identity_provider", ""),
        "scene_failure_policy": (contract.get("configuration") or {}).get("scene_failure_policy", ""),
    }
