from __future__ import annotations

import os
from typing import Any, Callable

from packages.reasoning_runtime.client import ReasoningRuntimeClient
from packages.reasoning_runtime.contracts import ReasoningClient
from packages.reasoning_runtime.factory import create_reasoning_client
from packages.reasoning_runtime.models import (
    GeneralComputeAccount,
    OllamaAccount,
    ReasoningProfile,
    ReasoningRuntimeConfig,
)
from saga.storage.persistence import SagaRelationalStore


OLLAMA_PROVIDER = "ollama"
GENERAL_COMPUTE_PROVIDER = "general_compute"

MODE_DEEPSEEK = ReasoningRuntimeClient.MODE_DEEPSEEK
MODE_GPT_OSS = ReasoningRuntimeClient.MODE_GPT_OSS
MODE_CODEX = "codex"
MODE_GENERAL_COMPUTE = ReasoningRuntimeClient.MODE_GENERAL_COMPUTE
MODE_MISTRAL = ReasoningRuntimeClient.MODE_MISTRAL
MODE_GEMINI = ReasoningRuntimeClient.MODE_GEMINI


def build_reasoning_runtime_config(*, store: SagaRelationalStore | None = None) -> ReasoningRuntimeConfig:
    relational_store = store or SagaRelationalStore()
    ollama_payload = relational_store.get_provider_config(OLLAMA_PROVIDER) or {}
    general_compute_payload = relational_store.get_provider_config(GENERAL_COMPUTE_PROVIDER) or {}
    ollama_active_index = int(ollama_payload.get("active_index", 0) if isinstance(ollama_payload, dict) else 0)
    general_compute_active_index = int(
        general_compute_payload.get("active_index", 0) if isinstance(general_compute_payload, dict) else 0
    )
    general_compute_last_request_index = int(
        general_compute_payload.get("last_request_index", -1) if isinstance(general_compute_payload, dict) else -1
    )
    return ReasoningRuntimeConfig(
        ollama_accounts=[
            OllamaAccount(
                label=str(item.get("label") or f"ollama-{index + 1}"),
                api_key=str(item.get("api_key") or "").strip(),
                email=str(item.get("email") or "").strip(),
                password=str(item.get("password") or "").strip(),
                metadata=dict(item.get("metadata") or {}) if isinstance(item.get("metadata"), dict) else {},
            )
            for index, item in enumerate(ollama_payload.get("accounts") or [])
            if isinstance(item, dict) and (str(item.get("api_key") or "").strip() or (str(item.get("email") or "").strip() and str(item.get("password") or "").strip()))
        ],
        general_compute_accounts=[
            GeneralComputeAccount(
                label=str(item.get("label") or f"general-compute-{index + 1}"),
                api_key=str(item.get("api_key") or "").strip(),
                limits=dict(item.get("limits") or {}) if isinstance(item.get("limits"), dict) else {},
                usage=dict(item.get("usage") or {}) if isinstance(item.get("usage"), dict) else {},
                metadata=dict(item.get("metadata") or {}) if isinstance(item.get("metadata"), dict) else {},
            )
            for index, item in enumerate(general_compute_payload.get("accounts") or [])
            if isinstance(item, dict) and str(item.get("api_key") or "").strip()
        ],
        ollama_active_index=max(0, ollama_active_index),
        general_compute_active_index=max(0, general_compute_active_index),
        general_compute_last_request_index=max(-1, general_compute_last_request_index),
        mistral_api_key=str(os.getenv("MISTRAL_API_KEY") or "").strip(),
        gemini_api_key=str(os.getenv("GEMINI_API_KEY") or "").strip(),
    )


