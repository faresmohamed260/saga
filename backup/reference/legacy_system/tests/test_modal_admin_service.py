from __future__ import annotations

from pathlib import Path

from saga.providers.inference_registry import MODAL_COMFYUI_PROVIDER, read_inference_provider_config
from saga.providers.modal_admin_service import bump_provider_runtime_generation
from saga.storage.persistence import SagaSQLiteStore

from integrations.comfyui.token_pool import load_active_token_name, mark_render_success


def test_bump_provider_runtime_generation_updates_config(tmp_path):
    store = SagaSQLiteStore(tmp_path / "saga.sqlite")

    before = read_inference_provider_config(MODAL_COMFYUI_PROVIDER, store=store, mask=False)
    bumped = bump_provider_runtime_generation(MODAL_COMFYUI_PROVIDER, store=store)
    after = read_inference_provider_config(MODAL_COMFYUI_PROVIDER, store=store, mask=False)

    assert int(before.get("runtime_generation") or 0) == 0
    assert int(bumped.get("runtime_generation") or 0) == 1
    assert int(after.get("runtime_generation") or 0) == 1


def test_comfyui_token_state_invalidates_when_runtime_generation_changes(tmp_path):
    state_path = Path(tmp_path) / "comfy_pool_state.json"

    mark_render_success(
        "member-01",
        state_path=state_path,
        warm_ttl_seconds=60,
        api_url="https://old.example/api",
        ui_url="https://old.example/ui",
        health_url="https://old.example/health",
        live_payload={"ready": True},
        app_name="saga-image-runtime",
        runtime_generation=1,
    )

    assert load_active_token_name(
        state_path,
        expected_app_name="saga-image-runtime",
        expected_generation=1,
    ) == "member-01"

    assert load_active_token_name(
        state_path,
        expected_app_name="saga-image-runtime",
        expected_generation=2,
    ) == ""
