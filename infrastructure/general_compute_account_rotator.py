"""Local-only General Compute API-key rotation helpers.

This mirrors the Ollama local credential pool pattern while staying simpler:
General Compute uses direct API keys, so rotation is just active-index
management plus a light round-robin selector.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
import time
from typing import Any, Dict, List

from sql_store.persistence import SagaSQLiteStore


DEFAULT_ACCOUNTS_FILE = Path("deploy/general_compute/accounts.local.json")


@dataclass
class GeneralComputeAccount:
    label: str
    api_key: str


class GeneralComputeAccountRotator:
    """Rotate among locally configured General Compute API keys."""

    DEFAULT_REQUESTS_PER_MINUTE = 60
    DEFAULT_INPUT_TOKENS_PER_MINUTE = 100_000
    DEFAULT_OUTPUT_TOKENS_PER_MINUTE = 10_000
    DEFAULT_REQUESTS_PER_DAY = 1_000
    DEFAULT_TOKENS_PER_DAY = 1_000_000

    def __init__(self, config_path: str | Path | None = None) -> None:
        self.config_path = Path(config_path or DEFAULT_ACCOUNTS_FILE)
        self.sqlite_store = SagaSQLiteStore()

    def has_accounts(self) -> bool:
        data = self._load_data()
        return bool(self._accounts(data))

    def active_account(self) -> GeneralComputeAccount | None:
        data = self._load_data()
        accounts = self._accounts(data)
        if not accounts:
            return None
        index = int(data.get("active_index", 0)) % len(accounts)
        return accounts[index]

    def active_api_key(self) -> str:
        account = self.active_account()
        return account.api_key if account else ""

    def acquire_api_key_for_request(
        self,
        *,
        estimated_tokens: int = 0,
        estimated_input_tokens: int | None = None,
        estimated_output_tokens: int | None = None,
        wait: bool = True,
        max_wait_seconds: int = 300,
    ) -> str:
        token_budget = self._normalize_token_budget(
            estimated_tokens=estimated_tokens,
            estimated_input_tokens=estimated_input_tokens,
            estimated_output_tokens=estimated_output_tokens,
        )
        while True:
            data = self._load_data()
            accounts = self._accounts(data)
            if not accounts:
                return ""
            ordered_indexes = self._round_robin_indexes(data, len(accounts))
            for next_index in ordered_indexes:
                account_payload = (data.get("accounts") or [])[next_index]
                self._reset_usage_windows(account_payload)
                if self._within_limits(account_payload, **token_budget):
                    usage = self._usage(account_payload)
                    usage["minute_requests"] += 1
                    usage["day_requests"] += 1
                    usage["minute_input_tokens"] += token_budget["estimated_input_tokens"]
                    usage["minute_output_tokens"] += token_budget["estimated_output_tokens"]
                    usage["minute_tokens"] = usage["minute_input_tokens"] + usage["minute_output_tokens"]
                    usage["day_tokens"] += token_budget["estimated_input_tokens"] + token_budget["estimated_output_tokens"]
                    data["last_request_index"] = next_index
                    data["active_index"] = next_index
                    self._save_data(data)
                    return accounts[next_index].api_key

            if not wait:
                return ""
            wait_seconds = self._next_wait_seconds(data, **token_budget)
            if wait_seconds <= 0:
                wait_seconds = 1
            if wait_seconds > max_wait_seconds:
                raise RuntimeError(
                    f"General Compute key pool exhausted; next safe slot is in {wait_seconds}s, "
                    f"which exceeds the configured max wait of {max_wait_seconds}s."
                )
            time.sleep(wait_seconds)

    def rotate_for_model(self, *, model_name: str, probe_callable) -> Dict[str, Any]:
        data = self._load_data()
        accounts = self._accounts(data)
        if not accounts:
            return {"status": "unconfigured", "detail": f"No General Compute accounts configured in {self.config_path}"}

        start_index = int(data.get("active_index", 0)) % len(accounts)
        for offset in range(1, len(accounts) + 1):
            next_index = (start_index + offset) % len(accounts)
            account = accounts[next_index]
            try:
                probe_result = probe_callable(model_name, account.api_key)
            except Exception as exc:  # pragma: no cover - defensive runtime guard
                probe_result = {"status": "error", "detail": repr(exc)}
            if probe_result.get("status") == "ok":
                data["active_index"] = next_index
                data["last_request_index"] = next_index
                self._save_data(data)
                return {
                    "status": "rotated",
                    "label": account.label,
                    "active_index": next_index,
                }
        return {
            "status": "exhausted",
            "detail": f"Unable to rotate General Compute accounts for model {model_name}.",
        }

    def record_usage(self, api_key: str, *, total_tokens: int = 0, request_count: int = 1) -> None:
        return

    def _load_data(self) -> Dict[str, Any]:
        stored = self.sqlite_store.get_provider_config("general_compute")
        if isinstance(stored, dict):
            accounts: list[dict[str, Any]] = []
            for index, item in enumerate(stored.get("accounts") or []):
                if not isinstance(item, dict):
                    continue
                merged = {
                    "label": str(item.get("label") or f"key-{index + 1}").strip(),
                    "api_key": str(item.get("api_key") or "").strip(),
                }
                metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
                for key, value in metadata.items():
                    if key not in merged:
                        merged[key] = value
                accounts.append(merged)
            payload = {
                "active_index": int(stored.get("active_index", 0) or 0),
                "accounts": accounts,
            }
            metadata = stored.get("metadata") if isinstance(stored.get("metadata"), dict) else {}
            if "last_request_index" in metadata:
                payload["last_request_index"] = metadata.get("last_request_index")
            return payload
        if not self.config_path.exists():
            return {"active_index": 0, "last_request_index": -1, "accounts": []}
        return json.loads(self.config_path.read_text(encoding="utf-8-sig"))

    def _save_data(self, payload: Dict[str, Any]) -> None:
        self.sqlite_store.upsert_provider_config("general_compute", {
            "provider_name": "general_compute",
            "active_index": int(payload.get("active_index", 0) or 0),
            "accounts": payload.get("accounts") or [],
            "last_request_index": int(payload.get("last_request_index", -1) or -1),
        })

    def _accounts(self, payload: Dict[str, Any]) -> List[GeneralComputeAccount]:
        accounts: List[GeneralComputeAccount] = []
        for index, item in enumerate(payload.get("accounts") or [], start=1):
            api_key = str(item.get("api_key") or "").strip()
            if not api_key:
                continue
            accounts.append(
                GeneralComputeAccount(
                    label=str(item.get("label") or f"key-{index}").strip() or f"key-{index}",
                    api_key=api_key,
                )
            )
        return accounts

    def _round_robin_indexes(self, payload: Dict[str, Any], count: int) -> List[int]:
        if count <= 0:
            return []
        start = int(payload.get("last_request_index", -1)) + 1
        return [((start + offset) % count) for offset in range(count)]

    def _usage(self, account_payload: Dict[str, Any]) -> Dict[str, Any]:
        usage = account_payload.get("usage")
        if not isinstance(usage, dict):
            usage = {}
            account_payload["usage"] = usage
        usage.setdefault("minute_window_started_at", "")
        usage.setdefault("day_window_started_on", "")
        usage.setdefault("minute_requests", 0)
        usage.setdefault("minute_input_tokens", int(usage.get("minute_tokens") or 0))
        usage.setdefault("minute_output_tokens", 0)
        usage.setdefault("minute_tokens", 0)
        usage.setdefault("day_requests", 0)
        usage.setdefault("day_tokens", 0)
        return usage

    def _limits(self, account_payload: Dict[str, Any]) -> Dict[str, int]:
        limits = account_payload.get("limits")
        if not isinstance(limits, dict):
            limits = {}
        shared_minute_limit = limits.get("tokens_per_minute")
        return {
            "requests_per_minute": int(limits.get("requests_per_minute") or self.DEFAULT_REQUESTS_PER_MINUTE),
            "input_tokens_per_minute": int(
                limits.get("input_tokens_per_minute")
                or shared_minute_limit
                or self.DEFAULT_INPUT_TOKENS_PER_MINUTE
            ),
            "output_tokens_per_minute": int(
                limits.get("output_tokens_per_minute")
                or shared_minute_limit
                or self.DEFAULT_OUTPUT_TOKENS_PER_MINUTE
            ),
            "requests_per_day": int(limits.get("requests_per_day") or self.DEFAULT_REQUESTS_PER_DAY),
            "tokens_per_day": int(limits.get("tokens_per_day") or self.DEFAULT_TOKENS_PER_DAY),
        }

    def _reset_usage_windows(self, account_payload: Dict[str, Any]) -> None:
        usage = self._usage(account_payload)
        now = datetime.now(timezone.utc)
        minute_key = now.strftime("%Y-%m-%dT%H:%M")
        day_key = now.strftime("%Y-%m-%d")
        if usage.get("minute_window_started_at") != minute_key:
            usage["minute_window_started_at"] = minute_key
            usage["minute_requests"] = 0
            usage["minute_input_tokens"] = 0
            usage["minute_output_tokens"] = 0
            usage["minute_tokens"] = 0
        if usage.get("day_window_started_on") != day_key:
            usage["day_window_started_on"] = day_key
            usage["day_requests"] = 0
            usage["day_tokens"] = 0

    def _within_limits(
        self,
        account_payload: Dict[str, Any],
        *,
        estimated_input_tokens: int,
        estimated_output_tokens: int,
    ) -> bool:
        limits = self._limits(account_payload)
        usage = self._usage(account_payload)
        next_request_count = usage["minute_requests"] + 1
        next_day_request_count = usage["day_requests"] + 1
        next_minute_input_tokens = usage["minute_input_tokens"] + estimated_input_tokens
        next_minute_output_tokens = usage["minute_output_tokens"] + estimated_output_tokens
        next_day_tokens = usage["day_tokens"] + estimated_input_tokens + estimated_output_tokens
        return (
            next_request_count <= limits["requests_per_minute"]
            and next_day_request_count <= limits["requests_per_day"]
            and next_minute_input_tokens <= limits["input_tokens_per_minute"]
            and next_minute_output_tokens <= limits["output_tokens_per_minute"]
            and next_day_tokens <= limits["tokens_per_day"]
        )

    def _next_wait_seconds(
        self,
        payload: Dict[str, Any],
        *,
        estimated_input_tokens: int,
        estimated_output_tokens: int,
    ) -> int:
        waits: List[int] = []
        for account_payload in payload.get("accounts") or []:
            self._reset_usage_windows(account_payload)
            waits.append(
                self._wait_for_account(
                    account_payload,
                    estimated_input_tokens=estimated_input_tokens,
                    estimated_output_tokens=estimated_output_tokens,
                )
            )
        return min(waits) if waits else 0

    def _wait_for_account(
        self,
        account_payload: Dict[str, Any],
        *,
        estimated_input_tokens: int,
        estimated_output_tokens: int,
    ) -> int:
        if self._within_limits(
            account_payload,
            estimated_input_tokens=estimated_input_tokens,
            estimated_output_tokens=estimated_output_tokens,
        ):
            return 0
        limits = self._limits(account_payload)
        usage = self._usage(account_payload)
        minute_blocked = (
            usage["minute_requests"] + 1 > limits["requests_per_minute"]
            or usage["minute_input_tokens"] + estimated_input_tokens > limits["input_tokens_per_minute"]
            or usage["minute_output_tokens"] + estimated_output_tokens > limits["output_tokens_per_minute"]
        )
        day_blocked = (
            usage["day_requests"] + 1 > limits["requests_per_day"]
            or usage["day_tokens"] + estimated_input_tokens + estimated_output_tokens > limits["tokens_per_day"]
        )
        waits: List[int] = []
        if minute_blocked:
            waits.append(self._seconds_until_next_minute())
        if day_blocked:
            waits.append(self._seconds_until_next_day())
        return max(waits) if waits else 0

    def _normalize_token_budget(
        self,
        *,
        estimated_tokens: int = 0,
        estimated_input_tokens: int | None = None,
        estimated_output_tokens: int | None = None,
    ) -> Dict[str, int]:
        if estimated_input_tokens is None and estimated_output_tokens is None:
            return {
                "estimated_input_tokens": max(0, int(estimated_tokens)),
                "estimated_output_tokens": 0,
            }
        return {
            "estimated_input_tokens": max(0, int(estimated_input_tokens or 0)),
            "estimated_output_tokens": max(0, int(estimated_output_tokens or 0)),
        }

    def _seconds_until_next_minute(self) -> int:
        now = datetime.now(timezone.utc)
        return max(1, 60 - now.second)

    def _seconds_until_next_day(self) -> int:
        now = datetime.now(timezone.utc)
        tomorrow = datetime(now.year, now.month, now.day, tzinfo=timezone.utc).timestamp() + 86400
        return max(1, int(tomorrow - now.timestamp()))
