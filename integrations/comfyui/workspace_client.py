from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packages.modal_runtime.profiling import record_modal_timing

# These helpers resolve ComfyUI web endpoints inside the selected Modal account
# context so the returned URLs always correspond to that account's deployment.

try:
    from integrations.comfyui.token_pool import ModalToken
except ImportError:  # pragma: no cover
    from token_pool import ModalToken


MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parents[1]
MODAL_APP_FILE = MODULE_DIR / "modal_app.py"
MODAL_EXE = PROJECT_ROOT / "venv" / "Scripts" / "modal.exe"
PYTHON_EXE = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"


@dataclass(frozen=True)
class ModalUrls:
    ui_url: str
    api_url: str
    health_url: str


def _modal_env(token: ModalToken, *, hf_token: str = "") -> dict[str, str]:
    env = os.environ.copy()
    env["MODAL_TOKEN_ID"] = token.token_id
    env["MODAL_TOKEN_SECRET"] = token.token_secret
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    resolved_hf_token = str(hf_token or "").strip()
    if resolved_hf_token:
        env["HF_TOKEN"] = resolved_hf_token
        env["HUGGING_FACE_HUB_TOKEN"] = resolved_hf_token
    return env


def _run(args: list[str], *, token: ModalToken, timeout: int = 300, hf_token: str = "") -> subprocess.CompletedProcess[str]:
    started_at = time.perf_counter()
    result = subprocess.run(
        args,
        env=_modal_env(token, hf_token=hf_token),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    record_modal_timing(
        "modal_cli_subprocess",
        time.perf_counter() - started_at,
        token_name=token.name,
        timeout_seconds=timeout,
        command=args[0] if args else "",
        argument_count=len(args),
        returncode=result.returncode,
    )
    return result


def health_check(token: ModalToken) -> tuple[bool, str]:
    result = _run([str(MODAL_EXE), "app", "list", "--json"], token=token, timeout=120)
    lines = (result.stderr or result.stdout).strip().splitlines()
    return result.returncode == 0, (lines[-1] if lines else "ok")


def app_list(token: ModalToken, *, timeout: int = 120) -> list[dict[str, Any]]:
    result = _run([str(MODAL_EXE), "app", "list", "--json"], token=token, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "modal app list failed")
    return json.loads(result.stdout or "[]")


def month_cost_usd(token: ModalToken) -> float:
    result = _run([str(MODAL_EXE), "billing", "report", "--for", "this month", "--json"], token=token, timeout=180)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "modal billing report failed")
    rows = json.loads(result.stdout or "[]")
    total = 0.0
    for row in rows:
        try:
            total += float(row.get("Cost", "0") or 0)
        except (TypeError, ValueError):
            continue
    return total


def lookup_urls(token: ModalToken, app_name: str, *, hf_token: str = "") -> ModalUrls | None:
    # URL lookup runs inside the target account context so the resolved web
    # endpoints always belong to that account's deployed ComfyUI app.
    started_at = time.perf_counter()
    script = f"""
import json
import modal
worker = modal.Cls.from_name({app_name!r}, "ComfyWorker")
api_url = worker().api.get_web_url()
health = modal.Function.from_name({app_name!r}, "health")
health_url = health.get_web_url()
print(json.dumps({{"ui_url": api_url, "api_url": api_url, "health_url": health_url}}))
"""
    result = _run([str(PYTHON_EXE), "-c", script], token=token, timeout=120, hf_token=hf_token)
    if result.returncode != 0:
        record_modal_timing(
            "modal_endpoint_lookup",
            time.perf_counter() - started_at,
            token_name=token.name,
            app_name=app_name,
            found=False,
            returncode=result.returncode,
        )
        return None
    try:
        payload = json.loads((result.stdout or "").strip())
        urls = ModalUrls(ui_url=payload["ui_url"], api_url=payload["api_url"], health_url=payload["health_url"])
        record_modal_timing(
            "modal_endpoint_lookup",
            time.perf_counter() - started_at,
            token_name=token.name,
            app_name=app_name,
            found=True,
        )
        return urls
    except (KeyError, json.JSONDecodeError):
        record_modal_timing(
            "modal_endpoint_lookup",
            time.perf_counter() - started_at,
            token_name=token.name,
            app_name=app_name,
            found=False,
            parse_failed=True,
        )
        return None


