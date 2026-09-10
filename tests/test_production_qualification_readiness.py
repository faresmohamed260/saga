from __future__ import annotations

from scripts import check_production_qualification_readiness as readiness


def _ready_reasoning() -> dict[str, object]:
    return {
        "ollama": {"configured": True},
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


def test_static_readiness_accepts_explicit_runtime_database_url() -> None:
    env = {
        "SAGA_RUNTIME_DB_URL": "postgresql+psycopg://example.invalid/postgres",
        "SAGA_SUPABASE_API_URL": "https://example.supabase.co",
        "SAGA_SUPABASE_SERVICE_ROLE_KEY": "service-role",
    }
    assert readiness.static_readiness_errors(env) == []


def test_static_readiness_accepts_component_database_configuration() -> None:
    env = {
        "SAGA_SUPABASE_DB_USER": "postgres.project",
        "SAGA_SUPABASE_DB_PASSWORD": "password",
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "service-role",
    }
    assert readiness.static_readiness_errors(env) == []


def test_static_readiness_reports_missing_contracts_without_values() -> None:
    assert readiness.static_readiness_errors({}) == [
        "supabase_database_not_configured",
        "supabase_api_not_configured",
        "supabase_service_role_not_configured",
    ]


def test_modal_provider_requires_complete_persisted_credentials() -> None:
    assert readiness.modal_provider_has_tokens(_modal_row()) is True
    assert readiness.modal_provider_has_tokens({"payload": {"accounts": []}}) is False
    assert (
        readiness.modal_provider_has_tokens(
            {"payload": {"accounts": [{"token_id": "only-id"}]}}
        )
        is False
    )


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
            "ollama": {"configured": False},
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
            "ollama": {"configured": True},
            "mistral": {"configured": True, "has_env_api_key": False},
        },
    )
    assert errors == []
