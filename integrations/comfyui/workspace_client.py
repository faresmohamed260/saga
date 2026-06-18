from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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


def _modal_env(token: ModalToken) -> dict[str, str]:
    env = os.environ.copy()
    env["MODAL_TOKEN_ID"] = token.token_id
    env["MODAL_TOKEN_SECRET"] = token.token_secret
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _run(args: list[str], *, token: ModalToken, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        env=_modal_env(token),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def health_check(token: ModalToken) -> tuple[bool, str]:
    result = _run([str(MODAL_EXE), "app", "list", "--json"], token=token, timeout=120)
    lines = (result.stderr or result.stdout).strip().splitlines()
    return result.returncode == 0, (lines[-1] if lines else "ok")


def app_list(token: ModalToken) -> list[dict[str, Any]]:
    result = _run([str(MODAL_EXE), "app", "list", "--json"], token=token, timeout=120)
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


def lookup_urls(token: ModalToken, app_name: str) -> ModalUrls | None:
    script = f"""
import json
import modal
ui = modal.Function.from_name({app_name!r}, "ui")
cls = modal.Cls.from_name({app_name!r}, "ComfyService")
print(json.dumps({{"ui_url": ui.get_web_url(), "api_url": cls().api.get_web_url()}}))
"""
    result = _run([str(PYTHON_EXE), "-c", script], token=token, timeout=120)
    if result.returncode != 0:
        return None
    try:
        payload = json.loads((result.stdout or "").strip())
        return ModalUrls(ui_url=payload["ui_url"], api_url=payload["api_url"])
    except (KeyError, json.JSONDecodeError):
        return None


def deploy_app(token: ModalToken) -> str:
    result = _run([str(MODAL_EXE), "deploy", str(MODAL_APP_FILE)], token=token, timeout=1800)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "modal deploy failed")
    return result.stdout + result.stderr


def ensure_urls(token: ModalToken, app_name: str) -> ModalUrls:
    urls = lookup_urls(token, app_name)
    if urls:
        return urls
    deploy_app(token)
    urls = lookup_urls(token, app_name)
    if not urls:
        raise RuntimeError(f"Failed to resolve Modal URLs for token '{token.name}'.")
    return urls
