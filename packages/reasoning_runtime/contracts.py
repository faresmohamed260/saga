"""Portable contracts and payload models for reasoning-capable clients."""

from __future__ import annotations

from typing import Any, Callable, Optional, Protocol

from pydantic import AliasChoices, BaseModel, Field
from packages.runtime_common import CancellationChecker, RuntimeRequestMetadata


class ReasoningRequestMetadata(RuntimeRequestMetadata):
    provider_family: str = ""
    resolved_model: str = ""
    provider_account_alias: str = ""
    request_kind: str = ""
    json_mode: str = ""
    response_format_type: str = ""
    tool_mode: str = ""
    rotation_used: bool = False
    rotation_attempt_count: int = 0
    fallback_used: bool = False
    fallback_from_mode: str = ""
    fallback_to_mode: str = ""


class ReasoningTextResult(BaseModel):
    provider: str = Field(description="Resolved provider family.")
    model: str = Field(description="Resolved model identifier.")
    text: str = Field(description="Generated natural-language text.")
    request_metadata: ReasoningRequestMetadata = Field(
        default_factory=ReasoningRequestMetadata,
        validation_alias=AliasChoices("request_metadata", "metadata"),
        serialization_alias="request_metadata",
    )


class ReasoningJsonResult(BaseModel):
    provider: str = Field(description="Resolved provider family.")
    model: str = Field(description="Resolved model identifier.")
    payload_kind: str = Field(default="object", description="Normalized top-level JSON payload kind.")
    payload_keys: list[str] = Field(default_factory=list, description="Sorted top-level keys present on object payloads.")
    field_count: int = Field(default=0, description="Top-level field count for object payloads.")
    payload: dict[str, Any] = Field(default_factory=dict, description="Structured JSON payload returned by the reasoning provider.")
    request_metadata: ReasoningRequestMetadata = Field(
        default_factory=ReasoningRequestMetadata,
        validation_alias=AliasChoices("request_metadata", "metadata"),
        serialization_alias="request_metadata",
    )


class ReasoningClient(Protocol):
    mode: str

    def generate_json(
        self,
        prompt: str,
        strict: bool = False,
        validator: Optional[Callable] = None,
        max_tokens: int = 4096,
        response_format: Optional[dict] = None,
        tools: Optional[list] = None,
        tool_choice: Optional[object] = None,
        cancellation_checker: CancellationChecker | None = None,
    ) -> dict[str, Any]:
        ...

    def generate_text(
        self,
        prompt: str,
        *,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        cancellation_checker: CancellationChecker | None = None,
    ) -> str:
        ...

    def provider_name(self) -> str:
        ...

    def resolved_model_name(self) -> str:
        ...

    def last_request_metadata(self) -> dict[str, Any]:
        ...
