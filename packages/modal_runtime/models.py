from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator
from packages.runtime_common import RuntimeRequestMetadata


class ModalEndpointRequestMetadata(RuntimeRequestMetadata):
    observed_at: int | None = None
    response_keys: list[str] = Field(default_factory=list)
    token_name: str = ""
    app_name: str = ""
    api_url: str = ""
    ui_url: str = ""
    health_url: str = ""
    upstream_trace_id: str = ""


class ModalLastSuccessfulRequest(ModalEndpointRequestMetadata):
    pass


class ModalTokenStatus(BaseModel):
    token_name: str = Field(min_length=1)
    app_name: str = ""
    api_url: str = ""
    ui_url: str = ""
    health_url: str = ""
    warm_until: int = 0
    last_seen_at: int = 0
    last_health_ok: bool | None = None
    last_health_checked_at: int = 0
    last_request_ok: bool | None = None
    last_request_checked_at: int = 0
    last_error: str = ""
    last_error_at: int = 0
    live_payload: dict[str, Any] = Field(default_factory=dict)
    live_payload_checked_at: int = 0
    last_successful_request: ModalLastSuccessfulRequest | None = None
    last_successful_request_at: int = 0

    @field_validator("token_name", "app_name", "api_url", "ui_url", "health_url", "last_error", mode="before")
    @classmethod
    def _coerce_string(cls, value: Any) -> str:
        return str(value or "").strip()

    def to_status_payload(self) -> dict[str, Any]:
        payload = self.model_dump(exclude_none=True)
        payload.pop("token_name", None)
        return payload

    @classmethod
    def from_status_row(cls, label: str, payload: dict[str, Any] | None) -> "ModalTokenStatus":
        merged = dict(payload or {})
        merged["token_name"] = str(label or "").strip()
        if "last_render_ok" in merged and "last_request_ok" not in merged:
            merged["last_request_ok"] = merged.get("last_render_ok")
        if "last_render_checked_at" in merged and "last_request_checked_at" not in merged:
            merged["last_request_checked_at"] = merged.get("last_render_checked_at")
        if "last_live_ok" in merged and "last_request_ok" not in merged:
            merged["last_request_ok"] = merged.get("last_live_ok")
        if "last_live_checked_at" in merged and "last_request_checked_at" not in merged:
            merged["last_request_checked_at"] = merged.get("last_live_checked_at")
        if isinstance(merged.get("last_successful_request"), dict):
            merged["last_successful_request"] = ModalLastSuccessfulRequest.model_validate(merged["last_successful_request"])
        return cls.model_validate(merged)


class ModalRuntimeState(BaseModel):
    app_name: str = ""
    runtime_generation: int = 0
    next_index: int = 0
    active_token_name: str = ""
    active_api_url: str = ""
    active_ui_url: str = ""
    active_health_url: str = ""
    active_app_name: str = ""
    token_stats: dict[str, ModalTokenStatus] = Field(default_factory=dict)

    @field_validator("app_name", "active_token_name", "active_api_url", "active_ui_url", "active_health_url", "active_app_name", mode="before")
    @classmethod
    def _coerce_runtime_strings(cls, value: Any) -> str:
        return str(value or "").strip()

    def to_runtime_payload(self) -> dict[str, Any]:
        return {
            "app_name": self.app_name,
            "runtime_generation": max(0, int(self.runtime_generation or 0)),
            "next_index": max(0, int(self.next_index or 0)),
            "active_token_name": self.active_token_name,
            "active_api_url": self.active_api_url,
            "active_ui_url": self.active_ui_url,
            "active_health_url": self.active_health_url,
            "active_app_name": self.active_app_name,
            "token_stats": {
                name: status.to_status_payload()
                for name, status in sorted(self.token_stats.items())
                if str(name or "").strip()
            },
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> "ModalRuntimeState":
        raw = dict(payload or {})
        token_stats_raw = raw.get("token_stats") if isinstance(raw.get("token_stats"), dict) else {}
        normalized_stats: dict[str, ModalTokenStatus] = {}
        for token_name, stats in token_stats_raw.items():
            normalized_name = str(token_name or "").strip()
            if not normalized_name:
                continue
            normalized_stats[normalized_name] = ModalTokenStatus.from_status_row(normalized_name, dict(stats or {}))
        raw["token_stats"] = normalized_stats
        return cls.model_validate(raw)


class ModalEndpointUrls(BaseModel):
    api_url: str = ""
    ui_url: str = ""
    health_url: str = ""


class ModalEndpointDescriptor(BaseModel):
    token_name: str = Field(min_length=1)
    api_url: str = ""
    ui_url: str = ""
    health_url: str = ""
    live_payload: dict[str, Any] = Field(default_factory=dict)


class ModalExecutionRequestMetadata(RuntimeRequestMetadata):
    token_name: str = ""
    app_name: str = ""
    api_url: str = ""
    ui_url: str = ""
    health_url: str = ""
    response_keys: list[str] = Field(default_factory=list)
    upstream_trace_id: str = ""


class ModalExecutionResult(BaseModel):
    token_name: str = Field(min_length=1)
    app_name: str = ""
    api_url: str = ""
    ui_url: str = ""
    health_url: str = ""
    live_payload: dict[str, Any] = Field(default_factory=dict)
    response: dict[str, Any] = Field(default_factory=dict)
    metadata: ModalExecutionRequestMetadata = Field(default_factory=ModalExecutionRequestMetadata)
