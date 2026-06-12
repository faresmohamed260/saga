"""Shared benchmark helpers for redesign_lab."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List


def ensure_dir(path: str | Path) -> Path:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def write_json(path: str | Path, payload: Dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def timed_call(func: Callable, *args, **kwargs) -> tuple[Any, float, str]:
    started = time.perf_counter()
    error = ""
    try:
        result = func(*args, **kwargs)
    except Exception as exc:  # pragma: no cover - runtime benchmark guard
        result = None
        error = repr(exc)
    elapsed = round(time.perf_counter() - started, 2)
    return result, elapsed, error


def choose_winner(results: Iterable[Dict[str, Any]]) -> Dict[str, Any] | None:
    candidates = [item for item in results if item.get("status") == "ok"]
    if not candidates:
        return None
    ranked = sorted(
        candidates,
        key=lambda item: (
            float(item.get("semantic_score", 0.0)),
            float(item.get("validity_score", 0.0)),
            -float(item.get("structural_failures", 0.0)),
            -float(item.get("elapsed_seconds", 99999.0)),
            -float(item.get("estimated_cost", 0.0)),
        ),
        reverse=True,
    )
    return ranked[0]


def save_case_artifact(
    output_root: str | Path,
    *,
    task_name: str,
    candidate_id: str,
    case_id: str,
    payload: Dict[str, Any],
) -> Path:
    target = ensure_dir(Path(output_root) / task_name / candidate_id)
    return write_json(target / f"{case_id}.json", payload)


def summarize_task_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    valid = [item for item in results if item.get("status") == "ok"]
    return {
        "candidate_count": len(results),
        "available_count": len(valid),
        "best_semantic_score": max((float(item.get("semantic_score", 0.0)) for item in valid), default=0.0),
        "best_validity_score": max((float(item.get("validity_score", 0.0)) for item in valid), default=0.0),
    }
