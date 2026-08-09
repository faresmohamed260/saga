from __future__ import annotations

import mimetypes
import os
from functools import lru_cache
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client
from packages.persistence_runtime.database_url import build_database_url_from_env
from packages.modal_runtime import (
    clear_modal_provider_config_cache,
    load_modal_provider_secret_config,
    save_modal_provider_secret_config,
    summarize_modal_provider_secret_config,
)
from packages.reasoning_runtime import summarize_reasoning_provider_configs
from packages.deployment_runtime import check_readiness
from packages.observability_runtime import UsageBudgetPolicy, UsageGovernanceRuntime


APP_TITLE = "S.A.G.A. Runtime API"
APP_HOST = str(os.getenv("SAGA_RUNTIME_HOST") or "127.0.0.1").strip() or "127.0.0.1"
APP_PORT = int(os.getenv("SAGA_RUNTIME_PORT") or "8675")


def _create_persistence_client():
    settings = (
        str(os.getenv("SAGA_RUNTIME_DB_URL") or "").strip() or build_database_url_from_env(),
        str(os.getenv("SAGA_RUNTIME_DB_MODE") or "supabase_postgres").strip() or "supabase_postgres",
        str(os.getenv("SAGA_RUNTIME_LOCAL_STORAGE_ROOT") or "").strip() or "analysis_outputs/unified_storage",
    )
    return _cached_persistence_client(*settings)


@lru_cache(maxsize=8)
def _cached_persistence_client(database_url: str, runtime_mode: str, local_storage_root_dir: str):
    profile = PersistenceProfile(
        name="dashboard-runtime",
        provider="supabase",
        mode=runtime_mode,
        database_url=database_url,
        application_name="saga-dashboard-runtime",
        local_storage_root_dir=local_storage_root_dir,
    )
    client = create_persistence_client(
        config=PersistenceRuntimeConfig(profile=profile),
        profile=profile,
    )
    client.initialize()
    return client


def _database_summary(database_url: str) -> dict:
    value = str(database_url or "").strip()
    if not value:
        return {"configured": False, "scheme": "", "host": ""}
    parsed = urlsplit(value)
    return {
        "configured": True,
        "scheme": str(parsed.scheme or "").strip(),
        "host": str(parsed.hostname or "").strip(),
    }


def _modal_provider_payload(client) -> dict:
    clear_modal_provider_config_cache()
    config = summarize_modal_provider_secret_config(load_modal_provider_secret_config("modal_comfyui"))
    operational = client.provider_configs.get_provider_operational_state("modal_comfyui")
    statuses = []
    for row in operational.get("statuses") or []:
        status = dict(row.get("status") or {})
        if status.get("last_request_ok") is True:
            probe_status = "ok"
            detail = "Last runtime request succeeded."
        elif status.get("last_health_ok") is True:
            probe_status = "healthy"
            detail = "Health check succeeded."
        elif str(status.get("last_error") or "").strip():
            probe_status = "error"
            detail = "Provider has a recorded runtime error."
        else:
            probe_status = "unknown"
            detail = "No live status recorded yet."
        statuses.append(
            {
                "label": row.get("label"),
                "probe_status": probe_status,
                "detail": detail,
            }
        )
    return {
        "provider_name": "modal_comfyui",
        "config": config,
        "statuses": statuses,
        "runtime_state": operational.get("runtime_state") or {},
    }


def _reasoning_provider_payloads(client) -> dict:
    summary = summarize_reasoning_provider_configs(client)
    payloads = {}
    for provider_name, item in summary.items():
        statuses = []
        for account in item.get("accounts") or []:
            statuses.append(
                {
                    "label": account.get("label"),
                    "probe_status": "configured" if account.get("has_api_key") else "missing_secret",
                    "detail": "Account is configured in the reasoning runtime." if account.get("has_api_key") else "Account is missing an API key.",
                }
            )
        if provider_name in {"mistral", "gemini"} and item.get("has_env_api_key"):
            statuses.append(
                {
                    "label": provider_name,
                    "probe_status": "configured",
                    "detail": "API key is available through runtime environment configuration.",
                }
            )
        payloads[provider_name] = {"provider_name": provider_name, "config": item, "statuses": statuses}
    return payloads


