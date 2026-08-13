"""Build deterministic local-reasoning scorecards and conservative routes."""

from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any, Iterable

from packages.reasoning_runtime import QualificationTrial


def build_scorecard(
    trials: Iterable[QualificationTrial], *, minimum_trials: int = 3,
    minimum_acceptance_rate: float = 1.0, minimum_sources: int = 3,
    required_families: Iterable[str] = (),
) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[QualificationTrial]] = defaultdict(list)
    for trial in trials:
        grouped[(trial.task_id.split(":", 1)[0], trial.model)].append(trial)

    rows: list[dict[str, Any]] = []
    for (family, model), items in sorted(grouped.items()):
        accepted = sum(item.status == "accepted" for item in items)
        failed = sum(item.status == "failed" for item in items)
        acceptance_rate = accepted / len(items)
        rows.append({
            "task_family": family,
            "model": model,
            "trials": len(items),
            "accepted": accepted,
            "failed": failed,
            "source_count": len({
                str(item.task_metadata.get("source_id") or "") for item in items
                if item.task_metadata.get("source_id")
            }),
            "acceptance_rate": round(acceptance_rate, 6),
            "median_wall_seconds": round(statistics.median(item.wall_seconds for item in items), 6),
            "qualified": (
                len(items) >= minimum_trials
                and len({
                    str(item.task_metadata.get("source_id") or "") for item in items
                    if item.task_metadata.get("source_id")
                }) >= minimum_sources
                and failed == 0
                and acceptance_rate >= minimum_acceptance_rate
            ),
        })

    routes: dict[str, dict[str, Any]] = {}
    families = {row["task_family"] for row in rows} | {str(item) for item in required_families}
    for family in sorted(families):
        eligible = [row for row in rows if row["task_family"] == family and row["qualified"]]
        if not eligible:
            routes[family] = {"status": "unqualified", "model": None}
            continue
        winner = min(eligible, key=lambda row: (row["median_wall_seconds"], row["model"]))
        routes[family] = {
            "status": "qualified",
            "model": winner["model"],
            "acceptance_rate": winner["acceptance_rate"],
            "median_wall_seconds": winner["median_wall_seconds"],
        }
    return {
        "policy": {
            "minimum_trials": minimum_trials,
            "minimum_acceptance_rate": minimum_acceptance_rate,
            "minimum_sources": minimum_sources,
            "allow_unqualified_fallback": False,
        },
        "routes": routes,
        "results": rows,
    }
