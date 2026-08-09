from __future__ import annotations

import json
import sys
from pathlib import Path

from packages.modal_runtime import save_modal_provider_secret_config
from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client
from packages.reasoning_runtime import import_general_compute_accounts_from_file, import_ollama_accounts_from_file


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _persistence_client():
    profile = PersistenceProfile(
        name="runtime-secret-rehome",
        provider="supabase",
        mode="supabase_postgres",
        application_name="saga-runtime-secret-rehome",
    )
    client = create_persistence_client(
        config=PersistenceRuntimeConfig(profile=profile),
        profile=profile,
    )
    client.initialize()
    return client


def run() -> dict[str, object]:
    client = _persistence_client()
    results: dict[str, object] = {"imports": []}

    ollama_file = PROJECT_ROOT / "deploy" / "ollama" / "accounts.local.json"
    if ollama_file.exists():
        results["imports"].append(import_ollama_accounts_from_file(client, file_path=ollama_file))

    general_compute_file = PROJECT_ROOT / "deploy" / "general_compute" / "accounts.local.json"
    if general_compute_file.exists():
        results["imports"].append(import_general_compute_accounts_from_file(client, file_path=general_compute_file))

    modal_tokens_file = PROJECT_ROOT / "tmp" / "pr6-review" / "integrations" / "comfyui" / "modal_tokens.json"
    gateway_config_file = PROJECT_ROOT / "tmp" / "pr6-review" / "integrations" / "comfyui" / "gateway_config.json"
    if modal_tokens_file.exists():
        tokens_payload = json.loads(modal_tokens_file.read_text(encoding="utf-8"))
        gateway_payload = {}
        if gateway_config_file.exists():
            gateway_payload = json.loads(gateway_config_file.read_text(encoding="utf-8"))
        saved = save_modal_provider_secret_config(
            "modal_comfyui",
            {
                "app_name": "saga-image-runtime",
                "api_url": str(gateway_payload.get("default_backend") or "").strip(),
                "ui_url": str(gateway_payload.get("local_ui_url") or "").strip(),
                "health_url": str(gateway_payload.get("default_backend") or "").strip(),
                "accounts": [
                    {
                        "label": str(item.get("name") or "").strip(),
                        "token_id": str(item.get("token_id") or "").strip(),
                        "token_secret": str(item.get("token_secret") or "").strip(),
                    }
                    for item in list(tokens_payload.get("tokens") or [])
                    if isinstance(item, dict) and str(item.get("name") or "").strip()
                ],
            },
        )
        results["imports"].append(
            {
                "provider_name": "modal_comfyui",
                "accounts_imported": len(saved.get("accounts") or []),
                "has_hf_token": bool(saved.get("has_hf_token")),
            }
        )

    return results


def main() -> int:
    payload = run()
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"RUNTIME_SECRET_REHOME_FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
