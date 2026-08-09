from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import threading
from typing import Any

from packages.reasoning_runtime.models import GeneralComputeAccount, OllamaAccount


@dataclass
class SimpleRotationPool:
    accounts: list[OllamaAccount] = field(default_factory=list)
    active_index: int = 0
    env_api_key: str = ""
    env_alias: str = ""
    local_alias: str = ""
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def acquire_for_request(self) -> tuple[str, str]:
        if self.env_api_key:
            return self.env_api_key, self.env_alias
        with self._lock:
            if not self.accounts:
                return "", self.local_alias
            index = self.active_index % len(self.accounts)
            account = self.accounts[index]
            self.active_index = (index + 1) % len(self.accounts)
            return str(account.api_key or "").strip(), account.label

    def current_api_key(self) -> str:
        if self.env_api_key:
            return self.env_api_key
        if self.accounts:
            return str(self.accounts[self.active_index % len(self.accounts)].api_key or "").strip()
        return ""

    def current_label(self) -> str:
        if self.env_api_key:
            return self.env_alias
        if self.accounts:
            return self.accounts[self.active_index % len(self.accounts)].label
        return self.local_alias

    def rotate(self) -> bool:
        with self._lock:
            if not self.accounts:
                return False
            self.active_index = (self.active_index + 1) % len(self.accounts)
            return True


class GeneralComputePool:
    DEFAULT_REQUESTS_PER_MINUTE = 60
    DEFAULT_INPUT_TOKENS_PER_MINUTE = 100_000
    DEFAULT_OUTPUT_TOKENS_PER_MINUTE = 10_000
    DEFAULT_REQUESTS_PER_DAY = 1_000
    DEFAULT_TOKENS_PER_DAY = 1_000_000

    def __init__(
        self,
        *,
        accounts: list[GeneralComputeAccount] | None = None,
        active_index: int = 0,
        last_request_index: int = -1,
        env_api_key: str = "",
    ) -> None:
        self.accounts = list(accounts or [])
        self.active_index = max(0, int(active_index or 0))
        self.last_request_index = int(last_request_index or -1)
        self.env_api_key = str(env_api_key or "").strip()
        self._usage_by_label: dict[str, dict[str, Any]] = {}

    def current_label(self) -> str:
        if self.env_api_key:
            return "env_general_compute_api_key"
        if not self.accounts:
            return ""
        return self.accounts[self.active_index % len(self.accounts)].label

    def current_api_key(self) -> str:
        if self.env_api_key:
            return self.env_api_key
        if not self.accounts:
            return ""
        return str(self.accounts[self.active_index % len(self.accounts)].api_key or "").strip()

    def rotate(self) -> bool:
        if not self.accounts:
            return False
        self.active_index = (self.active_index + 1) % len(self.accounts)
        self.last_request_index = self.active_index
        return True

    def acquire_api_key_for_request(
        self,
        *,
        estimated_tokens: int = 0,
        estimated_input_tokens: int | None = None,
        estimated_output_tokens: int | None = None,
        wait: bool = False,
        max_wait_seconds: int = 0,
    ) -> str:
        del wait, max_wait_seconds
        if self.env_api_key:
            return self.env_api_key
        token_budget = self._normalize_token_budget(
            estimated_tokens=estimated_tokens,
            estimated_input_tokens=estimated_input_tokens,
            estimated_output_tokens=estimated_output_tokens,
        )
        if not self.accounts:
            return ""
        ordered_indexes = self._round_robin_indexes(len(self.accounts))
        for next_index in ordered_indexes:
            account = self.accounts[next_index]
            self._reset_usage_windows(account)
            if self._within_limits(account, **token_budget):
                usage = self._usage(account)
                usage["minute_requests"] += 1
                usage["day_requests"] += 1
                usage["minute_input_tokens"] += token_budget["estimated_input_tokens"]
                usage["minute_output_tokens"] += token_budget["estimated_output_tokens"]
                usage["minute_tokens"] = usage["minute_input_tokens"] + usage["minute_output_tokens"]
                usage["day_tokens"] += token_budget["estimated_input_tokens"] + token_budget["estimated_output_tokens"]
                self.last_request_index = next_index
                self.active_index = next_index
                return str(account.api_key or "").strip()
        return ""

    def usage_for_label(self, label: str) -> dict[str, Any]:
        account = next((item for item in self.accounts if item.label == label), None)
        if account is None:
            return {}
        self._reset_usage_windows(account)
        return dict(self._usage(account))

    def limits_for_label(self, label: str) -> dict[str, int]:
        account = next((item for item in self.accounts if item.label == label), None)
        if account is None:
            return {}
        return dict(self._limits(account))

    def _round_robin_indexes(self, count: int) -> list[int]:
        if count <= 0:
            return []
        start = self.last_request_index + 1
        return [((start + offset) % count) for offset in range(count)]

    def _usage(self, account: GeneralComputeAccount) -> dict[str, Any]:
        label = str(account.label or "").strip()
        if label not in self._usage_by_label:
            source = account.usage if isinstance(account.usage, dict) else {}
            self._usage_by_label[label] = dict(source)
        usage = self._usage_by_label[label]
        usage.setdefault("minute_window_started_at", "")
        usage.setdefault("day_window_started_on", "")
        usage.setdefault("minute_requests", 0)
        usage.setdefault("minute_input_tokens", int(usage.get("minute_tokens") or 0))
        usage.setdefault("minute_output_tokens", 0)
        usage.setdefault("minute_tokens", 0)
        usage.setdefault("day_requests", 0)
        usage.setdefault("day_tokens", 0)
        return usage

    def _limits(self, account: GeneralComputeAccount) -> dict[str, int]:
        limits = account.limits if isinstance(account.limits, dict) else {}
        shared_minute_limit = limits.get("tokens_per_minute")
        return {
            "requests_per_minute": int(limits.get("requests_per_minute") or self.DEFAULT_REQUESTS_PER_MINUTE),
            "input_tokens_per_minute": int(limits.get("input_tokens_per_minute") or shared_minute_limit or self.DEFAULT_INPUT_TOKENS_PER_MINUTE),
            "output_tokens_per_minute": int(limits.get("output_tokens_per_minute") or shared_minute_limit or self.DEFAULT_OUTPUT_TOKENS_PER_MINUTE),
            "requests_per_day": int(limits.get("requests_per_day") or self.DEFAULT_REQUESTS_PER_DAY),
            "tokens_per_day": int(limits.get("tokens_per_day") or self.DEFAULT_TOKENS_PER_DAY),
        }

    def _reset_usage_windows(self, account: GeneralComputeAccount) -> None:
        usage = self._usage(account)
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

    def _within_limits(self, account: GeneralComputeAccount, *, estimated_input_tokens: int, estimated_output_tokens: int) -> bool:
        limits = self._limits(account)
        usage = self._usage(account)
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

    @staticmethod
    def _normalize_token_budget(
        *,
        estimated_tokens: int = 0,
        estimated_input_tokens: int | None = None,
        estimated_output_tokens: int | None = None,
    ) -> dict[str, int]:
        if estimated_input_tokens is None and estimated_output_tokens is None:
            return {
                "estimated_input_tokens": max(0, int(estimated_tokens)),
                "estimated_output_tokens": 0,
            }
        return {
            "estimated_input_tokens": max(0, int(estimated_input_tokens or 0)),
            "estimated_output_tokens": max(0, int(estimated_output_tokens or 0)),
        }
