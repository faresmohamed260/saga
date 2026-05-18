"""Local-only Ollama cloud credential rotation helpers.

This module intentionally uses a git-ignored local config file so production
operators can store credential pools without committing them to the repo.
It supports either browser-signin credentials or direct Ollama Cloud API keys.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_ACCOUNTS_FILE = Path("deploy/ollama/accounts.local.json")


@dataclass
class OllamaAccount:
    label: str
    email: str = ""
    password: str = ""
    api_key: str = ""


class OllamaAccountRotator:
    """Rotate among locally configured Ollama accounts after rate limits."""

    def __init__(self, config_path: str | Path | None = None) -> None:
        self.config_path = Path(config_path or DEFAULT_ACCOUNTS_FILE)

    def has_accounts(self) -> bool:
        data = self._load_data()
        return bool(self._accounts(data))

    def active_account(self) -> OllamaAccount | None:
        data = self._load_data()
        accounts = self._accounts(data)
        if not accounts:
            return None
        index = int(data.get("active_index", 0)) % len(accounts)
        return accounts[index]

    def active_api_key(self) -> str:
        account = self.active_account()
        return account.api_key if account and account.api_key else ""

    def rotate_for_model(self, *, mode: str, model_name: str, probe_callable) -> Dict[str, Any]:
        data = self._load_data()
        accounts = self._accounts(data)
        if not accounts:
            return {"status": "unconfigured", "detail": f"No Ollama accounts configured in {self.config_path}"}

        start_index = int(data.get("active_index", 0)) % len(accounts)
        for offset in range(1, len(accounts) + 1):
            next_index = (start_index + offset) % len(accounts)
            account = accounts[next_index]
            try:
                signin_result = self._activate_account(account)
                if signin_result.get("status") != "ok":
                    continue
                probe_result = probe_callable(mode, model_name, account.api_key or None)
            except Exception as exc:  # pragma: no cover - defensive runtime guard
                probe_result = {"status": "error", "detail": repr(exc)}
            if probe_result.get("status") == "ok":
                data["active_index"] = next_index
                self._save_data(data)
                return {
                    "status": "rotated",
                    "label": account.label,
                    "email": account.email,
                    "active_index": next_index,
                }
        return {
            "status": "exhausted",
            "detail": f"Unable to rotate Ollama accounts for model {model_name}.",
        }

    def _activate_account(self, account: OllamaAccount) -> Dict[str, Any]:
        if account.api_key:
            return {"status": "ok", "label": account.label, "mode": "api_key"}
        return self._signin(account)

    def _signin(self, account: OllamaAccount) -> Dict[str, Any]:
        try:
            subprocess.run(
                ["ollama", "signout"],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            result = subprocess.run(
                ["ollama", "signin"],
                input=f"{account.email}\n{account.password}\n",
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except Exception as exc:  # pragma: no cover - defensive runtime guard
            return {"status": "error", "detail": repr(exc), "label": account.label}

        output = "\n".join(
            part.strip() for part in [result.stdout or "", result.stderr or ""] if part.strip()
        ).lower()
        if result.returncode == 0 and ("signed in" in output or "already signed in" in output or not output):
            return {"status": "ok", "label": account.label}
        return {
            "status": "error",
            "label": account.label,
            "detail": output or f"signin_failed_exit_{result.returncode}",
        }

    def _load_data(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            return {"active_index": 0, "accounts": []}
        return json.loads(self.config_path.read_text(encoding="utf-8"))

    def _save_data(self, payload: Dict[str, Any]) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _accounts(self, payload: Dict[str, Any]) -> List[OllamaAccount]:
        accounts: List[OllamaAccount] = []
        for index, item in enumerate(payload.get("accounts") or [], start=1):
            email = str(item.get("email") or "").strip()
            password = str(item.get("password") or "").strip()
            api_key = str(item.get("api_key") or "").strip()
            if not api_key and (not email or not password):
                continue
            accounts.append(
                OllamaAccount(
                    label=str(item.get("label") or f"account-{index}").strip() or f"account-{index}",
                    email=email,
                    password=password,
                    api_key=api_key,
                )
            )
        return accounts
