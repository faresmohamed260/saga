"""Workspace-scoped Modal URL resolution helpers for Kokoro deployments."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

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
    api_url: str
    health_url: str


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


def lookup_urls(token: ModalToken, app_name: str) -> ModalUrls | None:
    script = f"""
import json
import modal
cls = modal.Cls.from_name({app_name!r}, "KokoroTTSService")
print(json.dumps({{"api_url": cls().api.get_web_url(), "health_url": cls().health.get_web_url()}}))
"""
    result = _run([str(PYTHON_EXE), "-c", script], token=token, timeout=120)
    if result.returncode != 0:
        return None
    try:
        payload = json.loads((result.stdout or "").strip())
        return ModalUrls(api_url=payload["api_url"], health_url=payload["health_url"])
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
