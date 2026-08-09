from __future__ import annotations

import io
import json
import os
import sys
import time
from pathlib import Path
from uuid import uuid4

from integrations.comfyui.pool_manager import ModalComfyUIPoolManager
from integrations.comfyui.token_pool import load_tokens
from packages.modal_runtime import clear_modal_provider_config_cache, collect_modal_timings, load_modal_provider_secret_config


def _require_env(name: str) -> str:
    value = str(os.getenv(name, "") or "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _time_call(fn, *args, **kwargs):
    started_at = time.perf_counter()
    value = fn(*args, **kwargs)
    return value, round(time.perf_counter() - started_at, 6)


def _image_metrics(image_bytes: bytes) -> dict[str, object]:
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Pillow is required for live image benchmark metrics.") from exc

    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    extrema = image.getextrema()
    return {
        "width": int(image.width),
        "height": int(image.height),
        "extrema": extrema,
        "is_non_black": any(channel_max > 0 for channel_min, channel_max in extrema),
    }


def _profiled_call(fn, *args, **kwargs) -> tuple[object, float, list[dict[str, object]], dict[str, dict[str, object]]]:
    with collect_modal_timings() as collector:
        value, elapsed_seconds = _time_call(fn, *args, **kwargs)
    events = [
        {
            "phase": event.phase,
            "elapsed_seconds": round(event.elapsed_seconds, 6),
            "metadata": dict(event.metadata),
        }
        for event in collector.events
    ]
    return value, elapsed_seconds, events, collector.summary()


def _with_fallback_bait() -> list:
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
        return load_tokens()
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _render_payload(workflow_mode: str) -> dict[str, object]:
    common = {
        "steps": 4,
        "cfg": 1.2,
        "width": 512,
        "height": 512,
        "workflow_mode": workflow_mode,
    }
    if workflow_mode == "entity_generation":
        return {
            **common,
            "prompt": "Photorealistic ancient stone gate overgrown with ivy in misty morning light, cinematic natural detail, no people.",
            "negative_prompt": "people, human, portrait, illustration, painting, cartoon, anime, CGI, 3D render, blurry, low quality",
            "seed": 314159,
        }
    return {
        **common,
        "prompt": "Photorealistic studio character-sheet photograph of a wizard, three-view layout, white seamless background.",
        "negative_prompt": "illustration, painterly style, anime, CGI, 3D render, extra characters, blurry, low quality",
        "seed": 271828,
    }


def _store_preview(output_dir: Path, name: str, image_bytes: bytes) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"{name}.png"
    target.write_bytes(image_bytes)
    return str(target)


def _render_report(name: str, result: dict[str, object], elapsed_seconds: float, events: list[dict[str, object]], summary: dict[str, dict[str, object]], output_dir: Path) -> dict[str, object]:
    response = dict(result.get("response") or {})
    image_bytes = bytes(response.get("image_bytes") or b"")
    metrics = _image_metrics(image_bytes)
    if not metrics["is_non_black"]:
        raise AssertionError(f"{name} produced a black image.")
    return {
        "token_name": str(result.get("token_name") or "").strip(),
        "elapsed_seconds": elapsed_seconds,
        "request_metrics": dict(response.get("request_metrics") or {}),
        "image_metrics": metrics,
        "timing_events": events,
        "timing_summary": summary,
        "preview_path": _store_preview(output_dir, name, image_bytes),
    }


def run_benchmark() -> dict[str, object]:
    _require_env("SAGA_SUPABASE_DB_URL")
    _require_env("SAGA_SUPABASE_SERVICE_ROLE_KEY")
    _require_env("SAGA_SUPABASE_API_URL")

    run_id = uuid4().hex[:10]
    output_dir = Path("tmp_live_image_runtime_benchmark") / run_id

    clear_modal_provider_config_cache()
    config, config_elapsed = _time_call(load_modal_provider_secret_config, "modal_comfyui")
    if not config.app_name or not config.hf_token or not config.accounts:
        raise RuntimeError("modal_comfyui provider config is incomplete.")

    tokens, token_elapsed = _time_call(_with_fallback_bait)
    if len(tokens) != len(config.accounts):
        raise AssertionError(f"Expected {len(config.accounts)} persisted tokens, got {len(tokens)}.")
    if any(token.name == "env-fallback-only" for token in tokens):
        raise AssertionError("Env fallback token was used instead of persisted tokens.")

    manager, manager_elapsed = _time_call(
        ModalComfyUIPoolManager,
        app_name=config.app_name,
        hf_token=config.hf_token,
        tokens=tokens,
        request_timeout_seconds=900,
    )

    cold_endpoint, cold_endpoint_elapsed, cold_endpoint_events, cold_endpoint_summary = _profiled_call(manager.ensure_live)
    if not bool((cold_endpoint.get("live_payload") or {}).get("ready")):
        raise AssertionError(f"Live endpoint did not report ready state: {cold_endpoint!r}")

    entity_result, entity_elapsed, entity_events, entity_summary = _profiled_call(
        manager.render_via_endpoint,
        cold_endpoint,
        **_render_payload("entity_generation"),
    )

    warm_entity_result, warm_entity_elapsed, warm_entity_events, warm_entity_summary = _profiled_call(
        manager.render_via_endpoint,
        cold_endpoint,
        **_render_payload("entity_generation"),
    )

    warm_manager, warm_manager_elapsed = _time_call(
        ModalComfyUIPoolManager,
        app_name=config.app_name,
        hf_token=config.hf_token,
        tokens=tokens,
        request_timeout_seconds=900,
    )
    warm_endpoint, warm_endpoint_elapsed, warm_endpoint_events, warm_endpoint_summary = _profiled_call(warm_manager.ensure_live)
    character_result, character_elapsed, character_events, character_summary = _profiled_call(
        warm_manager.render_via_endpoint,
        warm_endpoint,
        **_render_payload("character_sheet"),
    )

    benchmark = {
        "provider_name": "modal_comfyui",
        "app_name": config.app_name,
        "account_count": len(config.accounts),
        "has_hf_token": True,
        "bootstrap": {
            "provider_config_load_seconds": config_elapsed,
            "token_pool_load_seconds": token_elapsed,
            "pool_manager_init_seconds": manager_elapsed,
            "warm_pool_manager_init_seconds": warm_manager_elapsed,
        },
        "cold_discovery": {
            "elapsed_seconds": cold_endpoint_elapsed,
            "timing_events": cold_endpoint_events,
            "timing_summary": cold_endpoint_summary,
            "endpoint": {
                "token_name": str(cold_endpoint.get("token_name") or "").strip(),
                "api_url": str(cold_endpoint.get("api_url") or "").strip(),
                "health_url": str(cold_endpoint.get("health_url") or "").strip(),
                "ready": bool((cold_endpoint.get("live_payload") or {}).get("ready")),
            },
        },
        "entity_generation_coldish": _render_report(
            "entity_generation_coldish",
            entity_result,
            entity_elapsed,
            entity_events,
            entity_summary,
            output_dir,
        ),
        "entity_generation_warm": _render_report(
            "entity_generation_warm",
            warm_entity_result,
            warm_entity_elapsed,
            warm_entity_events,
            warm_entity_summary,
            output_dir,
        ),
        "warm_endpoint_reuse": {
            "elapsed_seconds": warm_endpoint_elapsed,
            "timing_events": warm_endpoint_events,
            "timing_summary": warm_endpoint_summary,
            "endpoint": {
                "token_name": str(warm_endpoint.get("token_name") or "").strip(),
                "api_url": str(warm_endpoint.get("api_url") or "").strip(),
                "health_url": str(warm_endpoint.get("health_url") or "").strip(),
                "ready": bool((warm_endpoint.get("live_payload") or {}).get("ready")),
            },
        },
        "character_sheet_warm": _render_report(
            "character_sheet_warm",
            character_result,
            character_elapsed,
            character_events,
            character_summary,
            output_dir,
        ),
    }

    report_path = output_dir / "benchmark.json"
    report_path.write_text(json.dumps(benchmark, ensure_ascii=False, indent=2), encoding="utf-8")
    benchmark["report_path"] = str(report_path)
    return benchmark


def main() -> int:
    payload = run_benchmark()
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REAL_IMAGE_RUNTIME_BENCHMARK_FAILED: {exc}", file=sys.stderr)
        raise
