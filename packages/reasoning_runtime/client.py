"""Standalone reasoning runtime that can be embedded in any project."""

from __future__ import annotations

import base64
import json
import os
import re
import time
from copy import deepcopy
from typing import Any, Callable, Optional

import requests
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

try:
    from google import genai
except ImportError:  # pragma: no cover
    genai = None

try:
    from mistralai import Mistral
except ImportError:  # pragma: no cover
    try:
        from mistralai.client.sdk import Mistral
    except ImportError:
        Mistral = None

from packages.reasoning_runtime.contracts import ReasoningJsonResult, ReasoningRequestMetadata, ReasoningTextResult
from packages.reasoning_runtime.models import ReasoningProfile, ReasoningRuntimeConfig
from packages.reasoning_runtime.pools import GeneralComputePool, SimpleRotationPool
from packages.runtime_common import build_structured_runtime_tool, create_trace, current_trace_context


class ReasoningRuntimeClient:
    MODE_DEEPSEEK = "deepseek"
    MODE_GPT_OSS = "gpt_oss"
    MODE_GENERAL_COMPUTE = "general_compute"
    MODE_MISTRAL = "mistral"
    MODE_GEMINI = "gemini"

    def __init__(self, *, profile: ReasoningProfile, config: ReasoningRuntimeConfig) -> None:
        self.profile = profile
        self.config = deepcopy(config)
        self.mode = str(profile.mode or self.MODE_GPT_OSS).strip().lower()
        self.timeout = max(30, int(profile.timeout_seconds))
        self.max_retries = max(1, int(profile.max_retries))
        self.base_delay = max(0.0, float(profile.base_delay_seconds))
        self.allow_account_rotation = bool(profile.allow_account_rotation)
        self.allow_cross_provider_fallback = False
        self._last_request_metadata = ReasoningRequestMetadata()
        self._mistral_client = None
        self._gemini_client = None
        self._json_failures = 0
        self._pending_request_kind = ""
        self._pending_json_mode = ""
        self._pending_response_format_type = ""
        self._pending_tool_mode = ""
        self._request_account_alias = ""
        self._ollama_pool = SimpleRotationPool(
            accounts=self.config.ollama_accounts,
            active_index=self.config.ollama_active_index,
            env_api_key=str(os.getenv("OLLAMA_API_KEY") or "").strip(),
            env_alias="env_ollama_api_key",
            local_alias="ollama_local",
        )
        self._general_compute_pool = GeneralComputePool(
            accounts=self.config.general_compute_accounts,
            active_index=self.config.general_compute_active_index,
            last_request_index=self.config.general_compute_last_request_index,
            env_api_key=str(os.getenv("GENERAL_COMPUTE_API_KEY") or "").strip(),
        )

    def generate_json(
        self,
        prompt: str,
        strict: bool = False,
        validator: Optional[Callable] = None,
        max_tokens: int = 4096,
        response_format: Optional[dict] = None,
        tools: Optional[list] = None,
        tool_choice: Optional[object] = None,
    ) -> dict[str, Any]:
        effective_prompt = self._apply_strict_mode(prompt) if strict else prompt
        self._pending_request_kind = "json"
        self._pending_json_mode = "strict_prompt" if strict else "plain_prompt"
        self._pending_response_format_type = self._response_format_type(response_format)
        self._pending_tool_mode = "tool_calling" if tools else ""
        self._begin_request_tracking()
        result = self._retry_json_request(
            lambda: self._dispatch_json(
                effective_prompt,
                max_tokens=max_tokens,
                response_format=response_format,
                tools=tools,
                tool_choice=tool_choice,
            )
        )
        if validator and isinstance(result, dict) and "error" not in result and not validator(result):
            self._last_request_metadata.status = "error"
            self._last_request_metadata.error_code = "validation_failed"
            return {"error": "validation_failed", "raw_output": result}
        if isinstance(result, dict) and result.get("error"):
            self._last_request_metadata.status = "error"
            self._last_request_metadata.error_code = str(result.get("error") or "max_retries_exceeded")
        self._finalize_request_tracking()
        return result

    def generate_text(
        self,
        prompt: str,
        *,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        self._pending_request_kind = "text"
        self._pending_json_mode = ""
        self._pending_response_format_type = ""
        self._pending_tool_mode = ""
        self._begin_request_tracking()
        try:
            result = self._retry_text_request(
                lambda: self._dispatch_text(
                    prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            )
            return result
        except Exception as exc:
            self._last_request_metadata.status = "error"
            self._last_request_metadata.error_code = type(exc).__name__
            raise
        finally:
            self._finalize_request_tracking()

    def generate_vision_json(
        self,
        *,
        prompt: str,
        image_bytes: bytes,
        response_format: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Run structured multimodal inference through the configured Ollama pool."""
        if self.mode not in {self.MODE_DEEPSEEK, self.MODE_GPT_OSS, self.MODE_MISTRAL}:
            raise ValueError("Vision inference requires an Ollama or Mistral reasoning profile.")
        if not image_bytes:
            raise ValueError("image_bytes is required for vision inference.")
        self._pending_request_kind = "vision_json"
        self._pending_json_mode = "strict_prompt"
        self._pending_response_format_type = self._response_format_type(response_format)
        self._pending_tool_mode = ""
        self._begin_request_tracking()
        if self.mode == self.MODE_MISTRAL:
            def operation() -> dict[str, Any]:
                return self._generate_vision_json_mistral(
                    prompt=self._apply_strict_mode(prompt), image_bytes=image_bytes
                )
        else:
            def operation() -> dict[str, Any]:
                return self._generate_vision_json_ollama(
                    prompt=self._apply_strict_mode(prompt),
                    image_bytes=image_bytes,
                    response_format=response_format,
                )
        result = self._retry_json_request(operation)
        if isinstance(result, dict) and result.get("error"):
            self._last_request_metadata.status = "error"
            self._last_request_metadata.error_code = str(result.get("error") or "max_retries_exceeded")
        self._finalize_request_tracking()
        return result

    def transcribe_audio(
        self,
        *,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language: str = "en",
        context_bias: list[str] | None = None,
    ) -> dict[str, Any]:
        """Transcribe bounded audio through a provider-owned speech-to-text capability."""
        if self.mode != self.MODE_MISTRAL:
            raise ValueError("Audio transcription currently requires a Mistral reasoning profile.")
        if not audio_bytes:
            raise ValueError("audio_bytes is required for transcription.")
        self._pending_request_kind = "audio_transcription"
        self._pending_json_mode = ""
        self._pending_response_format_type = ""
        self._pending_tool_mode = ""
        self._begin_request_tracking()
        try:
            response = self._mistral_client_instance().audio.transcriptions.complete(
                model=self.resolved_model_name(),
                file={
                    "fileName": str(filename or "audio.wav"),
                    "content": audio_bytes,
                    "Content-Type": "audio/wav",
                },
                language=str(language or "en"),
                context_bias=list(context_bias or []),
                diarize=False,
            )
            return {
                "text": str(getattr(response, "text", "") or "").strip(),
                "language": str(getattr(response, "language", "") or language or "").strip(),
                "model": str(getattr(response, "model", "") or self.resolved_model_name()).strip(),
            }
        except Exception as exc:
            self._last_request_metadata.status = "error"
            self._last_request_metadata.error_code = type(exc).__name__
            raise
        finally:
            self._finalize_request_tracking()

    def provider_name(self) -> str:
        if self.mode in {self.MODE_DEEPSEEK, self.MODE_GPT_OSS}:
            return "ollama"
        if self.mode == self.MODE_GENERAL_COMPUTE:
            return "general_compute"
        return self.mode

    def resolved_model_name(self) -> str:
        if self.profile.model_override:
            if self.mode == self.MODE_GENERAL_COMPUTE and self.profile.model_override.endswith("-cloud"):
                return self.profile.general_compute_model
            return self.profile.model_override
        if self.mode == self.MODE_DEEPSEEK:
            return self.profile.deepseek_model
        if self.mode == self.MODE_GPT_OSS:
            return self.profile.gpt_oss_model
        if self.mode == self.MODE_GENERAL_COMPUTE:
            return self.profile.general_compute_model
        if self.mode == self.MODE_MISTRAL:
            return self.profile.mistral_model
        if self.mode == self.MODE_GEMINI:
            return self.profile.gemini_model
        return ""

    def last_request_metadata(self) -> dict[str, Any]:
        return self._last_request_metadata.model_dump()

    def clone(self) -> "ReasoningRuntimeClient":
        """Create an independent client with the same provider profile/config.

        Request metadata is stored on each client instance, so concurrent callers
        should use clones rather than sharing one client across threads.
        """
        clone = ReasoningRuntimeClient(profile=deepcopy(self.profile), config=deepcopy(self.config))
        clone._ollama_pool = self._ollama_pool
        return clone

    def as_langgraph_tools(self) -> list[StructuredTool]:
        client = self

        class GenerateTextArgs(BaseModel):
            prompt: str = Field(description="Primary user prompt for the reasoning runtime.")
            system_prompt: str = Field(default="", description="Optional system prompt or role instruction.")
            temperature: float = Field(default=0.7, description="Sampling temperature for text generation.")
            max_tokens: int = Field(default=4096, ge=1, description="Maximum number of generated tokens.")

        class GenerateJsonArgs(BaseModel):
            prompt: str = Field(description="Prompt that should return a JSON object.")
            strict: bool = Field(default=True, description="Whether to apply strict JSON prompting rules.")
            max_tokens: int = Field(default=4096, ge=1, description="Maximum number of generated tokens.")
            expected_keys: list[str] = Field(default_factory=list, description="Optional required top-level keys that must be present in the JSON object.")

        def generate_text_tool(
            prompt: str,
            system_prompt: str = "",
            temperature: float = 0.7,
            max_tokens: int = 4096,
        ) -> dict[str, Any]:
            text = client.generate_text(
                prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return ReasoningTextResult(
                provider=client.provider_name(),
                model=client.resolved_model_name(),
                text=text,
                request_metadata=ReasoningRequestMetadata.model_validate(client.last_request_metadata()),
            ).model_dump()

        def generate_json_tool(
            prompt: str,
            strict: bool = True,
            max_tokens: int = 4096,
            expected_keys: list[str] | None = None,
        ) -> dict[str, Any]:
            payload = client.generate_json(
                prompt,
                strict=strict,
                max_tokens=max_tokens,
            )
            if isinstance(payload, dict) and payload.get("error"):
                raise RuntimeError(str(payload.get("last_error") or payload.get("error") or "Reasoning runtime returned an error payload."))
            normalized_payload = dict(payload or {})
            normalized_expected_keys = sorted(
                {
                    str(value or "").strip()
                    for value in (expected_keys or [])
                    if str(value or "").strip()
                }
            )
            missing_keys = [key for key in normalized_expected_keys if key not in normalized_payload]
            if missing_keys:
                raise ValueError(f"Reasoning JSON payload is missing required keys: {', '.join(missing_keys)}")
            return ReasoningJsonResult(
                provider=client.provider_name(),
                model=client.resolved_model_name(),
                payload_kind="object",
                payload_keys=sorted(normalized_payload.keys()),
                field_count=len(normalized_payload),
                payload=normalized_payload,
                request_metadata=ReasoningRequestMetadata.model_validate(client.last_request_metadata()),
            ).model_dump()

        return [
            build_structured_runtime_tool(
                func=generate_text_tool,
                name="reasoning_generate_text",
                description="Use the configured reasoning runtime to generate natural-language text.",
                args_schema=GenerateTextArgs,
                component="reasoning_runtime",
                operation="generate_text",
                provider_name=client.provider_name,
                metadata=lambda: {"profile": client.profile.name, "mode": client.mode},
                response_model=ReasoningTextResult,
                error_code="reasoning_generate_text_failed",
                error_details=lambda **_: {"provider": client.provider_name(), "model": client.resolved_model_name()},
            ),
            build_structured_runtime_tool(
                func=generate_json_tool,
                name="reasoning_generate_json",
                description="Use the configured reasoning runtime to generate a structured JSON payload.",
                args_schema=GenerateJsonArgs,
                component="reasoning_runtime",
                operation="generate_json",
                provider_name=client.provider_name,
                metadata=lambda: {"profile": client.profile.name, "mode": client.mode},
                response_model=ReasoningJsonResult,
                error_code="reasoning_generate_json_failed",
                error_details=lambda **_: {"provider": client.provider_name(), "model": client.resolved_model_name()},
            ),
        ]

    def _dispatch_json(
        self,
        prompt: str,
        *,
        max_tokens: int,
        response_format: Optional[dict],
        tools: Optional[list],
        tool_choice: Optional[object],
    ) -> dict[str, Any]:
        if self.mode in {self.MODE_DEEPSEEK, self.MODE_GPT_OSS}:
            return self._generate_json_ollama(prompt, max_tokens=max_tokens, response_format=response_format)
        if self.mode == self.MODE_GENERAL_COMPUTE:
            return self._generate_json_general_compute(
                prompt,
                max_tokens=max_tokens,
                response_format=response_format,
                tools=tools,
                tool_choice=tool_choice,
            )
        if self.mode == self.MODE_MISTRAL:
            return self._generate_json_mistral(prompt)
        if self.mode == self.MODE_GEMINI:
            return self._generate_json_gemini(prompt)
        raise ValueError(f"Unsupported mode '{self.mode}'.")

    def _dispatch_text(
        self,
        prompt: str,
        *,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        if self.mode in {self.MODE_DEEPSEEK, self.MODE_GPT_OSS}:
            return self._generate_text_ollama(
                self._compose_text_prompt(system_prompt, prompt),
                temperature=temperature,
                max_tokens=max_tokens,
            )
        if self.mode == self.MODE_GENERAL_COMPUTE:
            return self._generate_text_general_compute(
                prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        if self.mode == self.MODE_MISTRAL:
            return self._generate_text_mistral(
                prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        if self.mode == self.MODE_GEMINI:
            return self._generate_text_gemini(
                prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        raise ValueError(f"Unsupported mode '{self.mode}'.")

    def _generate_json_ollama(self, prompt: str, *, max_tokens: int, response_format: Optional[dict] = None) -> dict[str, Any]:
        url, headers, direct_cloud = self._ollama_transport()
        response = requests.post(
            url,
            headers=headers,
            json=self._ollama_payload(
                prompt=prompt,
                model_name=self.resolved_model_name(),
                direct_cloud=direct_cloud,
                json_mode=True,
                response_format=response_format,
                max_tokens=max_tokens,
                temperature=0.0,
            ),
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json() or {}
        return self._safe_parse_json(str(payload.get("response") or ""))

    def _generate_text_ollama(self, prompt: str, *, temperature: float, max_tokens: int) -> str:
        url, headers, direct_cloud = self._ollama_transport()
        response = requests.post(
            url,
            headers=headers,
            json=self._ollama_payload(
                prompt=prompt, model_name=self.resolved_model_name(), direct_cloud=direct_cloud,
                temperature=temperature, max_tokens=max_tokens,
            ),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return str((response.json() or {}).get("response") or "").strip()

    def _generate_vision_json_ollama(
        self,
        *,
        prompt: str,
        image_bytes: bytes,
        response_format: Optional[dict],
    ) -> dict[str, Any]:
        url, headers, _ = self._ollama_transport()
        model_name = self.resolved_model_name()
        translated_model = model_name[:-6] if model_name.endswith("-cloud") else model_name
        response = requests.post(
            url,
            headers=headers,
            json={
                "model": translated_model,
                "prompt": prompt,
                "images": [base64.b64encode(image_bytes).decode("ascii")],
                "stream": False,
                "format": self._ollama_json_format_payload(response_format),
                "options": {"temperature": 0},
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json() or {}
        content = str(payload.get("response") or (payload.get("message") or {}).get("content") or "")
        return self._safe_parse_json(content)

    def _generate_vision_json_mistral(self, *, prompt: str, image_bytes: bytes) -> dict[str, Any]:
        response = self._mistral_client_instance().chat.complete(
            model=self.resolved_model_name(),
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": f"data:image/png;base64,{base64.b64encode(image_bytes).decode('ascii')}",
                    },
                ],
            }],
            response_format={"type": "json_object"},
            temperature=0,
        )
        return self._safe_parse_json(str(response.choices[0].message.content or ""))

    def _generate_json_general_compute(
        self,
        prompt: str,
        *,
        max_tokens: int,
        response_format: Optional[dict],
        tools: Optional[list],
        tool_choice: Optional[object],
    ) -> dict[str, Any]:
        payload = {
            "model": self.resolved_model_name(),
            "messages": [{"role": "user", "content": self._apply_strict_mode(prompt)}],
            "temperature": 0.0,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format
        if tools:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        response = requests.post(
            self.config.general_compute_chat_url,
            headers=self._general_compute_headers(),
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        raw = response.json() or {}
        if tools:
            tool_payload = self._extract_general_compute_tool_calls(raw)
            if tool_payload is not None:
                return tool_payload
        return self._safe_parse_json(self._extract_general_compute_content(raw))

    def _generate_text_general_compute(
        self,
        prompt: str,
        *,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        response = requests.post(
            self.config.general_compute_chat_url,
            headers=self._general_compute_headers(),
            json={
                "model": self.resolved_model_name(),
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return self._extract_general_compute_content(response.json() or {}).strip()

    def _generate_json_mistral(self, prompt: str) -> dict[str, Any]:
        client = self._mistral_client_instance()
        response = client.chat.complete(
            model=self.resolved_model_name(),
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        return self._safe_parse_json(str(response.choices[0].message.content or ""))

    def _generate_text_mistral(
        self,
        prompt: str,
        *,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        client = self._mistral_client_instance()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        response = client.chat.complete(
            model=self.resolved_model_name(),
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return str(response.choices[0].message.content or "").strip()

    def _generate_json_gemini(self, prompt: str) -> dict[str, Any]:
        client = self._gemini_client_instance()
        response = client.models.generate_content(model=self.resolved_model_name(), contents=self._apply_strict_mode(prompt))
        return self._safe_parse_json(str(response.text or ""))

    def _generate_text_gemini(
        self,
        prompt: str,
        *,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        client = self._gemini_client_instance()
        input_text = self._compose_text_prompt(system_prompt, prompt)
        response = client.models.generate_content(
            model=self.resolved_model_name(),
            contents=input_text,
            config={"temperature": temperature, "max_output_tokens": max_tokens},
        )
        return str(response.text or "").strip()

    def _retry_json_request(
        self,
        func: Callable[[], dict[str, Any]],
        *,
        allow_rotation: bool = True,
        allow_fallback: bool = True,
    ) -> dict[str, Any]:
        last_error = "unknown_error"
        for attempt in range(self.max_retries):
            try:
                if self.base_delay:
                    time.sleep(self.base_delay)
                result = func()
                if isinstance(result, dict) and result.get("error") in {"empty_response", "parse_failed"}:
                    raise RuntimeError(str(result["error"]))
                return result
            except requests.HTTPError as exc:
                last_error = self._http_error_label(exc)
                if self._should_retry_http(exc, attempt, self.max_retries):
                    continue
                break
            except Exception as exc:
                last_error = str(exc)
                if self._should_retry_error_label(last_error, attempt, self.max_retries):
                    continue
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                break
        if self._is_rate_limit_label(last_error) and self.allow_account_rotation and allow_rotation and self._rotate_account():
            self._last_request_metadata.rotation_used = True
            self._last_request_metadata.rotation_attempt_count = int(self._last_request_metadata.rotation_attempt_count or 0) + 1
            return self._retry_json_request(func, allow_rotation=False, allow_fallback=allow_fallback)
        if allow_fallback and self.allow_cross_provider_fallback and self._activate_fallback_mode():
            self._last_request_metadata.fallback_used = True
            return self._retry_json_request(func, allow_rotation=True, allow_fallback=False)
        return {"error": "max_retries_exceeded", "last_error": last_error}

    def _retry_text_request(
        self,
        func: Callable[[], str],
        *,
        allow_rotation: bool = True,
        allow_fallback: bool = True,
    ) -> str:
        last_error = "unknown_error"
        for attempt in range(self.max_retries):
            try:
                if self.base_delay:
                    time.sleep(self.base_delay)
                result = str(func() or "").strip()
                if result:
                    return result
                raise RuntimeError("empty_response")
            except requests.HTTPError as exc:
                last_error = self._http_error_label(exc)
                if self._should_retry_http(exc, attempt, self.max_retries):
                    continue
                break
            except Exception as exc:
                last_error = str(exc)
                if self._should_retry_error_label(last_error, attempt, self.max_retries):
                    continue
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                break
        if self._is_rate_limit_label(last_error) and self.allow_account_rotation and allow_rotation and self._rotate_account():
            self._last_request_metadata.rotation_used = True
            self._last_request_metadata.rotation_attempt_count = int(self._last_request_metadata.rotation_attempt_count or 0) + 1
            return self._retry_text_request(func, allow_rotation=False, allow_fallback=allow_fallback)
        if allow_fallback and self.allow_cross_provider_fallback and self._activate_fallback_mode():
            self._last_request_metadata.fallback_used = True
            return self._retry_text_request(func, allow_rotation=True, allow_fallback=False)
        raise RuntimeError(last_error)

    def _activate_fallback_mode(self) -> bool:
        target_mode = self._fallback_mode_for(self.mode)
        if not target_mode:
            return False
        self._last_request_metadata.fallback_from_mode = self.mode
        self.mode = target_mode
        self._last_request_metadata.fallback_to_mode = self.mode
        return True

    def _fallback_mode_for(self, mode: str) -> str:
        normalized = str(mode or "").strip().lower()
        if normalized in {self.MODE_DEEPSEEK, self.MODE_GPT_OSS}:
            return self.MODE_GENERAL_COMPUTE
        if normalized == self.MODE_GENERAL_COMPUTE:
            return self.MODE_GPT_OSS
        return ""

    def _rotate_account(self) -> bool:
        if self.mode in {self.MODE_DEEPSEEK, self.MODE_GPT_OSS} and self._ollama_pool.rotate():
            self.config.ollama_active_index = self._ollama_pool.active_index
            return True
        if self.mode == self.MODE_GENERAL_COMPUTE and self._general_compute_pool.rotate():
            self.config.general_compute_active_index = self._general_compute_pool.active_index
            self.config.general_compute_last_request_index = self._general_compute_pool.last_request_index
            return True
        return False

    def _ollama_transport(self) -> tuple[str, dict[str, str], bool]:
        if self.profile.prefer_local_ollama:
            self._request_account_alias = self._ollama_pool.local_alias
            return self.config.ollama_local_url, {}, False
        api_key, alias = self._ollama_pool.acquire_for_request()
        self._request_account_alias = alias
        self.config.ollama_active_index = self._ollama_pool.active_index
        if api_key:
            return self.config.ollama_cloud_url, {"Authorization": f"Bearer {api_key}"}, True
        return self.config.ollama_local_url, {}, False

    def _ollama_payload(
        self,
        *,
        prompt: str,
        model_name: str,
        direct_cloud: bool,
        json_mode: bool = False,
        response_format: Optional[dict] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        translated_model = model_name[:-6] if model_name.endswith("-cloud") else model_name
        payload: dict[str, Any] = {
            "model": translated_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": max(0.0, float(temperature)),
                "num_predict": max(1, int(max_tokens)),
            },
        }
        if "gpt-oss" in translated_model.lower():
            payload["think"] = "low"
        if json_mode:
            payload["format"] = self._ollama_json_format_payload(response_format)
        return payload

    def _general_compute_headers(self) -> dict[str, str]:
        api_key = self._general_compute_pool.acquire_api_key_for_request()
        self.config.general_compute_active_index = self._general_compute_pool.active_index
        self.config.general_compute_last_request_index = self._general_compute_pool.last_request_index
        if not api_key:
            raise ValueError("No General Compute API key configured.")
        return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    def _mistral_client_instance(self):
        if self._mistral_client is None:
            api_key = str(self.config.mistral_api_key or os.getenv("MISTRAL_API_KEY") or "").strip()
            if not api_key:
                raise ValueError("MISTRAL_API_KEY not configured.")
            if Mistral is None:
                raise ImportError("mistralai package is not installed")
            self._mistral_client = Mistral(api_key=api_key)
        return self._mistral_client

    def _gemini_client_instance(self):
        if self._gemini_client is None:
            api_key = str(self.config.gemini_api_key or os.getenv("GEMINI_API_KEY") or "").strip()
            if not api_key:
                raise ValueError("GEMINI_API_KEY not configured.")
            if genai is None:
                raise ImportError("google-genai package is not installed")
            self._gemini_client = genai.Client(api_key=api_key)
        return self._gemini_client

    def _begin_request_tracking(self) -> None:
        self._request_account_alias = ""
        trace_context = current_trace_context()
        self._last_request_metadata = ReasoningRequestMetadata(
            trace_id=create_trace(
                component="reasoning_runtime",
                operation="reasoning_request",
                provider=self.provider_name(),
                metadata={"profile": self.profile.name, "mode": self.mode},
            ).trace_id,
            run_id=str(trace_context.get("run_id") or "").strip(),
            parent_trace_id=str(trace_context.get("parent_trace_id") or "").strip(),
            component="reasoning_runtime",
            operation="reasoning_request",
            provider=self.provider_name(),
            started_at_ms=int(time.time() * 1000),
            status="started",
            provider_family=self.provider_name(),
            resolved_model=self.resolved_model_name(),
            provider_account_alias=self._current_account_alias(),
            request_kind=self._pending_request_kind,
            json_mode=self._pending_json_mode,
            response_format_type=self._pending_response_format_type,
            tool_mode=self._pending_tool_mode,
            rotation_used=False,
            rotation_attempt_count=0,
            fallback_used=False,
        )

    def _finalize_request_tracking(self) -> None:
        completed_at_ms = int(time.time() * 1000)
        self._last_request_metadata.provider_family = self.provider_name()
        self._last_request_metadata.resolved_model = self.resolved_model_name()
        self._last_request_metadata.provider_account_alias = self._current_account_alias()
        self._last_request_metadata.provider = self.provider_name()
        self._last_request_metadata.completed_at_ms = completed_at_ms
        self._last_request_metadata.latency_ms = max(
            0,
            completed_at_ms - int(self._last_request_metadata.started_at_ms or completed_at_ms),
        )
        if str(self._last_request_metadata.status or "").strip() in {"", "started"}:
            self._last_request_metadata.status = "ok"
        self._pending_request_kind = ""
        self._pending_json_mode = ""
        self._pending_response_format_type = ""
        self._pending_tool_mode = ""

    def _current_account_alias(self) -> str:
        if self.mode in {self.MODE_DEEPSEEK, self.MODE_GPT_OSS}:
            return self._request_account_alias or self._ollama_pool.current_label()
        if self.mode == self.MODE_GENERAL_COMPUTE:
            return self._general_compute_pool.current_label()
        return ""

    @staticmethod
    def _should_retry_http(exc: requests.HTTPError, attempt: int, max_retries: int) -> bool:
        status_code = exc.response.status_code if exc.response is not None else None
        if attempt < 0 or attempt >= max_retries - 1:
            return False
        if status_code in {429, 402}:
            retry_after = str(exc.response.headers.get("Retry-After") or "").strip() if exc.response is not None else ""
            delay_seconds = float(retry_after) if retry_after.replace(".", "", 1).isdigit() else min(8 * (attempt + 1), 24)
            time.sleep(max(1.0, delay_seconds))
            return True
        if status_code and status_code >= 500:
            time.sleep(2 ** attempt)
            return True
        return False

    @classmethod
    def _should_retry_error_label(cls, label: str, attempt: int, max_retries: int) -> bool:
        if attempt < 0 or attempt >= max_retries - 1:
            return False
        if cls._is_rate_limit_label(label):
            time.sleep(min(8 * (attempt + 1), 24))
            return True
        return False

    @staticmethod
    def _http_error_label(exc: requests.HTTPError) -> str:
        status_code = exc.response.status_code if exc.response is not None else "unknown"
        return f"HTTP {status_code} {str(exc)}"

    @staticmethod
    def _is_rate_limit_label(label: str) -> bool:
        lowered = str(label or "").lower()
        return any(token in lowered for token in ("429", "rate", "quota", "balance", "402"))

    @staticmethod
    def _apply_strict_mode(prompt: str) -> str:
        return "Return ONLY valid JSON.\nNO markdown.\nNO explanations.\nNO extra text.\n\n" + str(prompt or "")

    @staticmethod
    def _response_format_type(response_format: Optional[dict]) -> str:
        if not isinstance(response_format, dict):
            return ""
        return str(response_format.get("type") or "").strip()

    @classmethod
    def _ollama_json_format_payload(cls, response_format: Optional[dict]) -> str | dict[str, Any]:
        if isinstance(response_format, dict) and response_format:
            json_schema = response_format.get("json_schema")
            if isinstance(json_schema, dict) and json_schema:
                schema = json_schema.get("schema")
                if isinstance(schema, dict) and schema:
                    return schema
        return "json"

    @staticmethod
    def _compose_text_prompt(system_prompt: str, prompt: str) -> str:
        if not system_prompt:
            return prompt
        return f"System:\n{system_prompt}\n\nUser:\n{prompt}"

    @staticmethod
    def _extract_general_compute_content(payload: dict[str, Any]) -> str:
        choices = payload.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(str(item.get("text") or ""))
                elif isinstance(item, str):
                    parts.append(item)
            return "".join(parts)
        return str(content or "")

    @staticmethod
    def _extract_general_compute_tool_calls(payload: dict[str, Any]) -> dict[str, Any] | None:
        choices = payload.get("choices") or []
        if not choices:
            return None
        message = choices[0].get("message") or {}
        tool_calls = message.get("tool_calls") or []
        if not isinstance(tool_calls, list) or not tool_calls:
            return None
        normalized = []
        for item in tool_calls:
            if not isinstance(item, dict):
                continue
            function = item.get("function") or {}
            name = str(function.get("name") or "").strip()
            if not name:
                continue
            raw_arguments = function.get("arguments")
            if isinstance(raw_arguments, dict):
                arguments = raw_arguments
            else:
                try:
                    arguments = json.loads(str(raw_arguments or ""))
                except Exception:
                    arguments = {}
            normalized.append({"tool": name, "arguments": arguments})
        return {"tool_calls": normalized} if normalized else None

    @classmethod
    def _safe_parse_json(cls, content: str) -> dict[str, Any]:
        raw = str(content or "").lstrip("\ufeff").strip()
        if not raw:
            return {"error": "empty_response"}
        try:
            return json.loads(raw)
        except Exception:
            pass
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        return {"error": "parse_failed", "raw_output": raw}
