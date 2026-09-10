from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(".github/workflows/production-qualification-readiness.yml")


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_readiness_workflow_is_manual_and_main_only() -> None:
    text = _workflow_text()

    assert "\n  workflow_dispatch:\n" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert 'refs/heads/main' in text
    assert 'asset_id:' in text
    assert 'required: true' in text


def test_readiness_workflow_uses_read_only_preflight_contract() -> None:
    text = _workflow_text()

    assert "scripts.check_production_qualification_readiness" in text
    assert "SAGA_SUPABASE_DB_URL" in text
    assert "SAGA_SUPABASE_DB_HOST" in text
    assert "SAGA_SUPABASE_API_URL" in text
    assert "SAGA_SUPABASE_SERVICE_ROLE_KEY" in text
    assert "SUPABASE_URL" in text
    assert "SUPABASE_SERVICE_ROLE_KEY" in text
    assert "OLLAMA_API_KEY" in text
    assert "MISTRAL_API_KEY" in text
    assert "SAGA_PROVIDER_COST_RATES_JSON" in text
    assert 'exit "$rc"' in text


def test_readiness_workflow_cannot_download_protected_assets_or_run_qualification() -> None:
    text = _workflow_text()

    prohibited = (
        "scripts.run_production_qualification",
        "check_protected_asset_storage",
        "verify_protected_assets",
        "R2_ACCOUNT_ID",
        "R2_BUCKET_NAME",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "confirm_live_cost",
        "saga-process",
        "saga-execution",
    )
    for token in prohibited:
        assert token not in text


def test_readiness_workflow_has_minimal_repository_permission() -> None:
    text = _workflow_text()

    assert "permissions:\n  contents: read\n" in text
    assert "contents: write" not in text
    assert "actions: write" not in text
