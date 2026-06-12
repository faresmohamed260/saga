from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


DEFAULT_ACCOUNTS_FILE = Path("deploy/openai/accounts.local.json")


@dataclass(frozen=True)
class OpenAIAccount:
    label: str
    api_key: str


class OpenAIAccountStore:
    """Local account store for Codex/OpenAI API keys.

    The runtime currently uses the active account only. The list shape mirrors
    the Ollama provider config so the dashboard can manage both providers with a
    similar UX.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = Path(config_path or DEFAULT_ACCOUNTS_FILE)

    def _load(self) -> dict:
        if not self.config_path.exists():
            return {"active_index": 0, "accounts": []}
        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8-sig"))
        except Exception:
            return {"active_index": 0, "accounts": []}
        if not isinstance(payload, dict):
            return {"active_index": 0, "accounts": []}
        return payload

    def accounts(self) -> list[OpenAIAccount]:
        rows = []
        for index, item in enumerate(self._load().get("accounts") or []):
            label = str(item.get("label") or f"account-{index + 1}").strip()
            api_key = str(item.get("api_key") or "").strip()
            if not api_key:
                continue
            rows.append(OpenAIAccount(label=label, api_key=api_key))
        return rows

    def has_accounts(self) -> bool:
        return bool(self.accounts())

    def active_index(self) -> int:
        payload = self._load()
        try:
            return max(0, int(payload.get("active_index", 0) or 0))
        except Exception:
            return 0

    def active_account(self) -> OpenAIAccount | None:
        accounts = self.accounts()
        if not accounts:
            return None
        index = min(self.active_index(), len(accounts) - 1)
        return accounts[index]

    def active_api_key(self) -> str:
        account = self.active_account()
        if not account:
            return ""
        return account.api_key.strip()
