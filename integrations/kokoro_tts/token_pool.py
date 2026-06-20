from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_TOKENS_PATH = MODULE_DIR.parent / "comfyui" / "modal_tokens.json"
DEFAULT_STATE_PATH = MODULE_DIR / "pool_state.json"
DEFAULT_WARM_TTL_SECONDS = 60


@dataclass(frozen=True)
class ModalToken:
    name: str
    token_id: str
    token_secret: str


def _load_state(state_path: Path = DEFAULT_STATE_PATH) -> dict:
    if not state_path.exists():
        return {}
    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return raw if isinstance(raw, dict) else {}


def _save_state(payload: dict, state_path: Path = DEFAULT_STATE_PATH) -> None:
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except OSError:
        # Pool state helps token rotation and observability, but it should never abort a live TTS render.
        return


def load_tokens(tokens_path: Path = DEFAULT_TOKENS_PATH) -> list[ModalToken]:
    if not tokens_path.exists():
        raise FileNotFoundError(
            f"Token file not found: {tokens_path}. Copy modal_tokens.example.json to modal_tokens.json first."
        )
    raw = json.loads(tokens_path.read_text(encoding="utf-8"))
    items = raw.get("tokens")
    if not isinstance(items, list) or not items:
        raise ValueError(f"{tokens_path} must contain a non-empty 'tokens' list.")
    tokens: list[ModalToken] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"Token entry #{index + 1} must be an object.")
        name = str(item.get("name") or f"token-{index + 1}")
        token_id = str(item.get("token_id") or "").strip()
        token_secret = str(item.get("token_secret") or "").strip()
        if not token_id or not token_secret:
            raise ValueError(f"Token entry '{name}' is missing token_id or token_secret.")
        tokens.append(ModalToken(name=name, token_id=token_id, token_secret=token_secret))
    return tokens


def load_start_index(state_path: Path = DEFAULT_STATE_PATH) -> int:
    raw = _load_state(state_path)
    return max(int(raw.get("next_index", 0)), 0)


def save_next_index(next_index: int, state_path: Path = DEFAULT_STATE_PATH) -> None:
    payload = _load_state(state_path)
    payload["next_index"] = max(next_index, 0)
    _save_state(payload, state_path)


def load_token_stats(state_path: Path = DEFAULT_STATE_PATH) -> dict[str, dict]:
    raw = _load_state(state_path)
    stats = raw.get("token_stats", {})
    return stats if isinstance(stats, dict) else {}


def load_active_token_name(state_path: Path = DEFAULT_STATE_PATH) -> str:
    raw = _load_state(state_path)
    return str(raw.get("active_token_name") or "").strip()


def update_token_stat(
    token_name: str,
    *,
    state_path: Path = DEFAULT_STATE_PATH,
    health_ok: bool | None = None,
    live_ok: bool | None = None,
    warm_until: int | None = None,
    last_error: str | None = None,
    api_url: str | None = None,
    health_url: str | None = None,
    app_name: str | None = None,
    live_payload: dict | None = None,
) -> None:
    payload = _load_state(state_path)
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
    _save_state(payload, state_path)


def mark_live_success(
    token_name: str,
    *,
    api_url: str,
    health_url: str,
    app_name: str,
    live_payload: dict,
    state_path: Path = DEFAULT_STATE_PATH,
    warm_ttl_seconds: int = DEFAULT_WARM_TTL_SECONDS,
) -> None:
    payload = _load_state(state_path)
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
    )


def is_token_warm(token_name: str, *, state_path: Path = DEFAULT_STATE_PATH) -> bool:
    stats = load_token_stats(state_path)
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
    state_path: Path = DEFAULT_STATE_PATH,
) -> list[tuple[int, ModalToken]]:
    ordered = rotate_from(tokens, start_index)
    warm: list[tuple[int, ModalToken]] = []
    cold: list[tuple[int, ModalToken]] = []
    for item in ordered:
        if is_token_warm(item[1].name, state_path=state_path):
            warm.append(item)
        else:
            cold.append(item)
    return warm + cold
