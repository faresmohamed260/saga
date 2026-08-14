from __future__ import annotations

import json
from pathlib import Path

from benchmarks.reasoning.task_suite import TASK_SUITE_VERSION
from packages.reasoning_runtime import QualifiedReasoningRouter, ReasoningRuntimeConfig


def test_tracked_local_production_routes_are_fail_closed_and_resolvable():
    root = Path(__file__).resolve().parents[1]
    payload = json.loads(
        (root / "benchmarks/reasoning/local_production_routes_v1.json").read_text(
            encoding="utf-8"
        )
    )

    router = QualifiedReasoningRouter(
        scorecard=payload,
        config=ReasoningRuntimeConfig(),
    )

    assert payload["decision"] == "partial_ready"
    assert payload["task_suite_version"] == TASK_SUITE_VERSION
    assert payload["policy"]["allow_unqualified_fallback"] is False
    assert router.qualified_families() == ("structured_json", "tool_use")
    assert router.client_for("structured_json") is router.client_for("tool_use")
