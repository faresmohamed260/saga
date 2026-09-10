from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import check_production_qualification_readiness as readiness


def _cost_rates_json() -> str:
    return json.dumps(
        [
            {
                "provider": provider,
                "request_each": 0.01,
                "pricing_version": "test-2026-09-10",
            }
            for provider in readiness.REQUIRED_PRICED_PROVIDERS
        ]
    )


def _ready_reasoning() -> dict[str, object]:
    return {
        "ollama": {
            "configured": True,
            "accounts": [{"label": "member-01", "has_api_key": True}],
        },
        "mistral": {"configured": False, "has_env_api_key": True},
    }


def _modal_row() -> dict[str, object]:
    return {
        "payload": {
            "accounts": [
                {
                    "label": "member-01",
                    "token_id": "token-id",
                    "token_secret": "token-secret",
                }
            ]
        }
    }


def _asset() -> dict[str, str]:
    return {
        "id": "fresh-book",
        "filename": "Fresh Book.epub",
        "sha256": "a" * 64,
        "object_key": "protected/saga/Fresh Book.epub",
    }


def _write_manifest(path: Path) -> None:
    path.write_text(json.dumps({"version": 1, "assets": [_asset()]}), encoding="utf-8")


def test_static_readiness_accepts_explicit_runtime_database_url() -> None:
    env = {
        "SAGA_RUNTIME_DB_URL": "postgresql+psycopg://example.invalid/postgres",
        "SAGA_SUPABASE_API_URL": "https://example.supabase.co",
        "SAGA_SUPABASE_SERVICE_ROLE_KEY": "service-role",
        "SAGA_PROVIDER_COST_RATES_JSON": _cost_rates_json(),
    }
    assert readiness.static_readiness_errors(env) == []


def test_static_readiness_accepts_component_database_configuration() -> None:
    env = {
        "SAGA_SUPABASE_DB_HOST": "db.example.supabase.co",
        "SAGA_SUPABASE_DB_USER": "postgres.project",
        "SAGA_SUPABASE_DB_PASSWORD": "password",
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "service-role",
        "SAGA_PROVIDER_COST_RATES_JSON": _cost_rates_json(),
    }
    assert readiness.static_readiness_errors(env) == []


def test_static_readiness_rejects_component_database_without_remote_host() -> None:
    env = {
        "SAGA_SUPABASE_DB_USER": "postgres.project",
        "SAGA_SUPABASE_DB_PASSWORD": "password",
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "service-role",
        "SAGA_PROVIDER_COST_RATES_JSON": _cost_rates_json(),
    }
    assert readiness.static_readiness_errors(env) == ["supabase_database_not_configured"]


def test_static_readiness_reports_missing_contracts_without_values() -> None:
    assert readiness.static_readiness_errors({}) == [
        "supabase_database_not_configured",
        "supabase_api_not_configured",
        "supabase_service_role_not_configured",
        "provider_cost_rates_not_configured",
    ]


def test_validate_cost_rates_rejects_empty_invalid_or_unversioned_rates() -> None:
    assert readiness.validate_cost_rates({}) == "provider_cost_rates_not_configured"
    assert (
        readiness.validate_cost_rates({"SAGA_PROVIDER_COST_RATES_JSON": "not-json"})
        == "provider_cost_rates_invalid"
    )
    assert (
        readiness.validate_cost_rates({"SAGA_PROVIDER_COST_RATES_JSON": "[]"})
        == "provider_cost_rates_invalid"
    )
    assert (
        readiness.validate_cost_rates(
            {
                "SAGA_PROVIDER_COST_RATES_JSON": json.dumps(
                    [{"provider": "mistral", "request_each": 0.01, "pricing_version": ""}]
                )
            }
        )
        == "provider_cost_rates_invalid"
    )


def test_validate_cost_rates_requires_provider_wide_fallbacks() -> None:
    missing_modal = json.dumps(
        [
            {
                "provider": "ollama",
                "request_each": 0.01,
                "pricing_version": "test",
            },
            {
                "provider": "mistral",
                "request_each": 0.01,
                "pricing_version": "test",
            },
            {
                "provider": "modal",
                "model": "saga-image-runtime",
                "request_each": 0.01,
                "pricing_version": "test",
            },
        ]
    )
    assert readiness.validate_cost_rates(
        {"SAGA_PROVIDER_COST_RATES_JSON": missing_modal}
    ) == "provider_cost_rate_fallback_missing:modal"


