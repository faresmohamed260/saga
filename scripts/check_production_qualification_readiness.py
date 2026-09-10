"""Fail-fast readiness checks for clean-source S.A.G.A. production qualification.

This preflight is intentionally non-destructive. It validates the configuration needed
before protected-book processing begins and reports only secret-presence/provider-state
metadata. Secret values and provider payloads are never printed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from packages.observability_runtime import CostRate
from packages.persistence_runtime import (
    PersistenceProfile,
    PersistenceRuntimeConfig,
    create_persistence_client,
)
from packages.persistence_runtime.database_url import build_database_url_from_env
from packages.reasoning_runtime.provider_config import summarize_reasoning_provider_configs

REQUIRED_MODAL_PROVIDERS = (
    "modal_xcore_litbank",
    "modal_comfyui",
    "modal_kokoro_tts",
)

# The current nine-stage qualification meters gpt_oss/retrieval as ``ollama``,
# Mistral reasoning/vision/transcription as ``mistral``, and Modal endpoint work
# (identity, visual rendering, TTS) as ``modal``. Provider-wide fallback rates make
# qualification pricing robust to account rotation and model-level overrides; more
# specific model/account rates may still override them at runtime.
REQUIRED_PRICED_PROVIDERS = ("ollama", "mistral", "modal")
DEFAULT_MANIFEST_PATH = Path("docs/operations/protected_assets.manifest.json")


def _value(environ: Mapping[str, str], *names: str) -> str:
    for name in names:
        value = str(environ.get(name, "") or "").strip()
        if value:
            return value
    return ""


def validate_cost_rates(environ: Mapping[str, str]) -> str:
    """Return an empty string when qualification pricing has safe fallback coverage."""

    raw = _value(environ, "SAGA_PROVIDER_COST_RATES_JSON")
    if not raw:
        return "provider_cost_rates_not_configured"
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return "provider_cost_rates_invalid"
    if not isinstance(payload, list) or not payload:
        return "provider_cost_rates_invalid"
    try:
        rates = [CostRate.model_validate(item) for item in payload]
    except Exception:  # noqa: BLE001 - convert schema detail into bounded diagnostic
        return "provider_cost_rates_invalid"
    if any(not str(rate.pricing_version or "").strip() for rate in rates):
        return "provider_cost_rates_invalid"

    fallback_providers = {
        str(rate.provider or "").strip()
        for rate in rates
        if not str(rate.account_alias or "").strip()
        and not str(rate.model or "").strip()
    }
    missing = [
        provider
        for provider in REQUIRED_PRICED_PROVIDERS
        if provider not in fallback_providers
    ]
    if missing:
        return "provider_cost_rate_fallback_missing:" + ",".join(missing)
    return ""


def static_readiness_errors(environ: Mapping[str, str]) -> list[str]:
    errors: list[str] = []
    explicit_db = _value(
        environ,
        "SAGA_RUNTIME_DB_URL",
        "SAGA_SUPABASE_DB_URL",
        "SUPABASE_DB_URL",
        "DATABASE_URL",
    )
    db_host = _value(environ, "SAGA_SUPABASE_DB_HOST", "SUPABASE_DB_HOST")
    db_user = _value(environ, "SAGA_SUPABASE_DB_USER", "SUPABASE_DB_USER")
    db_tenant = _value(
        environ,
        "SAGA_SUPABASE_POOLER_TENANT_ID",
        "SUPABASE_POOLER_TENANT_ID",
        "POOLER_TENANT_ID",
    )
    db_password = _value(
        environ,
        "SAGA_SUPABASE_DB_PASSWORD",
        "SUPABASE_DB_PASSWORD",
        "POSTGRES_PASSWORD",
    )
    if not explicit_db and not (db_host and (db_user or db_tenant) and db_password):
        errors.append("supabase_database_not_configured")

    if not _value(
        environ,
        "SAGA_SUPABASE_API_URL",
        "SAGA_SUPABASE_URL",
        "SUPABASE_API_URL",
        "SUPABASE_URL",
    ):
        errors.append("supabase_api_not_configured")

    if not _value(
        environ,
        "SAGA_SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
    ):
        errors.append("supabase_service_role_not_configured")

    cost_rate_error = validate_cost_rates(environ)
    if cost_rate_error:
        errors.append(cost_rate_error)
    return errors


def select_qualification_asset(
    *,
    asset_id: str,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> dict[str, Any]:
    requested = str(asset_id or "").strip()
    if not requested:
        raise ValueError("qualification_asset_not_configured")
    if requested == "all":
        raise ValueError("qualification_requires_single_asset")

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("qualification_asset_manifest_invalid")
    matches = [
        dict(item)
        for item in payload.get("assets", [])
        if isinstance(item, Mapping) and str(item.get("id") or "").strip() == requested
    ]
    if len(matches) != 1:
        raise ValueError("qualification_asset_unknown")

    asset = matches[0]
    filename = str(asset.get("filename") or "").strip()
    sha256 = str(asset.get("sha256") or "").strip().lower()
    if not filename or "\n" in filename or "\r" in filename:
        raise ValueError("qualification_asset_manifest_invalid")
    if len(sha256) != 64 or any(char not in "0123456789abcdef" for char in sha256):
        raise ValueError("qualification_asset_manifest_invalid")
    return asset


def asset_freshness_error(
    *,
    existing_books: Sequence[Mapping[str, Any]],
    asset: Mapping[str, Any],
) -> str:
    """Mirror the qualifier freshness guard without exposing persisted book rows."""

    asset_id = str(asset.get("id") or "").strip()
    filename = str(asset.get("filename") or "").strip().casefold()
    sha256 = str(asset.get("sha256") or "").strip().casefold()
    for item in existing_books:
        source_uri = str(item.get("source_uri") or "").casefold()
        serialized = json.dumps(dict(item), sort_keys=True, default=str).casefold()
        if (filename and filename in source_uri) or (sha256 and sha256 in serialized):
            return f"qualification_source_not_fresh:{asset_id}"
    return ""


def modal_provider_has_tokens(row: Mapping[str, Any] | None) -> bool:
    payload = dict((row or {}).get("payload") or {})
    for account in payload.get("accounts") or []:
        if not isinstance(account, Mapping):
            continue
        if str(account.get("token_id") or "").strip() and str(
            account.get("token_secret") or ""
        ).strip():
            return True
    return False


def provider_readiness_errors(
    *,
    provider_rows: Mapping[str, Mapping[str, Any] | None],
    reasoning_summary: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    for provider_name in REQUIRED_MODAL_PROVIDERS:
        if not modal_provider_has_tokens(provider_rows.get(provider_name)):
            errors.append(f"provider_not_ready:{provider_name}")

    ollama = dict(reasoning_summary.get("ollama") or {})
    if not bool(ollama.get("configured")):
        errors.append("reasoning_not_ready:ollama")

    mistral = dict(reasoning_summary.get("mistral") or {})
    if not bool(mistral.get("configured")) and not bool(
        mistral.get("has_env_api_key")
    ):
        errors.append("reasoning_not_ready:mistral")
    return errors


def _runtime_database_url() -> str:
    return str(os.getenv("SAGA_RUNTIME_DB_URL") or "").strip() or build_database_url_from_env()


def run_readiness_check(
    *,
    asset_id: str,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> dict[str, Any]:
    static_errors = static_readiness_errors(os.environ)
    if static_errors:
        return {
            "status": "not_ready",
            "errors": static_errors,
            "checked": {
                "database": True,
                "supabase_api": True,
                "supabase_service_role": True,
                "provider_cost_rates": True,
                "source_freshness": False,
                "persisted_providers": False,
            },
        }

    try:
        asset = select_qualification_asset(asset_id=asset_id, manifest_path=manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        error_code = str(exc) if isinstance(exc, ValueError) and str(exc) else "qualification_asset_manifest_invalid"
        return {
            "status": "not_ready",
            "errors": [error_code],
            "checked": {
                "database": True,
                "supabase_api": True,
                "supabase_service_role": True,
                "provider_cost_rates": True,
                "source_freshness": False,
                "persisted_providers": False,
            },
        }

    database_url = _runtime_database_url()
    api_url = _value(
        os.environ,
        "SAGA_SUPABASE_API_URL",
        "SAGA_SUPABASE_URL",
        "SUPABASE_API_URL",
        "SUPABASE_URL",
    )
    service_role = _value(
        os.environ,
        "SAGA_SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
    )
    profile = PersistenceProfile(
        name="production-qualification-readiness",
        provider="supabase",
        mode="supabase_postgres",
        database_url=database_url,
        application_name="saga-production-qualification-readiness",
    )
    client = create_persistence_client(
        profile=profile,
        config=PersistenceRuntimeConfig(
            profile=profile,
            supabase_api_url=api_url,
            supabase_service_role_key=service_role,
        ),
    )
    try:
        # Production initialization validates the existing migration/schema contract;
        # unlike test-harness mode it does not create tables.
        client.initialize()
        freshness_error = asset_freshness_error(
            existing_books=client.library.list_books(limit=10000),
            asset=asset,
        )
        if freshness_error:
            return {
                "status": "not_ready",
                "errors": [freshness_error],
                "checked": {
                    "database": True,
                    "supabase_api": True,
                    "supabase_service_role": True,
                    "provider_cost_rates": True,
                    "source_freshness": True,
                    "persisted_providers": False,
                },
                "asset": {
                    "asset_id": str(asset.get("id") or ""),
                    "fresh": False,
                },
            }

        provider_rows = {
            name: client.provider_configs.get_provider_config(name)
            for name in REQUIRED_MODAL_PROVIDERS
        }
        reasoning_summary = summarize_reasoning_provider_configs(client)
        provider_errors = provider_readiness_errors(
            provider_rows=provider_rows,
            reasoning_summary=reasoning_summary,
        )
        return {
            "status": "ready" if not provider_errors else "not_ready",
            "errors": provider_errors,
            "checked": {
                "database": True,
                "supabase_api": True,
                "supabase_service_role": True,
                "provider_cost_rates": True,
                "source_freshness": True,
                "persisted_providers": True,
            },
            "asset": {
                "asset_id": str(asset.get("id") or ""),
                "fresh": True,
            },
            "providers": {
                name: {"has_modal_credentials": modal_provider_has_tokens(row)}
                for name, row in provider_rows.items()
            },
            "reasoning": {
                "ollama_configured": bool(
                    dict(reasoning_summary.get("ollama") or {}).get("configured")
                ),
                "mistral_configured": bool(
                    dict(reasoning_summary.get("mistral") or {}).get("configured")
                )
                or bool(
                    dict(reasoning_summary.get("mistral") or {}).get("has_env_api_key")
                ),
            },
        }
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--asset-id",
        default=str(os.getenv("SAGA_QUALIFICATION_ASSET_ID") or "").strip(),
    )
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH))
    args = parser.parse_args()
    try:
        report = run_readiness_check(
            asset_id=args.asset_id,
            manifest_path=Path(args.manifest),
        )
    except Exception as exc:  # noqa: BLE001
        report = {
            "status": "error",
            "errors": ["persistence_readiness_check_failed"],
            "error_type": type(exc).__name__,
        }
        print(json.dumps(report, sort_keys=True), file=sys.stderr)
        return 3

    print(json.dumps(report, sort_keys=True))
    return 0 if report.get("status") == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
