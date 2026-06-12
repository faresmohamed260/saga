from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


DEFAULT_CODEX_AUTH_FILE = Path.home() / ".codex" / "auth.json"


@dataclass(frozen=True)
class CodexSessionAuth:
    auth_mode: str
    access_token: str
    account_id: str


class CodexSessionStore:
    """Read local Codex desktop/CLI session auth from ~/.codex/auth.json."""

    def __init__(self, auth_path: Path | None = None) -> None:
        self.auth_path = Path(auth_path or DEFAULT_CODEX_AUTH_FILE)

    def _load(self) -> dict:
        if not self.auth_path.exists():
            return {}
        try:
            payload = json.loads(self.auth_path.read_text(encoding="utf-8-sig"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def active_session(self) -> CodexSessionAuth | None:
        payload = self._load()
        tokens = payload.get("tokens") or {}
        access_token = str(tokens.get("access_token") or "").strip()
        if not access_token:
            return None
        return CodexSessionAuth(
            auth_mode=str(payload.get("auth_mode") or "").strip(),
            access_token=access_token,
            account_id=str(tokens.get("account_id") or "").strip(),
        )

    def active_access_token(self) -> str:
        session = self.active_session()
        if not session:
            return ""
        return session.access_token

    def has_session(self) -> bool:
        return bool(self.active_session())
