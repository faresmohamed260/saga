from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODAL_APP_FILE = PROJECT_ROOT / "integrations" / "comfyui" / "modal_app.py"
WORKFLOWS = {
    "character_sheet": PROJECT_ROOT / "integrations" / "comfyui" / "workflows" / "character_sheet_workflow.json",
    "entity_generation": PROJECT_ROOT / "integrations" / "comfyui" / "workflows" / "entity_generation_workflow.json",
}
DEFAULT_APP_NAME = "saga-image-runtime"


def _truthy(value: str | None, *, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _load_roster() -> list[dict[str, str]]:
    raw = str(os.environ.get("SAGA_MODAL_TOKENS_JSON") or "").strip()
    if raw:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"SAGA_MODAL_TOKENS_JSON is not valid JSON: {exc}") from exc
        if not isinstance(payload, list):
            raise SystemExit("SAGA_MODAL_TOKENS_JSON must be a JSON array.")
        rows: list[dict[str, str]] = []
        for index, item in enumerate(payload, start=1):
            if not isinstance(item, dict):
                continue
            token_id = str(item.get("token_id") or "").strip()
            token_secret = str(item.get("token_secret") or "").strip()
            if not token_id or not token_secret:
                continue
            rows.append(
                {
                    "label": str(item.get("label") or item.get("name") or f"member-{index:02d}").strip(),
                    "token_id": token_id,
                    "token_secret": token_secret,
                    "app_name_override": str(item.get("app_name_override") or "").strip(),
                }
            )
        if rows:
            return rows

    token_id = str(os.environ.get("MODAL_TOKEN_ID") or "").strip()
    token_secret = str(os.environ.get("MODAL_TOKEN_SECRET") or "").strip()
    if token_id and token_secret:
        return [
            {
                "label": "default",
                "token_id": token_id,
                "token_secret": token_secret,
                "app_name_override": "",
            }
        ]

    raise SystemExit(
        "No Modal credentials are available. Add repository secret SAGA_MODAL_TOKENS_JSON "
        "(preferred for a roster) or MODAL_TOKEN_ID + MODAL_TOKEN_SECRET."
    )


def _account_env(account: dict[str, str], app_name: str) -> dict[str, str]:
    env = os.environ.copy()
    env["MODAL_TOKEN_ID"] = account["token_id"]
    env["MODAL_TOKEN_SECRET"] = account["token_secret"]
    env["MODAL_COMFYUI_APP_NAME"] = app_name
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    hf_token = str(os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN") or "").strip()
    if hf_token:
        env["HF_TOKEN"] = hf_token
        env["HUGGING_FACE_HUB_TOKEN"] = hf_token
    return env


def _run(command: list[str], *, env: dict[str, str], timeout: int) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        output = (result.stderr or result.stdout or "command failed").strip()
        raise RuntimeError(output)
    return result


def _python_remote(script: str, *, env: dict[str, str], timeout: int) -> dict[str, Any]:
    result = _run([sys.executable, "-c", script], env=env, timeout=timeout)
    output = (result.stdout or "").strip()
    if not output:
        return {}
    # Modal can emit informational lines before the final JSON payload. Parse the last JSON-looking line.
    for line in reversed(output.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        return payload if isinstance(payload, dict) else {"result": payload}
    return {"raw_output": output[-4000:]}


def _deploy(account: dict[str, str], app_name: str) -> None:
    modal_cli = shutil.which("modal")
    if not modal_cli:
        raise SystemExit("Modal CLI was not found. Install modal==1.4.2 before running this script.")
    env = _account_env(account, app_name)
    _run([modal_cli, "deploy", str(MODAL_APP_FILE)], env=env, timeout=3600)


def _sync_workflows(account: dict[str, str], app_name: str) -> dict[str, Any]:
    env = _account_env(account, app_name)
    script = f'''
import json
import modal
from pathlib import Path
payload = {{
    "character_sheet": json.loads(Path({str(WORKFLOWS["character_sheet"])!r}).read_text(encoding="utf-8-sig")),
    "entity_generation": json.loads(Path({str(WORKFLOWS["entity_generation"])!r}).read_text(encoding="utf-8-sig")),
}}
fn = modal.Function.from_name({app_name!r}, "sync_workflows")
print(json.dumps(fn.remote(payload), ensure_ascii=False))
'''
    return _python_remote(script, env=env, timeout=900)


def _prefetch_models(account: dict[str, str], app_name: str, *, force: bool) -> dict[str, Any]:
    env = _account_env(account, app_name)
    script = f'''
import json
import modal
fn = modal.Function.from_name({app_name!r}, "prefetch_models")
print(json.dumps(fn.remote(force={bool(force)}), ensure_ascii=False))
'''
    return _python_remote(script, env=env, timeout=10800)


def _verify(account: dict[str, str], app_name: str) -> dict[str, Any]:
    env = _account_env(account, app_name)
    script = f'''
import json
import modal
worker = modal.Cls.from_name({app_name!r}, "ComfyWorker")
health = modal.Function.from_name({app_name!r}, "health")
print(json.dumps({{
    "api_url": worker().api.get_web_url(),
    "health_url": health.get_web_url(),
}}, ensure_ascii=False))
'''
    return _python_remote(script, env=env, timeout=300)


def main() -> int:
    if not MODAL_APP_FILE.exists():
        raise SystemExit(f"Modal app file not found: {MODAL_APP_FILE}")
    for path in WORKFLOWS.values():
        if not path.exists():
            raise SystemExit(f"Workflow file not found: {path}")

    roster = _load_roster()
    base_app_name = str(os.environ.get("MODAL_COMFYUI_APP_NAME") or DEFAULT_APP_NAME).strip() or DEFAULT_APP_NAME
    do_sync = _truthy(os.environ.get("SAGA_MODAL_SYNC_WORKFLOWS"), default=True)
    do_prefetch = _truthy(os.environ.get("SAGA_MODAL_PREFETCH_MODELS"), default=True)
    force_prefetch = _truthy(os.environ.get("SAGA_MODAL_FORCE_PREFETCH"), default=True)

    print(f"Deploying Modal ComfyUI runtime to {len(roster)} roster account(s).")
    summaries: list[dict[str, Any]] = []
    for index, account in enumerate(roster, start=1):
        label = account["label"]
        app_name = account["app_name_override"] or base_app_name
        print(f"[{index}/{len(roster)}] Deploying account '{label}' as app '{app_name}'...")
        try:
            _deploy(account, app_name)
            summary: dict[str, Any] = {"label": label, "app_name": app_name, "deployed": True}
            if do_sync:
                print(f"[{index}/{len(roster)}] Syncing workflows for '{label}'...")
                summary["workflow_sync"] = _sync_workflows(account, app_name)
            if do_prefetch:
                print(f"[{index}/{len(roster)}] Prefetching model cache for '{label}'...")
                summary["model_prefetch"] = _prefetch_models(account, app_name, force=force_prefetch)
            summary["endpoints"] = _verify(account, app_name)
            summaries.append(summary)
            print(f"[{index}/{len(roster)}] Account '{label}' is ready.")
        except Exception as exc:  # noqa: BLE001
            print(f"::error title=Modal deployment failed::{label}: {exc}")
            summaries.append({"label": label, "app_name": app_name, "deployed": False, "error": str(exc)})

    print(json.dumps({"accounts": summaries}, indent=2, ensure_ascii=False))
    failed = [item for item in summaries if not item.get("deployed")]
    if failed:
        raise SystemExit(f"Modal deployment failed for {len(failed)} of {len(summaries)} roster account(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
