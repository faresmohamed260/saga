from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import asdict
from pathlib import Path
from typing import Any

from integrations.comfyui.token_pool import ModalToken
from integrations.comfyui.workspace_client import app_list, invoke_workflow_catalog, lookup_urls

DEFAULT_APP_NAME = str(os.environ.get("MODAL_COMFYUI_APP_NAME") or "saga-image-runtime").strip()
OUTPUT_PATH = Path(os.environ.get("SAGA_MODAL_INSPECTION_OUTPUT") or "modal-roster-inspection.json")


def _load_tokens_from_env() -> list[ModalToken]:
    payload = str(os.environ.get("SAGA_MODAL_TOKENS_JSON") or "").strip()
    tokens: list[ModalToken] = []
    if payload:
        raw = json.loads(payload)
        if not isinstance(raw, list):
            raise RuntimeError("SAGA_MODAL_TOKENS_JSON must be a JSON array")
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
                    app_name_override=str(item.get("app_name_override") or "").strip(),
                )
            )
    if tokens:
        return tokens

    token_id = str(os.environ.get("MODAL_TOKEN_ID") or "").strip()
    token_secret = str(os.environ.get("MODAL_TOKEN_SECRET") or "").strip()
    if token_id and token_secret:
        return [ModalToken(name="default", token_id=token_id, token_secret=token_secret)]
    raise RuntimeError("No Modal credentials are available to the inspection workflow")


def _get_json(url: str, timeout: int = 60) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "saga-modal-inspector/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
        return payload if isinstance(payload, dict) else {"value": payload}


def _safe_app_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        result.append(
            {
                key: row.get(key)
                for key in ("App ID", "Description", "State", "Created at", "Stopped at", "Name")
                if key in row
            }
        )
    return result


def inspect_token(token: ModalToken) -> dict[str, Any]:
    app_name = token.app_name_override or DEFAULT_APP_NAME
    entry: dict[str, Any] = {
        "label": token.name,
        "app_name": app_name,
        "apps": [],
        "urls": None,
        "health": None,
        "workflow_catalog": None,
        "errors": [],
    }

    try:
        entry["apps"] = _safe_app_summary(app_list(token, timeout=120))
    except Exception as exc:  # noqa: BLE001
        entry["errors"].append(f"app_list: {exc}")

    try:
        urls = lookup_urls(token, app_name)
        if urls is None:
            entry["errors"].append("lookup_urls: no deployed endpoints found")
            return entry
        entry["urls"] = asdict(urls)
    except Exception as exc:  # noqa: BLE001
        entry["errors"].append(f"lookup_urls: {exc}")
        return entry

    try:
        entry["health"] = _get_json(entry["urls"]["health_url"])
    except Exception as exc:  # noqa: BLE001
        entry["errors"].append(f"health: {exc}")

    try:
        entry["workflow_catalog"] = invoke_workflow_catalog(token, app_name, timeout=300)
    except Exception as exc:  # noqa: BLE001
        entry["errors"].append(f"workflow_catalog: {exc}")

    return entry


def main() -> int:
    tokens = _load_tokens_from_env()
    report = {
        "account_count": len(tokens),
        "accounts": [inspect_token(token) for token in tokens],
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # Print only the sanitized report; token IDs/secrets never enter the output.
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
