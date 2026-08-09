from __future__ import annotations

import os

import pytest

from scripts.validate_real_runtime_stack import run_validation


def _runtime_stack_env_ready() -> bool:
    if str(os.getenv("SAGA_RUN_REAL_RUNTIME_STACK_TESTS", "") or "").strip().lower() not in {"1", "true", "yes"}:
        return False
    required = (
        "SAGA_SUPABASE_DB_URL",
        "SAGA_SUPABASE_API_URL",
        "SAGA_SUPABASE_SERVICE_ROLE_KEY",
    )
    return all(str(os.getenv(name, "") or "").strip() for name in required)


@pytest.mark.skipif(not _runtime_stack_env_ready(), reason="Real runtime stack validation env vars are not configured.")
def test_real_runtime_stack_validation() -> None:
    result = run_validation()

    assert result["reasoning_answer"] == "42"
    assert "ready" in str(result["reasoning_text"]).lower()
    assert str(result["retrieval_top_document_id"]).startswith("doc-")
    assert result["retrieval_request_status"] == "ok"
    assert result["web_request_status"] == "ok"
    assert "victor frankenstein" in str(result["agent_final_output"]).lower()
    assert result["agent_tool_steps"] == 1
    assert result["agent_status"] == "ok"
    assert result["artifact_bucket"] == "runtime-reports"