def create_runtime_client(
    *,
    mode: str = MODE_GPT_OSS,
    store: SagaRelationalStore | None = None,
    model_override: str = "",
    timeout: int = 180,
    max_retries: int = 2,
    base_delay: float = 0.0,
    allow_account_rotation: bool = True,
    allow_cross_provider_fallback: bool = False,
) -> ReasoningClient:
    requested_mode = str(mode or MODE_GPT_OSS).strip().lower() or MODE_GPT_OSS
    resolved_mode = MODE_GENERAL_COMPUTE if requested_mode == MODE_CODEX else requested_mode
    config = build_reasoning_runtime_config(store=store)
    profile = ReasoningProfile(
        name=f"runtime_{resolved_mode}",
        mode=resolved_mode,
        timeout_seconds=max(30, int(timeout)),
        max_retries=max(1, int(max_retries)),
        base_delay_seconds=max(0.0, float(base_delay)),
        allow_account_rotation=bool(allow_account_rotation),
        model_override=str(model_override or "").strip(),
    )
    config.profiles[profile.name] = profile
    client = create_reasoning_client(profile_name=profile.name, config=config, profile=profile)
    client.allow_cross_provider_fallback = bool(allow_cross_provider_fallback)
    return client


def build_analysis_reasoning_client(shared_config: dict[str, Any], *, store: SagaRelationalStore | None = None) -> ReasoningClient:
    provider_mode = str(shared_config.get("analysis_provider_mode") or "same_provider_rotating").strip().lower()
    return create_runtime_client(
        mode=str(shared_config.get("analysis_model") or MODE_GPT_OSS).strip() or MODE_GPT_OSS,
        store=store,
        timeout=max(30, int(shared_config.get("llm_timeout_seconds") or shared_config.get("analysis_timeout_seconds") or 120)),
        max_retries=max(1, int(shared_config.get("llm_max_retries") or shared_config.get("analysis_max_retries") or 2)),
        allow_account_rotation=(provider_mode == "same_provider_rotating"),
        allow_cross_provider_fallback=(provider_mode == "cross_provider_fallback"),
    )


def build_decoder_reasoning_bundle(
    *,
    provider: str = "",
    store: SagaRelationalStore | None = None,
    provider_ready: Callable[[str], bool] | None = None,
) -> dict[str, ReasoningClient]:
    requested = str(provider or "").strip().lower()
    ready = provider_ready or (lambda provider_name: False)
    if requested == "general_compute":
        shared = create_runtime_client(
            mode=MODE_GENERAL_COMPUTE,
            store=store,
            allow_account_rotation=False,
            allow_cross_provider_fallback=False,
        )
        return {"primary": shared, "planner": shared, "prose": shared}
    primary = create_runtime_client(
        mode=MODE_GPT_OSS,
        store=store,
        allow_account_rotation=False,
        allow_cross_provider_fallback=False,
    )
    prose = create_runtime_client(
        mode=MODE_GPT_OSS,
        store=store,
        allow_account_rotation=False,
        allow_cross_provider_fallback=False,
    )
    planner = primary
    if requested != "ollama" and ready("general_compute"):
        planner = create_runtime_client(mode=MODE_GENERAL_COMPUTE, store=store)
    return {"primary": primary, "planner": planner, "prose": prose}


def probe_runtime_mode_access(
    mode: str,
    *,
    store: SagaRelationalStore | None = None,
    model_override: str = "",
    timeout: int = 30,
    max_retries: int = 1,
    allow_account_rotation: bool = False,
    allow_cross_provider_fallback: bool = False,
) -> dict[str, Any]:
    client = create_runtime_client(
        mode=mode,
        store=store,
        model_override=model_override,
        timeout=timeout,
        max_retries=max_retries,
        allow_account_rotation=allow_account_rotation,
        allow_cross_provider_fallback=allow_cross_provider_fallback,
    )
    try:
        payload = client.generate_json('Reply with exactly {"ok": true}', strict=True, max_tokens=32)
    except Exception as exc:
        return {
            "status": "error",
            "detail": str(exc),
            "model": client.resolved_model_name(),
            "provider": client.provider_name(),
        }
    if isinstance(payload, dict) and payload.get("ok") is True:
        return {
            "status": "ok",
            "model": client.resolved_model_name(),
            "provider": client.provider_name(),
            "metadata": client.last_request_metadata(),
        }
    if isinstance(payload, dict) and payload.get("error"):
        return {
            "status": "error",
            "detail": str(payload.get("last_error") or payload.get("error")),
            "model": client.resolved_model_name(),
            "provider": client.provider_name(),
            "payload": payload,
        }
    return {
        "status": "error",
        "detail": "Unexpected probe payload",
        "model": client.resolved_model_name(),
        "provider": client.provider_name(),
        "payload": payload,
    }
