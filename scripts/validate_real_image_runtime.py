from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

from integrations.comfyui.pool_manager import ModalComfyUIPoolManager
from integrations.comfyui.token_pool import load_tokens
from packages.modal_runtime import clear_modal_provider_config_cache, load_modal_provider_secret_config


def _require_env(name: str) -> str:
    value = str(os.getenv(name, "") or "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _image_metrics(image_bytes: bytes) -> dict[str, object]:
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Pillow is required for live image validation metrics.") from exc

    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    extrema = image.getextrema()
    non_black = any(channel_max > 0 for channel_min, channel_max in extrema)
    return {
        "width": int(image.width),
        "height": int(image.height),
        "extrema": extrema,
        "is_non_black": non_black,
    }


def _save_preview(output_dir: Path, name: str, image_bytes: bytes) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"{name}.png"
    target.write_bytes(image_bytes)
    return str(target)


def run_validation() -> dict[str, object]:
    _require_env("SAGA_SUPABASE_DB_URL")
    _require_env("SAGA_SUPABASE_SERVICE_ROLE_KEY")
    _require_env("SAGA_SUPABASE_API_URL")

    clear_modal_provider_config_cache()
    config = load_modal_provider_secret_config("modal_comfyui")
    if not config.app_name:
        raise RuntimeError("modal_comfyui provider config is missing app_name.")
    if not config.hf_token:
        raise RuntimeError("modal_comfyui provider config is missing HF token.")
    if not config.accounts:
        raise RuntimeError("modal_comfyui provider config is missing account pool entries.")

    original_env = {
        "SAGA_MODAL_ALLOW_ENV_FALLBACK": os.environ.get("SAGA_MODAL_ALLOW_ENV_FALLBACK"),
        "SAGA_MODAL_TOKENS_JSON": os.environ.get("SAGA_MODAL_TOKENS_JSON"),
        "MODAL_TOKEN_ID": os.environ.get("MODAL_TOKEN_ID"),
        "MODAL_TOKEN_SECRET": os.environ.get("MODAL_TOKEN_SECRET"),
    }
    os.environ["SAGA_MODAL_ALLOW_ENV_FALLBACK"] = "1"
    os.environ["SAGA_MODAL_TOKENS_JSON"] = json.dumps(
        [{"label": "env-fallback-only", "token_id": "env-token-id", "token_secret": "env-token-secret"}],
        ensure_ascii=False,
    )
    os.environ["MODAL_TOKEN_ID"] = "env-direct-token-id"
    os.environ["MODAL_TOKEN_SECRET"] = "env-direct-token-secret"
    try:
        tokens = load_tokens()
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    if len(tokens) != len(config.accounts):
        raise AssertionError(
            f"Persisted modal account pool was not the source of truth. "
            f"Expected {len(config.accounts)} tokens, got {len(tokens)}."
        )
    if any(token.name == "env-fallback-only" for token in tokens):
        raise AssertionError("Env fallback token was used instead of persisted modal provider config.")

    manager = ModalComfyUIPoolManager(tokens=tokens, request_timeout_seconds=900)
    if manager.app_name != config.app_name:
        raise AssertionError(f"Pool manager app_name drifted from persisted config: {manager.app_name!r} != {config.app_name!r}")
    if manager.hf_token != config.hf_token:
        raise AssertionError("Pool manager HF token was not sourced from persisted config.")

    live_endpoint = manager.ensure_live()
    if str(live_endpoint.get("token_name") or "").strip() == "":
        raise AssertionError("Live endpoint resolution returned no token_name.")
    if not str(live_endpoint.get("api_url") or "").strip():
        raise AssertionError("Live endpoint resolution returned no api_url.")
    if not bool((live_endpoint.get("live_payload") or {}).get("ready")):
        raise AssertionError(f"Live endpoint did not report ready state: {live_endpoint!r}")

    run_id = uuid4().hex[:10]
    output_dir = Path("tmp_live_image_runtime_test") / run_id

    entity_result = manager.render_via_endpoint(
        live_endpoint,
        prompt="Photorealistic ancient stone gate overgrown with ivy in misty morning light, cinematic natural detail, no people.",
        negative_prompt="people, human, portrait, illustration, painting, cartoon, anime, CGI, 3D render, blurry, low quality",
        seed=314159,
        steps=4,
        cfg=1.2,
        width=512,
        height=512,
        workflow_mode="entity_generation",
    )
    entity_bytes = bytes((entity_result.get("response") or {}).get("image_bytes") or b"")
    if not entity_bytes:
        raise AssertionError("Entity render returned no image bytes.")
    entity_metrics = _image_metrics(entity_bytes)
    if not entity_metrics["is_non_black"]:
        raise AssertionError(f"Entity render produced a black image: {entity_metrics}")

    character_result = manager.render_via_endpoint(
        live_endpoint,
        prompt="Photorealistic studio character-sheet photograph of a wizard, three-view layout, white seamless background.",
        negative_prompt="illustration, painterly style, anime, CGI, 3D render, extra characters, blurry, low quality",
        seed=271828,
        steps=4,
        cfg=1.2,
        width=512,
        height=512,
        workflow_mode="character_sheet",
    )
    character_bytes = bytes((character_result.get("response") or {}).get("image_bytes") or b"")
    if not character_bytes:
        raise AssertionError("Character render returned no image bytes.")
    character_metrics = _image_metrics(character_bytes)
    if not character_metrics["is_non_black"]:
        raise AssertionError(f"Character render produced a black image: {character_metrics}")

    return {
        "provider_name": "modal_comfyui",
        "app_name": manager.app_name,
        "persisted_account_count": len(config.accounts),
        "loaded_account_count": len(tokens),
        "has_hf_token": True,
        "live_endpoint": {
            "token_name": str(live_endpoint.get("token_name") or "").strip(),
            "api_url": str(live_endpoint.get("api_url") or "").strip(),
            "health_url": str(live_endpoint.get("health_url") or "").strip(),
            "ready": bool((live_endpoint.get("live_payload") or {}).get("ready")),
        },
        "entity_generation": {
            "token_name": str(entity_result.get("token_name") or "").strip(),
            "image_metrics": entity_metrics,
            "preview_path": _save_preview(output_dir, "entity_generation", entity_bytes),
        },
        "character_sheet": {
            "token_name": str(character_result.get("token_name") or "").strip(),
            "image_metrics": character_metrics,
            "preview_path": _save_preview(output_dir, "character_sheet", character_bytes),
        },
    }


def main() -> int:
    result = run_validation()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REAL_IMAGE_RUNTIME_VALIDATION_FAILED: {exc}", file=sys.stderr)
        raise
