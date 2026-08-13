"""Portable configuration models for the reasoning runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class OllamaAccount:
    label: str
    api_key: str = ""
    email: str = ""
    password: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.label or "").strip():
            raise ValueError("OllamaAccount.label is required.")


@dataclass(frozen=True)
class GeneralComputeAccount:
    label: str
    api_key: str
    limits: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.label or "").strip():
            raise ValueError("GeneralComputeAccount.label is required.")
        if not str(self.api_key or "").strip():
            raise ValueError("GeneralComputeAccount.api_key is required.")

@dataclass(frozen=True)
class ReasoningProfile:
    name: str
    mode: str = "gpt_oss"
    timeout_seconds: int = 180
    max_retries: int = 2
    base_delay_seconds: float = 0.0
    allow_account_rotation: bool = True
    prefer_local_ollama: bool = False
    ollama_model: str = ""
    context_window_tokens: int = 8192
    deepseek_model: str = "deepseek-v3.1:671b-cloud"
    gpt_oss_model: str = "gpt-oss:120b-cloud"
    general_compute_model: str = "deepseek-v3.1"
    mistral_model: str = "mistral-large-2512"
    gemini_model: str = "gemini-2.0-flash"
    model_override: str = ""

    def __post_init__(self) -> None:
        if not str(self.name or "").strip():
            raise ValueError("ReasoningProfile.name is required.")
        if not str(self.mode or "").strip():
            raise ValueError("ReasoningProfile.mode is required.")
        if int(self.timeout_seconds) <= 0:
            raise ValueError("ReasoningProfile.timeout_seconds must be positive.")
        if int(self.max_retries) < 1:
            raise ValueError("ReasoningProfile.max_retries must be at least 1.")
        if float(self.base_delay_seconds) < 0:
            raise ValueError("ReasoningProfile.base_delay_seconds cannot be negative.")
        if int(self.context_window_tokens) < 1024:
            raise ValueError("ReasoningProfile.context_window_tokens must be at least 1024.")


@dataclass
class ReasoningRuntimeConfig:
    profiles: dict[str, ReasoningProfile] = field(default_factory=dict)
    ollama_accounts: list[OllamaAccount] = field(default_factory=list)
    general_compute_accounts: list[GeneralComputeAccount] = field(default_factory=list)
    ollama_active_index: int = 0
    general_compute_active_index: int = 0
    general_compute_last_request_index: int = -1
    ollama_local_url: str = "http://localhost:11434/api/generate"
    ollama_local_chat_url: str = "http://localhost:11434/api/chat"
    ollama_cloud_url: str = "https://ollama.com/api/generate"
    general_compute_chat_url: str = "https://api.generalcompute.com/v1/chat/completions"
    mistral_api_key: str = ""
    gemini_api_key: str = ""

    def __post_init__(self) -> None:
        if str(self.ollama_local_url or "").strip() and not str(self.ollama_local_url).strip().startswith(("http://", "https://")):
            raise ValueError("ReasoningRuntimeConfig.ollama_local_url must be an HTTP(S) URL.")
        if str(self.ollama_local_chat_url or "").strip() and not str(self.ollama_local_chat_url).strip().startswith(("http://", "https://")):
            raise ValueError("ReasoningRuntimeConfig.ollama_local_chat_url must be an HTTP(S) URL.")
        if str(self.ollama_cloud_url or "").strip() and not str(self.ollama_cloud_url).strip().startswith(("http://", "https://")):
            raise ValueError("ReasoningRuntimeConfig.ollama_cloud_url must be an HTTP(S) URL.")
        if str(self.general_compute_chat_url or "").strip() and not str(self.general_compute_chat_url).strip().startswith(("http://", "https://")):
            raise ValueError("ReasoningRuntimeConfig.general_compute_chat_url must be an HTTP(S) URL.")