app = FastAPI(title=APP_TITLE)
_cors_origins = [item.strip() for item in str(os.getenv("SAGA_CORS_ORIGINS") or "http://127.0.0.1:5173,http://localhost:5173").split(",") if item.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials="*" not in _cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/runtime/state")
def runtime_state():
    client = _create_persistence_client()
    return {
        "runtime": {
            "name": APP_TITLE,
            "provider": client.provider_name(),
            "database": _database_summary(client.database_url),
        },
        "artifacts": {
            "buckets": {
                "source_documents": "source-documents",
                "generated_images": "generated-images",
                "identity_exports": "identity-exports",
                "story_exports": "story-exports",
                "audio_outputs": "audio-outputs",
                "runtime_reports": "runtime-reports",
            }
        },
    }


@app.get("/runtime/artifacts/object")
def runtime_artifact_object(
    bucket_name: str = Query(..., min_length=1),
    object_path: str = Query(..., min_length=1),
):
    client = _create_persistence_client()
    try:
        info = client.objects.get_object_info(bucket_name, object_path)
        data = client.objects.download_bytes(bucket_name, object_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    media_type = str(info.get("content_type") or "").strip()
    if not media_type:
        media_type, _ = mimetypes.guess_type(object_path)
    return Response(content=data, media_type=media_type or "application/octet-stream")


@app.get("/runtime/providers/status")
def runtime_provider_statuses(refresh: int = Query(0, ge=0, le=1)):
    del refresh
    client = _create_persistence_client()
    return {
        "providers": {
            "modal_comfyui": _modal_provider_payload(client),
            **_reasoning_provider_payloads(client),
        }
    }


@app.get("/runtime/usage/summary")
def runtime_usage_summary(
    run_id: str = Query("", max_length=160),
    provider: str = Query("", max_length=120),
    account_alias: str = Query("", max_length=160),
    since_ms: int = Query(0, ge=0),
):
    client = _create_persistence_client()
    runtime = UsageGovernanceRuntime(store=client.usage)
    return {
        "summary": runtime.summary(
            run_id=run_id, provider=provider, account_alias=account_alias, since_ms=since_ms,
        ),
        "by_provider": runtime.breakdown(
            group_by="provider", run_id=run_id, provider=provider, account_alias=account_alias, since_ms=since_ms,
        ),
        "by_account": runtime.breakdown(
            group_by="account_alias", run_id=run_id, provider=provider, account_alias=account_alias, since_ms=since_ms,
        ),
        "by_model": runtime.breakdown(
            group_by="model", run_id=run_id, provider=provider, account_alias=account_alias, since_ms=since_ms,
        ),
        "by_stage": runtime.breakdown(
            group_by="stage", run_id=run_id, provider=provider, account_alias=account_alias, since_ms=since_ms,
        ),
        "policies": client.usage.list_policies(enabled=True),
    }


@app.post("/runtime/usage/budgets/{policy_id}")
def configure_runtime_usage_budget(policy_id: str, payload: dict):
    client = _create_persistence_client()
    try:
        policy = UsageBudgetPolicy.model_validate({**dict(payload or {}), "policy_id": policy_id})
        saved = UsageGovernanceRuntime(store=client.usage, observation_store=client.observability).configure_policy(policy)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"policy": saved}


@app.get("/runtime/providers/{provider_name}")
def runtime_provider_state(provider_name: str):
    client = _create_persistence_client()
    payload = client.provider_configs.get_provider_operational_state(provider_name)
    if not bool(payload.get("found")):
        raise HTTPException(status_code=404, detail=f"Unknown provider '{provider_name}'.")
    return payload


@app.get("/runtime/inference/providers/{provider_name}")
def runtime_inference_provider(provider_name: str):
    client = _create_persistence_client()
    normalized = str(provider_name or "").strip().lower()
    if normalized == "modal_comfyui":
        clear_modal_provider_config_cache()
        return {"provider": summarize_modal_provider_secret_config(load_modal_provider_secret_config(normalized))}
    if normalized in {"ollama", "general_compute", "mistral", "gemini"}:
        return {"provider": _reasoning_provider_payloads(client).get(normalized, {"provider_name": normalized})}
    raise HTTPException(status_code=404, detail=f"Unknown inference provider '{provider_name}'.")


@app.post("/runtime/inference/providers/{provider_name}")
def save_runtime_inference_provider(provider_name: str, payload: dict):
    normalized = str(provider_name or "").strip().lower()
    if normalized != "modal_comfyui":
        raise HTTPException(status_code=404, detail=f"Unknown inference provider '{provider_name}'.")
    try:
        clear_modal_provider_config_cache()
        saved = save_modal_provider_secret_config(normalized, dict(payload or {}))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"provider": saved}

@app.get("/live")
def liveness():
    return JSONResponse({"ok": True, "service": "dashboard-runtime", "release_id": str(os.getenv("SAGA_RELEASE_ID") or "")})


@app.get("/ready")
def readiness():
    try:
        client = _create_persistence_client()
        report = check_readiness(persistence=client, service="dashboard-runtime", release_id=str(os.getenv("SAGA_RELEASE_ID") or ""))
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(status_code=503, content={"ready": False, "service": "dashboard-runtime", "error": f"{type(exc).__name__}: {str(exc)[:240]}"})
    return JSONResponse(status_code=200 if report.ready else 503, content=report.model_dump())


@app.get("/health")
def health():
    return liveness()


def main() -> None:
    import uvicorn

    uvicorn.run(app, host=APP_HOST, port=APP_PORT, log_level="info")


if __name__ == "__main__":
    main()
