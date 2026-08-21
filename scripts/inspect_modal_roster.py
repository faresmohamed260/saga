from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import Any

from integrations.comfyui.token_pool import ModalToken
from integrations.comfyui.workspace_client import app_list, invoke_workflow_catalog, lookup_urls

DEFAULT_APP_NAME = str(os.environ.get("MODAL_COMFYUI_APP_NAME") or "saga-image-runtime").strip()
DEFAULT_VOLUME_NAME = str(os.environ.get("MODAL_COMFYUI_CACHE_VOLUME") or "graduation-comfyui-cache").strip()
OUTPUT_PATH = Path(os.environ.get("SAGA_MODAL_INSPECTION_OUTPUT") or "modal-roster-inspection.json")
MAX_WORKERS = max(1, min(int(os.environ.get("SAGA_MODAL_INSPECTION_WORKERS") or "8"), 16))


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


def _get_json(url: str, timeout: int = 30) -> dict[str, Any]:
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


def _contains_target_app(rows: list[dict[str, Any]], app_name: str) -> bool:
    target = str(app_name or "").strip().lower()
    if not target:
        return False
    for row in rows:
        if not isinstance(row, dict):
            continue
        haystack = " ".join(str(value or "") for value in row.values()).lower()
        if target in haystack:
            return True
    return False


def _token_env(token: ModalToken) -> dict[str, str]:
    env = os.environ.copy()
    env["MODAL_TOKEN_ID"] = token.token_id
    env["MODAL_TOKEN_SECRET"] = token.token_secret
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _parse_last_json_line(output: str) -> Any:
    for line in reversed((output or "").splitlines()):
        candidate = line.strip()
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    raise RuntimeError("Modal subprocess returned no JSON payload")


def _inspect_cache_volume(token: ModalToken, *, timeout: int = 240) -> dict[str, Any]:
    # Read the persistent cache directly through Modal's Volume API. This avoids
    # launching a GPU container or requiring a newly deployed inspection function.
    script = f'''
import json
from pathlib import Path
import modal

MODEL_EXTENSIONS = {{".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf", ".onnx"}}
volume = modal.Volume.from_name({DEFAULT_VOLUME_NAME!r})
entries = volume.listdir("/", recursive=True)
rows = []
for entry in entries:
    path = str(getattr(entry, "path", "") or "")
    suffix = Path(path).suffix.lower()
    keep = suffix in MODEL_EXTENSIONS or path.endswith("weights/prefetch_manifest.json") or (path.startswith("workflows/") and suffix == ".json")
    if not keep:
        continue
    entry_type = getattr(getattr(entry, "type", None), "name", str(getattr(entry, "type", "")))
    rows.append({{
        "path": path,
        "name": Path(path).name,
        "kind": str(entry_type).lower(),
        "size_bytes": int(getattr(entry, "size", 0) or 0),
        "modified_at": int(getattr(entry, "mtime", 0) or 0),
    }})
rows.sort(key=lambda item: item["path"].lower())
print(json.dumps({{"volume_name": {DEFAULT_VOLUME_NAME!r}, "entries": rows}}, ensure_ascii=False))
'''
    result = subprocess.run(
        [sys.executable, "-c", script],
        env=_token_env(token),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "Modal volume inspection failed").strip())
    payload = _parse_last_json_line(result.stdout or "")
    if not isinstance(payload, dict):
        raise RuntimeError("Modal volume inspection returned an unexpected payload")
    return payload


def inspect_token(token: ModalToken) -> dict[str, Any]:
    app_name = token.app_name_override or DEFAULT_APP_NAME
    entry: dict[str, Any] = {
        "label": token.name,
        "app_name": app_name,
        "apps": [],
        "urls": None,
        "health": None,
        "workflow_catalog": None,
        "volume": None,
        "errors": [],
    }

    # Volume inspection is the authoritative source for persistent model/cache
    # contents and is metadata-only/read-only.
    try:
        entry["volume"] = _inspect_cache_volume(token)
    except Exception as exc:  # noqa: BLE001
        entry["errors"].append(f"volume_inspection: {exc}")

    try:
        raw_apps = app_list(token, timeout=60)
        entry["apps"] = _safe_app_summary(raw_apps)
    except Exception as exc:  # noqa: BLE001
        entry["errors"].append(f"app_list: {exc}")
        return entry

    if not _contains_target_app(raw_apps, app_name):
        entry["errors"].append("app_not_deployed: target ComfyUI app was not found in this Modal account")
        return entry

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
        entry["workflow_catalog"] = invoke_workflow_catalog(token, app_name, timeout=180)
    except Exception as exc:  # noqa: BLE001
        entry["errors"].append(f"workflow_catalog: {exc}")

    return entry


def main() -> int:
    tokens = _load_tokens_from_env()
    accounts: list[dict[str, Any] | None] = [None] * len(tokens)

    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(tokens) or 1)) as executor:
        futures = {executor.submit(inspect_token, token): index for index, token in enumerate(tokens)}
        for future in as_completed(futures):
            index = futures[future]
            token = tokens[index]
            try:
                accounts[index] = future.result()
            except Exception as exc:  # noqa: BLE001
                accounts[index] = {
                    "label": token.name,
                    "app_name": token.app_name_override or DEFAULT_APP_NAME,
                    "apps": [],
                    "urls": None,
                    "health": None,
                    "workflow_catalog": None,
                    "volume": None,
                    "errors": [f"inspection: {exc}"],
                }

    report = {
        "account_count": len(tokens),
        "accounts": [item for item in accounts if isinstance(item, dict)],
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # Print only the sanitized report; token IDs/secrets never enter the output.
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
