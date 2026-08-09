from __future__ import annotations

import os

import pytest

from scripts.validate_real_supabase_runtime import run_validation


REAL_SUPABASE_ENV_NAMES = (
    "SAGA_SUPABASE_DB_URL",
    "SAGA_SUPABASE_API_URL",
    "SAGA_SUPABASE_SERVICE_ROLE_KEY",
)


def _has_real_supabase_env() -> bool:
    return bool(str(os.getenv("SAGA_RUN_REAL_SUPABASE_TESTS") or "").strip()) and all(
        str(os.getenv(name) or "").strip()
        for name in REAL_SUPABASE_ENV_NAMES
    )


@pytest.mark.skipif(not _has_real_supabase_env(), reason="real Supabase validation env is not configured")
def test_real_supabase_runtime_validation_round_trip() -> None:
    result = run_validation()

    assert str(result["provider_config_provider"]).startswith("runtime-validation-")
    assert result["provider_status_label"] == "member-01"
    assert result["operational_ready_labels"] == ["member-01"]
    assert result["operational_diagnostics"] == []
    assert result["vector_document_count"] == 1
    assert str(result["vector_top_result"]).startswith("doc-")
    assert int(result["object_bytes_written"]) > 0
    assert result["downloaded_text"] == "real supabase runtime validation"
    assert result["artifact_bucket"] == "runtime-reports"
    assert result["object_deleted"] is True
    assert result["vectors_deleted"] == 1
