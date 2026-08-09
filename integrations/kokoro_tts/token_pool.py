"""Persisted token rotation state for Kokoro provider accounts."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from packages.modal_runtime import load_modal_account_secrets
from packages.modal_runtime.state import load_runtime_state, save_runtime_state, stamp_runtime_metadata


DEFAULT_STATE_PATH: Path | None = None
DEFAULT_WARM_TTL_SECONDS = 60
PROVIDER_NAME = "modal_kokoro_tts"


@dataclass(frozen=True)
class ModalToken:
    name: str
    token_id: str
    token_secret: str


def load_tokens() -> list[ModalToken]:
    persisted = []
    try:
        persisted = load_modal_account_secrets(PROVIDER_NAME)
    except Exception:
        persisted = []
    if persisted:
        return [
            ModalToken(
                name=str(item.get("label") or "").strip(),
                token_id=str(item.get("token_id") or "").strip(),
                token_secret=str(item.get("token_secret") or "").strip(),
            )
            for item in persisted
            if str(item.get("label") or "").strip() and str(item.get("token_id") or "").strip() and str(item.get("token_secret") or "").strip()
        ]
    if str(os.getenv("SAGA_MODAL_ALLOW_ENV_FALLBACK") or "").strip().lower() not in {"1", "true", "yes"}:
        return []
    payload = str(os.getenv("SAGA_MODAL_TOKENS_JSON") or "").strip()
    if payload:
        try:
            raw = json.loads(payload)
        except json.JSONDecodeError:
            raw = []
        if isinstance(raw, list):
            tokens: list[ModalToken] = []
            for idx, item in enumerate(raw, start=1):
                if not isinstance(item, dict):
                    continue
                token_id = str(item.get("token_id") or "").strip()
                token_secret = str(item.get("token_secret") or "").strip()
                if not token_id or not token_secret:
                    continue
                tokens.append(
                    ModalToken(
                        name=str(item.get("label") or item.get("name") or f"member-{idx:02d}").strip(),
                        token_id=token_id,
                        token_secret=token_secret,
                    )
                )
            if tokens:
                return tokens
    token_id = str(os.getenv("MODAL_TOKEN_ID") or "").strip()
    token_secret = str(os.getenv("MODAL_TOKEN_SECRET") or "").strip()
    if token_id and token_secret:
        return [ModalToken(name="default", token_id=token_id, token_secret=token_secret)]
    return []


def _load_state(
    state_path: Path | None = DEFAULT_STATE_PATH,
    *,
    expected_app_name: str = "",
    expected_generation: int = 0,
) -> dict:
    return load_runtime_state(
        state_path,
        expected_app_name=expected_app_name,
        expected_generation=expected_generation,
        provider_name=PROVIDER_NAME,
    )


def _save_state(payload: dict, state_path: Path | None = DEFAULT_STATE_PATH) -> None:
    try:
        save_runtime_state(payload, state_path, provider_name=PROVIDER_NAME)
    except OSError:
        # Pool state helps token rotation and observability, but it should never abort a live TTS render.
        return


def load_start_index(state_path: Path | None = DEFAULT_STATE_PATH, *, expected_app_name: str = "", expected_generation: int = 0) -> int:
    raw = _load_state(state_path, expected_app_name=expected_app_name, expected_generation=expected_generation)
    return max(int(raw.get("next_index", 0)), 0)


def save_next_index(
    next_index: int,
    state_path: Path | None = DEFAULT_STATE_PATH,
    *,
    app_name: str = "",
    runtime_generation: int = 0,
) -> None:
    payload = _load_state(state_path, expected_app_name=app_name, expected_generation=runtime_generation)
    if app_name or runtime_generation:
        payload = stamp_runtime_metadata(payload, app_name=app_name, runtime_generation=runtime_generation)
    payload["next_index"] = max(next_index, 0)
    _save_state(payload, state_path)


def load_token_stats(state_path: Path | None = DEFAULT_STATE_PATH, *, expected_app_name: str = "", expected_generation: int = 0) -> dict[str, dict]:
    raw = _load_state(state_path, expected_app_name=expected_app_name, expected_generation=expected_generation)
    stats = raw.get("token_stats", {})
    return stats if isinstance(stats, dict) else {}


def load_active_token_name(state_path: Path | None = DEFAULT_STATE_PATH, *, expected_app_name: str = "", expected_generation: int = 0) -> str:
    raw = _load_state(state_path, expected_app_name=expected_app_name, expected_generation=expected_generation)
    return str(raw.get("active_token_name") or "").strip()


def update_token_stat(
    token_name: str,
    *,
    state_path: Path | None = DEFAULT_STATE_PATH,
    health_ok: bool | None = None,
    live_ok: bool | None = None,
    warm_until: int | None = None,
    last_error: str | None = None,
    api_url: str | None = None,
    health_url: str | None = None,
    app_name: str | None = None,
    live_payload: dict | None = None,
    last_successful_request: dict | None = None,
    runtime_generation: int = 0,
) -> None:
    payload = _load_state(state_path, expected_app_name=str(app_name or ""), expected_generation=runtime_generation)
    payload = stamp_runtime_metadata(payload, app_name=str(app_name or ""), runtime_generation=runtime_generation)
    stats = payload.setdefault("token_stats", {})
    token_stats = stats.setdefault(token_name, {})
    now = int(time.time())
    token_stats["last_seen_at"] = now
    if health_ok is not None:
        token_stats["last_health_ok"] = bool(health_ok)
        token_stats["last_health_checked_at"] = now
    if live_ok is not None:
        token_stats["last_live_ok"] = bool(live_ok)
        token_stats["last_live_checked_at"] = now
    if warm_until is not None:
        token_stats["warm_until"] = int(warm_until)
    if last_error is not None:
        token_stats["last_error"] = last_error
        token_stats["last_error_at"] = now
    if api_url is not None:
        token_stats["api_url"] = api_url
    if health_url is not None:
        token_stats["health_url"] = health_url
    if app_name is not None:
        token_stats["app_name"] = app_name
    if live_payload is not None:
        token_stats["live_payload"] = live_payload
        token_stats["live_payload_checked_at"] = now
    if last_successful_request is not None:
        token_stats["last_successful_request"] = last_successful_request
        token_stats["last_successful_request_at"] = now
    _save_state(payload, state_path)


def mark_live_success(
    token_name: str,
    *,
    api_url: str,
    health_url: str,
    app_name: str,
    live_payload: dict,
    state_path: Path | None = DEFAULT_STATE_PATH,
    warm_ttl_seconds: int = DEFAULT_WARM_TTL_SECONDS,
    runtime_generation: int = 0,
    last_successful_request: dict | None = None,
) -> None:
    payload = _load_state(state_path, expected_app_name=app_name, expected_generation=runtime_generation)
    payload = stamp_runtime_metadata(payload, app_name=app_name, runtime_generation=runtime_generation)
    payload["active_api_url"] = api_url
    payload["active_health_url"] = health_url
    payload["active_token_name"] = token_name
    payload["active_app_name"] = app_name
    _save_state(payload, state_path)
    update_token_stat(
        token_name,
        state_path=state_path,
        health_ok=True,
        live_ok=True,
        warm_until=int(time.time()) + warm_ttl_seconds,
        last_error="",
        api_url=api_url,
        health_url=health_url,
        app_name=app_name,
        live_payload=live_payload,
        last_successful_request=last_successful_request,
        runtime_generation=runtime_generation,
    )


def is_token_warm(token_name: str, *, state_path: Path | None = DEFAULT_STATE_PATH, expected_app_name: str = "", expected_generation: int = 0) -> bool:
    stats = load_token_stats(state_path, expected_app_name=expected_app_name, expected_generation=expected_generation)
    token_stats = stats.get(token_name, {})
    return int(token_stats.get("warm_until", 0)) > int(time.time())


def rotate_from(tokens: Iterable[ModalToken], start_index: int) -> list[tuple[int, ModalToken]]:
    token_list = list(tokens)
    if not token_list:
        return []
    offset = start_index % len(token_list)
    return [
        ((offset + step) % len(token_list), token_list[(offset + step) % len(token_list)])
        for step in range(len(token_list))
    ]


def rotate_prefer_warm(
    tokens: Iterable[ModalToken],
    start_index: int,
    *,
    state_path: Path | None = DEFAULT_STATE_PATH,
    expected_app_name: str = "",
    expected_generation: int = 0,
) -> list[tuple[int, ModalToken]]:
    ordered = rotate_from(tokens, start_index)
    warm: list[tuple[int, ModalToken]] = []
    cold: list[tuple[int, ModalToken]] = []
    for item in ordered:
        if is_token_warm(item[1].name, state_path=state_path, expected_app_name=expected_app_name, expected_generation=expected_generation):
            warm.append(item)
        else:
            cold.append(item)
    return warm + cold