def deploy_app(token: ModalToken, *, hf_token: str = "") -> str:
    result = _run([str(MODAL_EXE), "deploy", str(MODAL_APP_FILE)], token=token, timeout=1800, hf_token=hf_token)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "modal deploy failed")
    return result.stdout + result.stderr


def stop_app(token: ModalToken, app_name: str, *, hf_token: str = "") -> str:
    result = _run([str(MODAL_EXE), "app", "stop", "-y", str(app_name)], token=token, timeout=300, hf_token=hf_token)
    if result.returncode != 0:
        message = result.stderr or result.stdout or f"modal app stop failed for '{app_name}'"
        if "already stopped" not in str(message).lower():
            raise RuntimeError(message)
        return str(message)
    return result.stdout + result.stderr


def invoke_prefetch(token: ModalToken, app_name: str, *, force: bool = False, timeout: int = 7200, hf_token: str = "") -> dict[str, Any]:
    script = f"""
import json
import modal
fn = modal.Function.from_name({app_name!r}, "prefetch_models")
print(json.dumps(fn.remote(force={bool(force)}), ensure_ascii=False))
"""
    result = _run([str(PYTHON_EXE), "-c", script], token=token, timeout=timeout, hf_token=hf_token)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "modal prefetch failed")
    try:
        return json.loads((result.stdout or "").strip())
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse prefetch payload: {(result.stdout or '').strip()}") from exc


def invoke_workflow_catalog(token: ModalToken, app_name: str, *, timeout: int = 300, hf_token: str = "") -> dict[str, Any]:
    script = f"""
import json
import modal
fn = modal.Function.from_name({app_name!r}, "workflow_catalog")
print(json.dumps(fn.remote(), ensure_ascii=False))
"""
    result = _run([str(PYTHON_EXE), "-c", script], token=token, timeout=timeout, hf_token=hf_token)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "modal workflow_catalog failed")
    try:
        return json.loads((result.stdout or "").strip())
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse workflow catalog payload: {(result.stdout or '').strip()}") from exc


def invoke_sync_workflows(
    token: ModalToken,
    app_name: str,
    workflows: dict[str, Any] | None = None,
    *,
    timeout: int = 600,
    hf_token: str = "",
) -> dict[str, Any]:
    payload = json.dumps(workflows if isinstance(workflows, dict) else {}, ensure_ascii=False)
    script = f"""
import json
import modal
fn = modal.Function.from_name({app_name!r}, "sync_workflows")
payload = json.loads({payload!r})
print(json.dumps(fn.remote(payload), ensure_ascii=False))
"""
    result = _run([str(PYTHON_EXE), "-c", script], token=token, timeout=timeout, hf_token=hf_token)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "modal sync_workflows failed")
    try:
        return json.loads((result.stdout or "").strip())
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse workflow sync payload: {(result.stdout or '').strip()}") from exc


def ensure_urls(token: ModalToken, app_name: str, *, hf_token: str = "") -> ModalUrls:
    started_at = time.perf_counter()
    urls = lookup_urls(token, app_name, hf_token=hf_token)
    if urls:
        record_modal_timing(
            "modal_ensure_urls",
            time.perf_counter() - started_at,
            token_name=token.name,
            app_name=app_name,
            deployed_recovery=False,
        )
        return urls
    # Deploy only as a recovery path when the account does not currently expose
    # the expected web endpoints.
    deploy_app(token, hf_token=hf_token)
    urls = lookup_urls(token, app_name, hf_token=hf_token)
    if not urls:
        raise RuntimeError(f"Failed to resolve Modal URLs for token '{token.name}'.")
    record_modal_timing(
        "modal_ensure_urls",
        time.perf_counter() - started_at,
        token_name=token.name,
        app_name=app_name,
        deployed_recovery=True,
    )
    return urls