def test_validate_cost_rates_accepts_versioned_provider_fallbacks() -> None:
    assert (
        readiness.validate_cost_rates(
            {"SAGA_PROVIDER_COST_RATES_JSON": _cost_rates_json()}
        )
        == ""
    )


def test_select_qualification_asset_requires_one_known_manifest_asset(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    _write_manifest(manifest)

    selected = readiness.select_qualification_asset(
        asset_id="fresh-book",
        manifest_path=manifest,
    )
    assert selected["filename"] == "Fresh Book.epub"

    with pytest.raises(ValueError, match="qualification_asset_not_configured"):
        readiness.select_qualification_asset(asset_id="", manifest_path=manifest)
    with pytest.raises(ValueError, match="qualification_requires_single_asset"):
        readiness.select_qualification_asset(asset_id="all", manifest_path=manifest)
    with pytest.raises(ValueError, match="qualification_asset_unknown"):
        readiness.select_qualification_asset(asset_id="missing", manifest_path=manifest)


def test_asset_freshness_accepts_unseen_source() -> None:
    assert (
        readiness.asset_freshness_error(
            existing_books=[{"source_uri": "Other Book.epub", "metadata": {"sha256": "b" * 64}}],
            asset=_asset(),
        )
        == ""
    )


def test_asset_freshness_rejects_existing_filename_or_sha() -> None:
    expected = "qualification_source_not_fresh:fresh-book"
    assert (
        readiness.asset_freshness_error(
            existing_books=[{"source_uri": "/private/Fresh Book.epub"}],
            asset=_asset(),
        )
        == expected
    )
    assert (
        readiness.asset_freshness_error(
            existing_books=[{"source_uri": "renamed.epub", "metadata": {"source_sha256": "A" * 64}}],
            asset=_asset(),
        )
        == expected
    )


def test_modal_provider_requires_complete_persisted_credentials() -> None:
    assert readiness.modal_provider_has_tokens(_modal_row()) is True
    assert readiness.modal_provider_has_tokens({"payload": {"accounts": []}}) is False
    assert (
        readiness.modal_provider_has_tokens(
            {"payload": {"accounts": [{"token_id": "only-id"}]}}
        )
        is False
    )


def test_ollama_readiness_requires_a_usable_key_not_just_a_config_row() -> None:
    summary = {"ollama": {"configured": True, "accounts": [{"label": "member-01", "has_api_key": False}]}}
    assert readiness.ollama_reasoning_ready(summary, environ={}) is False
    assert readiness.ollama_reasoning_ready(summary, environ={"OLLAMA_API_KEY": "env-key"}) is True
    assert readiness.ollama_reasoning_ready(_ready_reasoning(), environ={}) is True


def test_provider_readiness_accepts_current_nine_stage_contract() -> None:
    rows = {name: _modal_row() for name in readiness.REQUIRED_MODAL_PROVIDERS}
    assert (
        readiness.provider_readiness_errors(
            provider_rows=rows,
            reasoning_summary=_ready_reasoning(),
        )
        == []
    )


def test_provider_readiness_reports_missing_modal_and_reasoning_contracts() -> None:
    rows = {
        "modal_xcore_litbank": _modal_row(),
        "modal_comfyui": None,
        "modal_kokoro_tts": {"payload": {"accounts": []}},
    }
    errors = readiness.provider_readiness_errors(
        provider_rows=rows,
        reasoning_summary={
            "ollama": {"configured": True, "accounts": []},
            "mistral": {"configured": False, "has_env_api_key": False},
        },
    )
    assert errors == [
        "provider_not_ready:modal_comfyui",
        "provider_not_ready:modal_kokoro_tts",
        "reasoning_not_ready:ollama",
        "reasoning_not_ready:mistral",
    ]


def test_provider_readiness_accepts_persisted_mistral_key() -> None:
    rows = {name: _modal_row() for name in readiness.REQUIRED_MODAL_PROVIDERS}
    errors = readiness.provider_readiness_errors(
        provider_rows=rows,
        reasoning_summary={
            "ollama": {"configured": True, "accounts": [{"label": "member-01", "has_api_key": True}]},
            "mistral": {"configured": True, "has_env_api_key": False},
        },
    )
    assert errors == []
