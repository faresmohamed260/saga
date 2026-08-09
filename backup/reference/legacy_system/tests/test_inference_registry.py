from __future__ import annotations

from saga.providers.inference_registry import (
    COREF_CAPABILITY,
    IMAGE_CAPABILITY,
    MODAL_COMFYUI_PROVIDER,
    MODAL_KOKORO_PROVIDER,
    MODAL_XCORE_PROVIDER,
    SPEECH_CAPABILITY,
    active_provider_name_for_capability,
    modal_tokens_from_provider_payload,
    read_inference_provider_config,
    read_inference_selection,
    save_inference_provider_config,
    save_inference_selection,
)
from integrations.comfyui.token_pool import ModalToken
from saga.storage.persistence import SagaSQLiteStore


def test_inference_provider_config_persists_modal_accounts(tmp_path):
    store = SagaSQLiteStore(tmp_path / "saga.sqlite")

    payload = save_inference_provider_config(
        MODAL_KOKORO_PROVIDER,
        {
            "provider_name": MODAL_KOKORO_PROVIDER,
            "app_name": "custom-kokoro-app",
            "request_timeout_seconds": 360,
            "accounts": [
                {
                    "label": "member-01",
                    "token_id": "token-id-01",
                    "token_secret": "token-secret-01",
                }
            ],
        },
        store=store,
    )

    assert payload["provider_name"] == MODAL_KOKORO_PROVIDER
    assert payload["app_name"] == "custom-kokoro-app"
    assert payload["accounts"][0]["has_token_id"] is True
    assert payload["accounts"][0]["has_token_secret"] is True

    stored = store.get_provider_config(MODAL_KOKORO_PROVIDER)
    assert stored is not None
    assert stored["accounts"][0]["api_key"] == "token-id-01"
    assert stored["accounts"][0]["password"] == "token-secret-01"


def test_inference_selection_defaults_to_expected_provider(tmp_path):
    store = SagaSQLiteStore(tmp_path / "saga.sqlite")

    assert active_provider_name_for_capability(SPEECH_CAPABILITY, store=store) == MODAL_KOKORO_PROVIDER
    assert active_provider_name_for_capability(IMAGE_CAPABILITY, store=store) == MODAL_COMFYUI_PROVIDER
    assert active_provider_name_for_capability(COREF_CAPABILITY, store=store) == MODAL_XCORE_PROVIDER


def test_inference_selection_persists_active_provider(tmp_path):
    store = SagaSQLiteStore(tmp_path / "saga.sqlite")

    save_inference_selection(SPEECH_CAPABILITY, MODAL_KOKORO_PROVIDER, store=store)
    selection = read_inference_selection(SPEECH_CAPABILITY, store=store)

    assert selection["active_provider"] == MODAL_KOKORO_PROVIDER


def test_read_inference_provider_config_masks_token_secret(tmp_path):
    store = SagaSQLiteStore(tmp_path / "saga.sqlite")
    save_inference_provider_config(
        MODAL_COMFYUI_PROVIDER,
        {
            "provider_name": MODAL_COMFYUI_PROVIDER,
            "accounts": [
                {
                    "label": "member-01",
                    "token_id": "token-id-01",
                    "token_secret": "token-secret-01",
                }
            ],
        },
        store=store,
    )

    masked = read_inference_provider_config(MODAL_COMFYUI_PROVIDER, store=store, mask=True)

    assert masked["accounts"][0]["token_secret"] == ""
    assert masked["accounts"][0]["has_token_secret"] is True


def test_inference_provider_config_persists_and_masks_hf_token(tmp_path):
    store = SagaSQLiteStore(tmp_path / "saga.sqlite")

    save_inference_provider_config(
        MODAL_COMFYUI_PROVIDER,
        {
            "provider_name": MODAL_COMFYUI_PROVIDER,
            "hf_token": "hf_test_1234567890",
        },
        store=store,
    )

    raw = read_inference_provider_config(MODAL_COMFYUI_PROVIDER, store=store, mask=False)
    masked = read_inference_provider_config(MODAL_COMFYUI_PROVIDER, store=store, mask=True)

    assert raw["hf_token"] == "hf_test_1234567890"
    assert raw["has_hf_token"] is True
    assert masked["has_hf_token"] is True
    assert masked["hf_token"].startswith("hf_t")
    assert masked["hf_token"] != "hf_test_1234567890"


def test_inference_provider_config_preserves_existing_hf_token_when_blank_payload_is_saved(tmp_path):
    store = SagaSQLiteStore(tmp_path / "saga.sqlite")

    save_inference_provider_config(
        MODAL_COMFYUI_PROVIDER,
        {
            "provider_name": MODAL_COMFYUI_PROVIDER,
            "hf_token": "hf_existing_token",
        },
        store=store,
    )
    save_inference_provider_config(
        MODAL_COMFYUI_PROVIDER,
        {
            "provider_name": MODAL_COMFYUI_PROVIDER,
            "app_name": "custom-comfyui-app",
            "hf_token": "",
        },
        store=store,
    )

    raw = read_inference_provider_config(MODAL_COMFYUI_PROVIDER, store=store, mask=False)
    assert raw["app_name"] == "custom-comfyui-app"
    assert raw["hf_token"] == "hf_existing_token"


def test_modal_tokens_from_provider_payload_preserves_app_name_override():
    tokens = modal_tokens_from_provider_payload(
        {
            "accounts": [
                {
                    "label": "member-10",
                    "token_id": "token-id-10",
                    "token_secret": "token-secret-10",
                    "app_name_override": "saga-image-runtime-member-10",
                }
            ]
        },
        ModalToken,
    )

    assert len(tokens) == 1
    assert tokens[0].name == "member-10"
    assert tokens[0].app_name_override == "saga-image-runtime-member-10"
