"""Shared JSON-first LLM client used across the production pipeline.

The client hides provider-specific request details and centralizes retry,
timeout, and logging behavior for dashboard and service code.
"""

import json
import hashlib
import logging
import os
import re
import subprocess
import tempfile
import threading
import time
from functools import lru_cache
from pathlib import Path
from typing import Callable, Optional

import requests
from openai import OpenAI
try:
    from google import genai
except ImportError:  # pragma: no cover - optional runtime dependency
    genai = None

try:
    from mistralai import Mistral
except ImportError:  # pragma: no cover - optional runtime dependency
    Mistral = None

from saga.providers.ollama_account_rotator import OllamaAccountRotator
from saga.providers.general_compute_account_rotator import GeneralComputeAccountRotator
from saga.providers.openai_account_store import OpenAIAccountStore
from saga.providers.codex_session_store import CodexSessionStore


class LLMClient:
    """
    Multi-provider JSON-first LLM client.

    Supported modes:
    - deepseek: Ollama-backed DeepSeek model
    - gpt_oss: Ollama-backed GPT-OSS model
    - codex: OpenAI/Codex-backed responses API model
    - mistral: hosted Mistral API
    - gemini: hosted Gemini API

    The legacy "local" mode is still accepted as an alias for "deepseek"
    so existing modules keep working while the new architecture is rolled out.
    """

    MODE_LOCAL_ALIAS = "local"
    MODE_DEEPSEEK = "deepseek"
    MODE_GPT_OSS = "gpt_oss"
    MODE_CODEX = "codex"
    MODE_MISTRAL = "mistral"
    MODE_GEMINI = "gemini"
    MODE_GENERAL_COMPUTE = "general_compute"
    OLLAMA_LOCAL_URL = "http://localhost:11434/api/generate"
    OLLAMA_CLOUD_URL = "https://ollama.com/api/generate"
    GENERAL_COMPUTE_CHAT_URL = "https://api.generalcompute.com/v1/chat/completions"
    HERMES_WSL_DISTRO = "Ubuntu-24.04"
    HERMES_WSL_BINARY = "~/.local/bin/hermes"
    _HERMES_CODEX_SEMAPHORE: threading.BoundedSemaphore | None = None

    def __init__(
        self,
        mode: str = MODE_GPT_OSS,
        mistral_model: str = "mistral-large-2512",
        gemini_model: str = "gemini-2.0-flash",
        deepseek_model: str = "deepseek-v3.1:671b-cloud",
        gpt_oss_model: str = "gpt-oss:120b-cloud",
        codex_model: str = "gpt-5.4-mini",
        general_compute_model: str = "deepseek-v3.1",
        ollama_model_override: str = "",
        max_retries: int = 5,
        base_delay: float = 1.0,
        timeout: int = 180,
        allow_account_rotation: bool = True,
        allow_cross_provider_fallback: bool = True,
    ):
        requested_mode = (mode or self.MODE_GPT_OSS).lower()
        self.mode = self._normalize_mode(requested_mode)

        self.mistral_model = mistral_model
        self.gemini_model_name = gemini_model
        self.deepseek_model = deepseek_model
        self.gpt_oss_model = gpt_oss_model
        self.codex_model = str(os.getenv("OPENAI_CODEX_MODEL") or codex_model or "gpt-5.4-mini").strip()
        self.general_compute_model = general_compute_model
        self.ollama_model_override = str(ollama_model_override or "").strip()

        self.mistral_api_key = os.getenv("MISTRAL_API_KEY")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.general_compute_api_key = str(os.getenv("GENERAL_COMPUTE_API_KEY") or "").strip()
        self.openai_api_key = str(os.getenv("OPENAI_API_KEY") or "").strip()
        self.openai_account_store = OpenAIAccountStore()
        self.codex_session_store = CodexSessionStore()
        self.openai_client: OpenAI | None = None
        self.codex_transport = ""

        if self.mode == self.MODE_MISTRAL:
            if not self.mistral_api_key:
                raise ValueError("MISTRAL_API_KEY not set")
            if Mistral is None:
                raise ImportError("mistralai package is not installed")
            self.mistral_client = Mistral(api_key=self.mistral_api_key)

        if self.mode == self.MODE_GEMINI:
            if not self.gemini_api_key:
                raise ValueError("GEMINI_API_KEY not set")
            if genai is None:
                raise ImportError("google-genai package is not installed")
            self.gemini_client = genai.Client(api_key=self.gemini_api_key)
        if self.mode == self.MODE_CODEX:
            self.codex_transport = self._resolve_codex_transport()
            if not self.codex_transport:
                raise ValueError("Codex is not configured. Set OPENAI_API_KEY or configure local Hermes/Codex device auth.")
            if self.codex_transport == "openai_api":
                resolved_key = self._resolve_openai_api_key()
                if not resolved_key:
                    raise ValueError("OPENAI_API_KEY not set and no local OpenAI/Codex account configured")
                self.openai_api_key = resolved_key
                self.openai_client = OpenAI(api_key=resolved_key)

        self.base_delay = max(0.0, float(base_delay))
        self.max_retries = max(1, int(max_retries))
        self.timeout = max(1, int(timeout))
        self.allow_account_rotation = bool(allow_account_rotation)
        self.allow_cross_provider_fallback = bool(allow_cross_provider_fallback)
        self.json_failures = 0
        self.ollama_account_rotator = OllamaAccountRotator()
        self.general_compute_account_rotator = GeneralComputeAccountRotator()
        self.ollama_url = self.OLLAMA_LOCAL_URL
        self.ollama_headers: dict[str, str] = {}
        self.ollama_direct_cloud = False
        self._last_request_metadata: dict[str, object] = {}
        self._refresh_ollama_transport()

        if requested_mode == self.MODE_LOCAL_ALIAS:
            logging.warning("LLMClient mode='local' is deprecated; use 'deepseek' or 'gpt_oss'.")

    def generate_json(
        self,
        prompt: str,
        strict: bool = False,
        validator: Optional[Callable] = None,
        max_tokens: int = 4096,
        response_format: Optional[dict] = None,
        tools: Optional[list] = None,
        tool_choice: Optional[object] = None,
    ) -> dict:
        start_time = time.time()
        self._begin_request_tracking()

        if strict:
            prompt = self._apply_strict_mode(prompt)

        logging.info("LLM Request | Mode: %s | Prompt chars: %s", self.mode, len(prompt))

        if self.mode in {self.MODE_DEEPSEEK, self.MODE_GPT_OSS}:
            result = self._retry_wrapper(self._generate_json_ollama, prompt)
        elif self.mode == self.MODE_CODEX:
            result = self._retry_wrapper(
                lambda current_prompt: self._generate_json_codex(
                    current_prompt,
                    max_tokens=max_tokens,
                    response_format=response_format,
                ),
                prompt,
            )
        elif self.mode == self.MODE_GENERAL_COMPUTE:
            result = self._retry_wrapper(
                lambda current_prompt: self._generate_json_general_compute(
                    current_prompt,
                    max_tokens=max_tokens,
                    response_format=response_format,
                    tools=tools,
                    tool_choice=tool_choice,
                ),
                prompt,
            )
        elif self.mode == self.MODE_MISTRAL:
            result = self._retry_wrapper(self._generate_json_mistral, prompt)
            if self.allow_cross_provider_fallback and "error" in result:
                logging.warning("Mistral failed; falling back to DeepSeek Ollama mode")
                self._mark_fallback_used()
                result = self._retry_wrapper(
                    lambda current_prompt: self._generate_json_ollama(current_prompt, model_name=self.deepseek_model),
                    prompt,
                )
        elif self.mode == self.MODE_GEMINI:
            result = self._retry_wrapper(self._generate_json_gemini, prompt)
            if self.allow_cross_provider_fallback and "error" in result:
                logging.warning("Gemini failed; falling back to DeepSeek Ollama mode")
                self._mark_fallback_used()
                result = self._retry_wrapper(
                    lambda current_prompt: self._generate_json_ollama(current_prompt, model_name=self.deepseek_model),
                    prompt,
                )
        else:
            return {"error": "invalid_mode"}

        duration = round(time.time() - start_time, 2)
        logging.info("LLM Response Time: %ss", duration)

        if validator and isinstance(result, dict) and "error" not in result:
            if not validator(result):
                logging.warning("Response failed validation")
                self._finalize_request_tracking()
                return {"error": "validation_failed", "raw_output": result}

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
        start_time = time.time()
        self._begin_request_tracking()
        combined_prompt = self._compose_text_prompt(system_prompt, prompt)
        logging.info("LLM Text Request | Mode: %s | Prompt chars: %s", self.mode, len(combined_prompt))

        if self.mode in {self.MODE_DEEPSEEK, self.MODE_GPT_OSS}:
            result = self._retry_text_wrapper(
                lambda current_prompt: self._generate_text_ollama(
                    current_prompt,
                    model_name=self._ollama_model_for_mode(),
                ),
                combined_prompt,
            )
        elif self.mode == self.MODE_CODEX:
            result = self._retry_text_wrapper(
                lambda current_prompt: self._generate_text_codex(
                    system_prompt,
                    prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ),
                combined_prompt,
            )
        elif self.mode == self.MODE_GENERAL_COMPUTE:
            result = self._retry_text_wrapper(
                lambda current_prompt: self._generate_text_general_compute(
                    system_prompt,
                    prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ),
                combined_prompt,
            )
        elif self.mode == self.MODE_MISTRAL:
            result = self._retry_text_wrapper(
                lambda current_prompt: self._generate_text_mistral(
                    system_prompt,
                    prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ),
                combined_prompt,
            )
        elif self.mode == self.MODE_GEMINI:
            result = self._retry_text_wrapper(
                lambda current_prompt: self._generate_text_gemini(
                    current_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ),
                combined_prompt,
            )
        else:
            raise RuntimeError("invalid_mode")

        duration = round(time.time() - start_time, 2)
        logging.info("LLM Text Response Time: %ss", duration)
        self._finalize_request_tracking()
        return result

    def _normalize_mode(self, mode: str) -> str:
        if mode == self.MODE_LOCAL_ALIAS:
            return self.MODE_DEEPSEEK

        valid_modes = {
            self.MODE_DEEPSEEK,
            self.MODE_GPT_OSS,
            self.MODE_CODEX,
            self.MODE_GENERAL_COMPUTE,
            self.MODE_MISTRAL,
            self.MODE_GEMINI,
        }
        if mode not in valid_modes:
            raise ValueError(f"Unsupported mode: {mode}")
        return mode

    def provider_name(self) -> str:
        if self.mode in {self.MODE_DEEPSEEK, self.MODE_GPT_OSS}:
            return "ollama"
        if self.mode == self.MODE_CODEX:
            return "openai-codex"
        if self.mode == self.MODE_GENERAL_COMPUTE:
            return "general_compute"
        if self.mode == self.MODE_MISTRAL:
            return "mistral"
        if self.mode == self.MODE_GEMINI:
            return "gemini"
        return self.mode

    def resolved_model_name(self) -> str:
        if self.mode in {self.MODE_DEEPSEEK, self.MODE_GPT_OSS}:
            return self._ollama_model_for_mode()
        if self.mode == self.MODE_CODEX:
            return self._codex_model_for_mode()
        if self.mode == self.MODE_GENERAL_COMPUTE:
            return self._general_compute_model_for_mode()
        if self.mode == self.MODE_MISTRAL:
            return self.mistral_model
        if self.mode == self.MODE_GEMINI:
            return self.gemini_model_name
        return ""

    def provider_config_hash(self) -> str:
        payload = {
            "provider": self.provider_name(),
            "mode": self.mode,
            "model": self.resolved_model_name(),
            "transport": self.codex_transport if self.mode == self.MODE_CODEX else "",
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "allow_account_rotation": self.allow_account_rotation,
            "allow_cross_provider_fallback": self.allow_cross_provider_fallback,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]

    def current_account_alias(self) -> str:
        if self.mode in {self.MODE_DEEPSEEK, self.MODE_GPT_OSS}:
            env_key = str(os.getenv("OLLAMA_API_KEY") or "").strip()
            if env_key:
                return "env_ollama_api_key"
            account = self.ollama_account_rotator.active_account()
            if account and account.label:
                return str(account.label)
            if self.ollama_direct_cloud:
                return "ollama_cloud"
            return "ollama_local"
        if self.mode == self.MODE_GENERAL_COMPUTE:
            env_key = str(os.getenv("GENERAL_COMPUTE_API_KEY") or "").strip()
            if env_key:
                return "env_general_compute_api_key"
            account = self.general_compute_account_rotator.active_account()
            if account and account.label:
                return str(account.label)
            return "general_compute_unconfigured"
        if self.mode == self.MODE_CODEX:
            env_key = str(os.getenv("OPENAI_API_KEY") or "").strip()
            if env_key:
                return "env_openai_api_key"
            account = self.openai_account_store.active_account()
            if account and account.label:
                return str(account.label)
            if self.codex_transport == "hermes":
                return "hermes_openai_codex"
            session = self.codex_session_store.active_session()
            if session:
                return f"codex_session:{session.auth_mode or 'chatgpt'}"
            return "openai_unconfigured"
        return ""

    @classmethod
    def _hermes_codex_max_concurrency(cls) -> int:
        raw = str(os.getenv("SAGA_HERMES_CODEX_MAX_CONCURRENCY") or "1").strip()
        try:
            return max(1, int(raw))
        except Exception:
            return 1

    @classmethod
    def _hermes_codex_semaphore(cls) -> threading.BoundedSemaphore:
        max_concurrency = cls._hermes_codex_max_concurrency()
        semaphore = cls._HERMES_CODEX_SEMAPHORE
        if semaphore is None or getattr(semaphore, "_initial_value", max_concurrency) != max_concurrency:
            semaphore = threading.BoundedSemaphore(max_concurrency)
            setattr(semaphore, "_initial_value", max_concurrency)
            cls._HERMES_CODEX_SEMAPHORE = semaphore
        return semaphore

    @classmethod
    def _codex_hermes_timeout_budget(cls, prompt: str, timeout_seconds: int) -> int:
        base_timeout = max(30, int(timeout_seconds))
        prompt_chars = len(str(prompt or ""))
        prompt_slack = min(240, max(30, prompt_chars // 120))
        return max(base_timeout + 30, base_timeout + prompt_slack)

    def last_request_metadata(self) -> dict:
        base = {
            "provider_family": self.provider_name(),
            "resolved_model": self.resolved_model_name(),
            "provider_account_alias": self.current_account_alias(),
            "rotation_used": False,
            "rotation_attempt_count": 0,
            "fallback_used": False,
        }
        base.update(self._last_request_metadata or {})
        return dict(base)

    def _begin_request_tracking(self) -> None:
        self._last_request_metadata = {
            "provider_family": self.provider_name(),
            "resolved_model": self.resolved_model_name(),
            "provider_account_alias": self.current_account_alias(),
            "rotation_used": False,
            "rotation_attempt_count": 0,
            "fallback_used": False,
        }

    def _finalize_request_tracking(self) -> None:
        if not self._last_request_metadata:
            self._begin_request_tracking()
        self._last_request_metadata["provider_family"] = self.provider_name()
        self._last_request_metadata["resolved_model"] = self.resolved_model_name()
        self._last_request_metadata["provider_account_alias"] = self.current_account_alias()

    def _mark_rotation(self, alias: str = "") -> None:
        if not self._last_request_metadata:
            self._begin_request_tracking()
        self._last_request_metadata["rotation_used"] = True
        self._last_request_metadata["rotation_attempt_count"] = int(self._last_request_metadata.get("rotation_attempt_count") or 0) + 1
        if alias:
            self._last_request_metadata["provider_account_alias"] = alias

    def _mark_fallback_used(self) -> None:
        if not self._last_request_metadata:
            self._begin_request_tracking()
        self._last_request_metadata["fallback_used"] = True

    @classmethod
    def classify_error(cls, error: str, last_error: str = "") -> str:
        joined = " ".join([str(error or ""), str(last_error or "")]).strip().lower()
        if not joined:
            return ""
        if "general compute key pool exhausted" in joined or "key pool exhausted" in joined:
            return "provider_exhausted"
        if "rate_limited_exhausted" in joined:
            return "provider_exhausted"
        if "429" in joined or "rate limit" in joined or "rate_limited" in joined:
            return "provider_rate_limited"
        if "quota" in joined or "balance exhaustion" in joined or "402" in joined:
            return "quota_error"
        if "model_access_forbidden" in joined or "403" in joined or "forbidden" in joined or "subscription" in joined:
            return "authentication_error"
        if "parse_failed" in joined or "json parse failed" in joined:
            return "json_parse_failed"
        if "validation_failed" in joined:
            return "validation_failed"
        if "timed out" in joined or "timeout" in joined:
            return "timeout"
        if "connection" in joined or "network" in joined:
            return "network_error"
        if "model" in joined and "unavailable" in joined:
            return "model_unavailable"
        if "max_retries_exceeded" in joined:
            return "max_retries_exceeded"
        return "unknown_model_error"

    def _retry_wrapper(self, func, prompt: str, *, allow_rotation: bool = True) -> dict:
        last_error = "unknown_error"
        for attempt in range(self.max_retries):
            try:
                if self.base_delay:
                    time.sleep(self.base_delay)
                result = func(prompt)

                if isinstance(result, dict) and "error" not in result:
                    return result

                error = result.get("error", "unknown_error") if isinstance(result, dict) else "unknown_error"
                last_error = error
                raise RuntimeError(error)
            except requests.HTTPError as exc:
                status_code = exc.response.status_code if exc.response is not None else None
                retry_after = self._retry_after_seconds(exc.response)
                if status_code == 429:
                    wait = retry_after if retry_after is not None else min(8 * (attempt + 1), 45)
                    last_error = f"HTTP 429 rate_limited"
                    if attempt >= self.max_retries - 1:
                        logging.warning("Attempt %s hit rate limit (429); no retries remaining", attempt + 1)
                        break
                    logging.warning("Attempt %s hit rate limit (429); retry in %ss", attempt + 1, wait)
                    time.sleep(wait)
                    continue
                if status_code == 402:
                    last_error = self._http_error_label(exc)
                    if attempt >= self.max_retries - 1:
                        logging.warning("Attempt %s failed with quota/balance exhaustion: %s", attempt + 1, last_error)
                        break
                    logging.warning("Attempt %s failed with quota/balance exhaustion: %s; retrying.", attempt + 1, last_error)
                    continue
                if status_code == 403:
                    last_error = self._http_error_label(exc)
                    logging.warning("Attempt %s failed with forbidden model access: %s", attempt + 1, last_error)
                    break
                last_error = str(exc)
                wait = 2 ** attempt
                if attempt >= self.max_retries - 1:
                    logging.warning("Attempt %s failed: %s; no retries remaining", attempt + 1, exc)
                    break
                logging.warning("Attempt %s failed: %s; retry in %ss", attempt + 1, exc, wait)
                time.sleep(wait)
            except Exception as exc:
                last_error = str(exc)
                wait = 2 ** attempt
                if attempt >= self.max_retries - 1:
                    logging.warning("Attempt %s failed: %s; no retries remaining", attempt + 1, exc)
                    break
                logging.warning("Attempt %s failed: %s; retry in %ss", attempt + 1, exc, wait)
                time.sleep(wait)

        logging.error("All retries failed")
        if "429" in str(last_error) or "rate_limit" in str(last_error) or "402" in str(last_error) or "quota" in str(last_error) or "balance" in str(last_error):
            if self.allow_account_rotation and allow_rotation and self.mode in {self.MODE_DEEPSEEK, self.MODE_GPT_OSS}:
                rotation_result = self._rotate_ollama_account()
                if rotation_result.get("status") == "rotated":
                    self._mark_rotation(str(rotation_result.get("label") or rotation_result.get("email") or ""))
                    logging.warning(
                        "Rotated Ollama account to %s after rate-limit exhaustion; retrying request once.",
                        rotation_result.get("label") or rotation_result.get("email") or "next account",
                    )
                    return self._retry_wrapper(func, prompt, allow_rotation=False)
            if self.allow_account_rotation and allow_rotation and self.mode == self.MODE_GENERAL_COMPUTE:
                rotation_result = self._rotate_general_compute_account()
                if rotation_result.get("status") == "rotated":
                    self._mark_rotation(str(rotation_result.get("label") or ""))
                    logging.warning(
                        "Rotated General Compute key to %s after quota/rate-limit exhaustion; retrying request once.",
                        rotation_result.get("label") or "next key",
                    )
                    return self._retry_wrapper(func, prompt, allow_rotation=False)
            return {
                "error": "rate_limited_exhausted",
                "last_error": last_error,
                "rate_limit_exhausted": True,
            }
        if "403" in str(last_error) or "forbidden" in str(last_error) or "subscription" in str(last_error):
            return {
                "error": "model_access_forbidden",
                "last_error": last_error,
                "model_access_forbidden": True,
            }
        return {"error": "max_retries_exceeded", "last_error": last_error}

    def _retry_text_wrapper(self, func, prompt: str, *, allow_rotation: bool = True) -> str:
        last_error = "unknown_error"
        for attempt in range(self.max_retries):
            try:
                if self.base_delay:
                    time.sleep(self.base_delay)
                result = func(prompt)
                if isinstance(result, str) and result.strip():
                    return result.strip()
                last_error = "empty_response"
                raise RuntimeError(last_error)
            except requests.HTTPError as exc:
                status_code = exc.response.status_code if exc.response is not None else None
                retry_after = self._retry_after_seconds(exc.response)
                if status_code == 429:
                    wait = retry_after if retry_after is not None else min(8 * (attempt + 1), 45)
                    last_error = "HTTP 429 rate_limited"
                    if attempt >= self.max_retries - 1:
                        logging.warning("Text attempt %s hit rate limit (429); no retries remaining", attempt + 1)
                        break
                    logging.warning("Text attempt %s hit rate limit (429); retry in %ss", attempt + 1, wait)
                    time.sleep(wait)
                    continue
                if status_code == 402:
                    last_error = self._http_error_label(exc)
                    if attempt >= self.max_retries - 1:
                        logging.warning("Text attempt %s failed with quota/balance exhaustion: %s", attempt + 1, last_error)
                        break
                    logging.warning("Text attempt %s failed with quota/balance exhaustion: %s; retrying.", attempt + 1, last_error)
                    continue
                if status_code == 403:
                    last_error = self._http_error_label(exc)
                    logging.warning("Text attempt %s failed with forbidden model access: %s", attempt + 1, last_error)
                    break
                last_error = str(exc)
                wait = 2 ** attempt
                if attempt >= self.max_retries - 1:
                    logging.warning("Text attempt %s failed: %s; no retries remaining", attempt + 1, exc)
                    break
                logging.warning("Text attempt %s failed: %s; retry in %ss", attempt + 1, exc, wait)
                time.sleep(wait)
            except Exception as exc:
                last_error = str(exc)
                wait = 2 ** attempt
                if attempt >= self.max_retries - 1:
                    logging.warning("Text attempt %s failed: %s; no retries remaining", attempt + 1, exc)
                    break
                logging.warning("Text attempt %s failed: %s; retry in %ss", attempt + 1, exc, wait)
                time.sleep(wait)
        logging.error("All text retries failed")
        if "429" in str(last_error) or "rate_limit" in str(last_error) or "402" in str(last_error) or "quota" in str(last_error) or "balance" in str(last_error):
            if self.allow_account_rotation and allow_rotation and self.mode in {self.MODE_DEEPSEEK, self.MODE_GPT_OSS}:
                rotation_result = self._rotate_ollama_account()
                if rotation_result.get("status") == "rotated":
                    self._mark_rotation(str(rotation_result.get("label") or rotation_result.get("email") or ""))
                    logging.warning(
                        "Rotated Ollama account to %s after text rate-limit exhaustion; retrying once.",
                        rotation_result.get("label") or rotation_result.get("email") or "next account",
                    )
                    return self._retry_text_wrapper(func, prompt, allow_rotation=False)
            if self.allow_account_rotation and allow_rotation and self.mode == self.MODE_GENERAL_COMPUTE:
                rotation_result = self._rotate_general_compute_account()
                if rotation_result.get("status") == "rotated":
                    self._mark_rotation(str(rotation_result.get("label") or ""))
                    logging.warning(
                        "Rotated General Compute key to %s after text quota/rate-limit exhaustion; retrying once.",
                        rotation_result.get("label") or "next key",
                    )
                    return self._retry_text_wrapper(func, prompt, allow_rotation=False)
            raise RuntimeError("rate_limited_exhausted")
        if "403" in str(last_error) or "forbidden" in str(last_error) or "subscription" in str(last_error):
            raise RuntimeError("model_access_forbidden")
        raise RuntimeError(f"max_retries_exceeded: {last_error}")

    @classmethod
    @lru_cache(maxsize=64)
    def probe_ollama_mode_access(cls, mode: str, model_name: str, api_key: str | None = None) -> dict:
        transport = cls._resolve_probe_transport(api_key=api_key)
        response = requests.post(
            transport["url"],
            headers=transport["headers"],
            json={
                "model": cls._translate_ollama_model_name(model_name, transport["direct_cloud"]),
                "prompt": 'Respond with JSON: {"ok": true}',
                "stream": False,
            },
            timeout=30,
        )
        if response.status_code == 403:
            detail = ""
            try:
                detail = (response.json() or {}).get("error", "")
            except Exception:
                detail = response.text or ""
            return {
                "status": "forbidden",
                "mode": mode,
                "model": model_name,
                "detail": detail.strip(),
            }
        response.raise_for_status()
        return {
            "status": "ok",
            "mode": mode,
            "model": cls._translate_ollama_model_name(model_name, transport["direct_cloud"]),
        }

    def _rotate_ollama_account(self) -> dict:
        type(self).probe_ollama_mode_access.cache_clear()
        rotation_result = self.ollama_account_rotator.rotate_for_model(
            mode=self.mode,
            model_name=self._ollama_model_for_mode(),
            probe_callable=type(self).probe_ollama_mode_access,
        )
        if rotation_result.get("status") == "rotated":
            self._refresh_ollama_transport()
        return rotation_result

    @classmethod
    @lru_cache(maxsize=128)
    def probe_general_compute_model_access(cls, model_name: str, api_key: str | None = None) -> dict:
        resolved_api_key = str(api_key or os.getenv("GENERAL_COMPUTE_API_KEY") or "").strip()
        if not resolved_api_key:
            resolved_api_key = GeneralComputeAccountRotator().active_api_key().strip()
        if not resolved_api_key:
            return {"status": "unconfigured", "model": model_name, "detail": "No General Compute API key configured."}
        response = requests.post(
            cls.GENERAL_COMPUTE_CHAT_URL,
            headers={
                "Authorization": f"Bearer {resolved_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model_name,
                "messages": [{"role": "user", "content": 'Reply with exactly: {"ok": true}'}],
                "temperature": 0,
                "max_tokens": 32,
            },
            timeout=30,
        )
        if response.status_code in {401, 402, 403, 429}:
            detail = ""
            try:
                detail = json.dumps(response.json() or {}, ensure_ascii=False)
            except Exception:
                detail = response.text or ""
            return {
                "status": "forbidden" if response.status_code == 403 else "error",
                "model": model_name,
                "detail": detail.strip(),
                "http_status": response.status_code,
            }
        response.raise_for_status()
        return {"status": "ok", "model": model_name}

    @classmethod
    @lru_cache(maxsize=128)
    def probe_codex_model_access(cls, model_name: str, api_key: str | None = None) -> dict:
        resolved_api_key = str(api_key or os.getenv("OPENAI_API_KEY") or "").strip()
        if not resolved_api_key:
            resolved_api_key = OpenAIAccountStore().active_api_key().strip()
        if resolved_api_key:
            client = OpenAI(api_key=resolved_api_key)
            try:
                response = client.responses.create(
                    model=model_name,
                    input='Reply with exactly {"ok": true}',
                    max_output_tokens=32,
                    temperature=0,
                    text={"format": {"type": "json_object"}},
                )
                content = str(getattr(response, "output_text", "") or "").strip()
                if content:
                    return {"status": "ok", "model": model_name, "transport": "openai_api"}
                return {"status": "error", "model": model_name, "detail": "Empty OpenAI/Codex probe response.", "transport": "openai_api"}
            except Exception as exc:
                status_code = getattr(exc, "status_code", None)
                detail = str(exc)
                if status_code == 401 and "api.responses.write" in detail:
                    return {
                        "status": "session_insufficient_scope",
                        "model": model_name,
                        "detail": detail,
                        "http_status": status_code,
                        "transport": "openai_api",
                    }
                return {
                    "status": "forbidden" if status_code == 403 else "error",
                    "model": model_name,
                    "detail": detail,
                    "http_status": status_code,
                    "transport": "openai_api",
                }
        if not cls._hermes_codex_available():
            return {"status": "unconfigured", "model": model_name, "detail": "No OpenAI API key and Hermes Codex transport is unavailable."}
        try:
            content = cls._run_codex_hermes_prompt(
                model_name=model_name,
                prompt='Return ONLY valid JSON.\nNO markdown.\nNO extra text.\n{"ok": true}',
                timeout_seconds=45,
            )
            parsed = cls._safe_parse_json_static(content)
            if parsed.get("ok") is True:
                return {"status": "ok", "model": model_name, "transport": "hermes"}
            return {"status": "error", "model": model_name, "detail": f"Unexpected Hermes probe output: {content[:200]}", "transport": "hermes"}
        except Exception as exc:
            return {"status": "error", "model": model_name, "detail": str(exc), "transport": "hermes"}

    def _rotate_general_compute_account(self) -> dict:
        type(self).probe_general_compute_model_access.cache_clear()
        rotation_result = self.general_compute_account_rotator.rotate_for_model(
            model_name=self._general_compute_model_for_mode(),
            probe_callable=type(self).probe_general_compute_model_access,
        )
        if rotation_result.get("status") == "rotated":
            self.general_compute_api_key = self.general_compute_account_rotator.active_api_key().strip()
        return rotation_result

    def _generate_json_mistral(self, prompt: str) -> dict:
        response = self.mistral_client.chat.complete(
            model=self.mistral_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content.strip()
        return self._safe_parse_json(content)

    def _generate_json_gemini(self, prompt: str) -> dict:
        response = self.gemini_client.models.generate_content(
            model=self.gemini_model_name,
            contents=self._apply_strict_mode(prompt),
        )
        content = (response.text or "").strip()
        return self._safe_parse_json(content)

    def _generate_json_ollama(self, prompt: str, model_name: Optional[str] = None) -> dict:
        response = requests.post(
            self.ollama_url,
            headers=self.ollama_headers,
            json=self._ollama_generate_payload(
                prompt=prompt,
                model_name=model_name or self._ollama_model_for_mode(),
            ),
            timeout=self.timeout,
        )
        response.raise_for_status()

        result = response.json()
        content = result.get("response", "").strip()
        return self._safe_parse_json(content)

    def _generate_json_general_compute(
        self,
        prompt: str,
        *,
        max_tokens: int,
        response_format: Optional[dict] = None,
        tools: Optional[list] = None,
        tool_choice: Optional[object] = None,
    ) -> dict:
        estimated_input_tokens, estimated_output_tokens = self._estimate_general_compute_token_budget(
            self._apply_strict_mode(prompt),
            max_tokens=max_tokens,
        )
        request_payload = {
            "model": self._general_compute_model_for_mode(),
            "messages": [{"role": "user", "content": self._apply_strict_mode(prompt)}],
            "temperature": 0.0,
            "max_tokens": max_tokens,
        }
        if response_format:
            request_payload["response_format"] = response_format
        if tools:
            request_payload["tools"] = tools
        if tool_choice is not None:
            request_payload["tool_choice"] = tool_choice
        response = requests.post(
            self.GENERAL_COMPUTE_CHAT_URL,
            headers=self._general_compute_headers(
                estimated_input_tokens=estimated_input_tokens,
                estimated_output_tokens=estimated_output_tokens,
            ),
            json=request_payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        try:
            payload = response.json() or {}
        except Exception:
            raw_content = (response.text or "").strip()
            return self._safe_parse_json(raw_content)
        self._record_general_compute_usage(payload)
        if tools:
            tool_payload = self._extract_general_compute_tool_calls(payload)
            if tool_payload is not None:
                return tool_payload
        content = self._extract_general_compute_content(payload)
        return self._safe_parse_json(content)

    def _generate_json_codex(
        self,
        prompt: str,
        *,
        max_tokens: int,
        response_format: Optional[dict] = None,
    ) -> dict:
        if self.codex_transport == "hermes":
            return self._generate_json_codex_hermes(
                prompt,
                max_tokens=max_tokens,
                response_format=response_format,
            )
        client = self._codex_client()
        payload = {
            "model": self._codex_model_for_mode(),
            "input": prompt,
            "temperature": 0,
            "max_output_tokens": max_tokens,
        }
        if response_format and isinstance(response_format, dict) and response_format.get("type") == "json_schema":
            schema_payload = dict(response_format)
            schema_payload.setdefault("strict", True)
            payload["text"] = {"format": schema_payload}
        else:
            payload["text"] = {"format": {"type": "json_object"}}
        try:
            response = client.responses.create(**payload)
        except Exception as exc:
            raise self._as_http_error(exc)
        content = str(getattr(response, "output_text", "") or "").strip()
        return self._safe_parse_json(content)

    def _generate_text_mistral(
        self,
        system_prompt: str,
        prompt: str,
        *,
        temperature: float,
        max_tokens: int,
    ) -> str:
        response = self.mistral_client.chat.complete(
            model=self.mistral_model,
            messages=[
                *([{"role": "system", "content": system_prompt}] if system_prompt else []),
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return (response.choices[0].message.content or "").strip()

    def _generate_text_gemini(
        self,
        prompt: str,
        *,
        temperature: float,
        max_tokens: int,
    ) -> str:
        response = self.gemini_client.models.generate_content(
            model=self.gemini_model_name,
            contents=prompt,
            config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            },
        )
        return (response.text or "").strip()

    def _generate_text_ollama(self, prompt: str, model_name: Optional[str] = None) -> str:
        response = requests.post(
            self.ollama_url,
            headers=self.ollama_headers,
            json=self._ollama_generate_payload(
                prompt=prompt,
                model_name=model_name or self._ollama_model_for_mode(),
            ),
            timeout=self.timeout,
        )
        response.raise_for_status()
        result = response.json()
        return (result.get("response") or "").strip()

    def _generate_text_general_compute(
        self,
        system_prompt: str,
        prompt: str,
        *,
        temperature: float,
        max_tokens: int,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        estimated_input_tokens, estimated_output_tokens = self._estimate_general_compute_token_budget(
            "\n".join(str(item.get("content") or "") for item in messages),
            max_tokens=max_tokens,
        )
        response = requests.post(
            self.GENERAL_COMPUTE_CHAT_URL,
            headers=self._general_compute_headers(
                estimated_input_tokens=estimated_input_tokens,
                estimated_output_tokens=estimated_output_tokens,
            ),
            json={
                "model": self._general_compute_model_for_mode(),
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        try:
            payload = response.json() or {}
        except Exception:
            return (response.text or "").strip()
        self._record_general_compute_usage(payload)
        return self._extract_general_compute_content(payload).strip()

    def _generate_text_codex(
        self,
        system_prompt: str,
        prompt: str,
        *,
        temperature: float,
        max_tokens: int,
    ) -> str:
        if self.codex_transport == "hermes":
            return self._generate_text_codex_hermes(
                system_prompt,
                prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        client = self._codex_client()
        payload = {
            "model": self._codex_model_for_mode(),
            "input": prompt,
            "max_output_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_prompt:
            payload["instructions"] = system_prompt
        try:
            response = client.responses.create(**payload)
        except Exception as exc:
            raise self._as_http_error(exc)
        return str(getattr(response, "output_text", "") or "").strip()

    def _ollama_generate_payload(self, *, prompt: str, model_name: str) -> dict:
        request_model_name = self._translate_ollama_model_name(model_name, self.ollama_direct_cloud)
        payload = {
            "model": request_model_name,
            "prompt": prompt,
            "stream": False,
        }
        think = self._ollama_think_setting(request_model_name)
        if think is not None:
            payload["think"] = think
        return payload

    def _ollama_model_for_mode(self) -> str:
        if self.ollama_model_override:
            return self.ollama_model_override
        if self.mode == self.MODE_GPT_OSS:
            return self.gpt_oss_model
        return self.deepseek_model

    def _codex_model_for_mode(self) -> str:
        if self.ollama_model_override:
            return self.ollama_model_override
        return self.codex_model

    def _general_compute_model_for_mode(self) -> str:
        if self.ollama_model_override:
            candidate = str(self.ollama_model_override).strip()
            if candidate and not candidate.endswith("-cloud"):
                return candidate
        return self.general_compute_model

    def _ollama_think_setting(self, model_name: str) -> Optional[str]:
        if "gpt-oss" in str(model_name or "").lower():
            return "low"
        return None

    def _refresh_ollama_transport(self) -> None:
        if self.mode not in {self.MODE_DEEPSEEK, self.MODE_GPT_OSS}:
            self.ollama_url = self.OLLAMA_LOCAL_URL
            self.ollama_headers = {}
            self.ollama_direct_cloud = False
            return
        api_key = self._resolve_ollama_api_key()
        if api_key:
            self.ollama_url = self.OLLAMA_CLOUD_URL
            self.ollama_headers = {"Authorization": f"Bearer {api_key}"}
            self.ollama_direct_cloud = True
            return
        self.ollama_url = self.OLLAMA_LOCAL_URL
        self.ollama_headers = {}
        self.ollama_direct_cloud = False

    def _resolve_ollama_api_key(self) -> str:
        env_key = str(os.getenv("OLLAMA_API_KEY") or "").strip()
        if env_key:
            return env_key
        return self.ollama_account_rotator.active_api_key().strip()

    def _resolve_general_compute_api_key(
        self,
        *,
        estimated_input_tokens: int = 0,
        estimated_output_tokens: int = 0,
    ) -> str:
        env_key = str(os.getenv("GENERAL_COMPUTE_API_KEY") or "").strip()
        if env_key:
            return env_key
        selected = self.general_compute_account_rotator.acquire_api_key_for_request(
            estimated_input_tokens=estimated_input_tokens,
            estimated_output_tokens=estimated_output_tokens,
        ).strip()
        if selected:
            return selected
        return self.general_compute_account_rotator.active_api_key().strip()

    def _resolve_openai_api_key(self) -> str:
        env_key = str(os.getenv("OPENAI_API_KEY") or "").strip()
        if env_key:
            return env_key
        account_key = self.openai_account_store.active_api_key().strip()
        if account_key:
            return account_key
        return self.codex_session_store.active_access_token().strip()

    def _resolve_codex_transport(self) -> str:
        if self._has_direct_openai_credentials():
            return "openai_api"
        if self._hermes_codex_available():
            return "hermes"
        if self.codex_session_store.has_session():
            return "openai_api"
        return ""

    def _has_direct_openai_credentials(self) -> bool:
        return bool(str(os.getenv("OPENAI_API_KEY") or "").strip() or self.openai_account_store.active_api_key().strip())

    def _codex_client(self) -> OpenAI:
        resolved_key = self._resolve_openai_api_key()
        if not resolved_key:
            raise ValueError("OPENAI_API_KEY not set and no local OpenAI/Codex account configured")
        if self.openai_client is None or self.openai_api_key != resolved_key:
            self.openai_api_key = resolved_key
            self.openai_client = OpenAI(api_key=resolved_key)
        return self.openai_client

    def _generate_json_codex_hermes(
        self,
        prompt: str,
        *,
        max_tokens: int,
        response_format: Optional[dict] = None,
    ) -> dict:
        del max_tokens
        composed_prompt = self._compose_codex_json_prompt(prompt, response_format=response_format)
        content = self._run_codex_hermes_prompt(
            model_name=self._codex_model_for_mode(),
            prompt=composed_prompt,
            timeout_seconds=self.timeout,
        )
        return self._safe_parse_json(content)

    def _generate_text_codex_hermes(
        self,
        system_prompt: str,
        prompt: str,
        *,
        temperature: float,
        max_tokens: int,
    ) -> str:
        del temperature, max_tokens
        content = self._run_codex_hermes_prompt(
            model_name=self._codex_model_for_mode(),
            prompt=self._compose_text_prompt(system_prompt, prompt),
            timeout_seconds=self.timeout,
        )
        return str(content or "").strip()

    def _compose_codex_json_prompt(self, prompt: str, *, response_format: Optional[dict] = None) -> str:
        if response_format and isinstance(response_format, dict) and response_format.get("type") == "json_schema":
            schema_payload = json.dumps(response_format, ensure_ascii=False, indent=2)
            return (
                "Return ONLY valid JSON.\n"
                "NO markdown.\n"
                "NO extra text.\n"
                "The response MUST satisfy this JSON schema configuration exactly:\n"
                f"{schema_payload}\n\n"
                f"{prompt}"
            )
        return self._apply_strict_mode(prompt)

    @classmethod
    @lru_cache(maxsize=1)
    def _hermes_codex_available(cls) -> bool:
        try:
            result = subprocess.run(
                [
                    "wsl",
                    "-d",
                    cls.HERMES_WSL_DISTRO,
                    "bash",
                    "-lc",
                    f"test -x {cls.HERMES_WSL_BINARY} && test -f ~/.hermes/auth.json",
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            return result.returncode == 0
        except Exception:
            return False

    @classmethod
    def _run_codex_hermes_prompt(cls, *, model_name: str, prompt: str, timeout_seconds: int) -> str:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as handle:
            handle.write(prompt)
            prompt_path = Path(handle.name)
        try:
            wsl_prompt_path = cls._windows_path_to_wsl(prompt_path)
            wsl_code = (
                "import os, subprocess, sys; "
                "prompt_path = sys.argv[1]; "
                "model_name = sys.argv[2]; "
                "prompt = open(prompt_path, 'r', encoding='utf-8').read(); "
                "env = dict(os.environ); "
                "env['PYTHONIOENCODING'] = 'utf-8'; "
                "env['LC_ALL'] = 'C.UTF-8'; "
                "env['LANG'] = 'C.UTF-8'; "
                "cmd = [os.path.expanduser('~/.local/bin/hermes'), '--provider', 'openai-codex', '-m', model_name, '--yolo', '-z', prompt]; "
                "proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', env=env); "
                "sys.stdout.write(proc.stdout or ''); "
                "sys.stderr.write(proc.stderr or ''); "
                "raise SystemExit(proc.returncode)"
            )
            command = [
                "wsl",
                "-d",
                cls.HERMES_WSL_DISTRO,
                "python3",
                "-c",
                wsl_code,
                wsl_prompt_path,
                model_name,
            ]
            effective_timeout = cls._codex_hermes_timeout_budget(prompt, timeout_seconds)
            semaphore = cls._hermes_codex_semaphore()
            acquired = semaphore.acquire(timeout=max(30, effective_timeout))
            if not acquired:
                raise RuntimeError("Hermes Codex concurrency gate timed out before request could start")
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=effective_timeout,
                )
            except subprocess.TimeoutExpired as exc:
                partial_stdout = str(getattr(exc, "stdout", "") or "").strip()
                partial_stderr = str(getattr(exc, "stderr", "") or "").strip()
                detail = "\n".join(part for part in [partial_stderr, partial_stdout] if part).strip()
                prompt_chars = len(str(prompt or ""))
                raise RuntimeError(
                    f"Hermes Codex timed out after {effective_timeout}s "
                    f"(model={model_name}, prompt_chars={prompt_chars}, transport=hermes)"
                    + (f"\n{detail[:1000]}" if detail else "")
                ) from exc
            finally:
                semaphore.release()
            if result.returncode != 0:
                detail = "\n".join(part for part in [result.stderr.strip(), result.stdout.strip()] if part).strip()
                raise RuntimeError(detail or f"Hermes Codex command failed with exit code {result.returncode}")
            return str(result.stdout or "").strip()
        finally:
            try:
                prompt_path.unlink(missing_ok=True)
            except Exception:
                pass

    @staticmethod
    def _windows_path_to_wsl(path: Path) -> str:
        resolved = Path(path).resolve()
        drive = resolved.drive.rstrip(":").lower()
        tail = resolved.as_posix().split(":", 1)[-1].lstrip("/")
        if drive:
            return f"/mnt/{drive}/{tail}"
        return resolved.as_posix()

    @staticmethod
    def _safe_parse_json_static(content: str) -> dict:
        content = str(content or "").lstrip("\ufeff").strip()
        if not content:
            return {"error": "empty_response"}
        try:
            return json.loads(content)
        except Exception:
            pass
        cleaned = content.replace("```json", "").replace("```", "").lstrip("\ufeff").strip()
        json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except Exception:
                pass
        try:
            return json.loads(cleaned)
        except Exception:
            return {"error": "parse_failed", "raw_output": content}

    @classmethod
    def _resolve_probe_transport(cls, api_key: str | None = None) -> dict:
        resolved_api_key = str(api_key or os.getenv("OLLAMA_API_KEY") or "").strip()
        if not resolved_api_key:
            resolved_api_key = OllamaAccountRotator().active_api_key().strip()
        if resolved_api_key:
            return {
                "url": cls.OLLAMA_CLOUD_URL,
                "headers": {"Authorization": f"Bearer {resolved_api_key}"},
                "direct_cloud": True,
            }
        return {
            "url": cls.OLLAMA_LOCAL_URL,
            "headers": {},
            "direct_cloud": False,
        }

    @staticmethod
    def _translate_ollama_model_name(model_name: str, direct_cloud: bool) -> str:
        if direct_cloud and str(model_name or "").endswith("-cloud"):
            return str(model_name)[:-6]
        return model_name

    def _general_compute_headers(
        self,
        *,
        estimated_input_tokens: int = 0,
        estimated_output_tokens: int = 0,
    ) -> dict[str, str]:
        api_key = self._resolve_general_compute_api_key(
            estimated_input_tokens=estimated_input_tokens,
            estimated_output_tokens=estimated_output_tokens,
        )
        if not api_key:
            raise ValueError("GENERAL_COMPUTE_API_KEY not set and no local General Compute key pool configured")
        self.general_compute_api_key = api_key
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _record_general_compute_usage(self, payload: dict) -> None:
        usage = payload.get("usage") or {}
        total_tokens = int(usage.get("total_tokens") or usage.get("tokens") or 0)
        self.general_compute_account_rotator.record_usage(
            self.general_compute_api_key,
            total_tokens=total_tokens,
            request_count=1,
        )

    def _estimate_general_compute_tokens(self, content: str, *, max_tokens: int) -> int:
        input_estimate, output_estimate = self._estimate_general_compute_token_budget(content, max_tokens=max_tokens)
        return input_estimate + output_estimate

    def _estimate_general_compute_token_budget(self, content: str, *, max_tokens: int) -> tuple[int, int]:
        input_estimate = max(1, int(len(str(content or "")) / 4))
        output_estimate = max(0, int(max_tokens))
        return input_estimate, output_estimate

    def _extract_general_compute_content(self, payload: dict) -> str:
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

    def _extract_general_compute_tool_calls(self, payload: dict) -> dict | None:
        choices = payload.get("choices") or []
        if not choices:
            return None
        message = choices[0].get("message") or {}
        tool_calls = message.get("tool_calls") or []
        if not isinstance(tool_calls, list) or not tool_calls:
            return None
        normalized_calls = []
        for item in tool_calls:
            if not isinstance(item, dict):
                continue
            function = item.get("function") or {}
            name = str(function.get("name") or "").strip()
            if not name:
                continue
            raw_arguments = function.get("arguments")
            arguments = {}
            if isinstance(raw_arguments, dict):
                arguments = raw_arguments
            elif isinstance(raw_arguments, str):
                try:
                    arguments = json.loads(raw_arguments)
                except Exception:
                    arguments = {}
            normalized_calls.append({
                "tool": name,
                "arguments": arguments,
            })
        if not normalized_calls:
            return None
        return {"tool_calls": normalized_calls}

    def _as_http_error(self, exc: Exception) -> requests.HTTPError:
        status_code = getattr(exc, "status_code", None)
        body = str(exc)
        response = requests.Response()
        if status_code is not None:
            response.status_code = int(status_code)
        response._content = body.encode("utf-8", errors="replace")
        error = requests.HTTPError(body)
        error.response = response
        return error

    def _apply_strict_mode(self, prompt: str) -> str:
        return (
            "Return ONLY valid JSON.\n"
            "NO markdown.\n"
            "NO explanations.\n"
            "NO extra text.\n\n"
            f"{prompt}"
        )

    def _compose_text_prompt(self, system_prompt: str, prompt: str) -> str:
        if not system_prompt:
            return prompt
        return f"System:\n{system_prompt}\n\nUser:\n{prompt}"

    @staticmethod
    def _log_preview(text: str, limit: int = 600) -> str:
        cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[:limit] + " ..."

    @staticmethod
    def _extract_balanced_json_object(text: str) -> str:
        source = str(text or "")
        start = source.find("{")
        if start < 0:
            return ""
        depth = 0
        in_string = False
        escape = False
        for index in range(start, len(source)):
            char = source[index]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return source[start:index + 1]
        return ""

    def _safe_parse_json(self, content: str) -> dict:
        content = str(content or "").lstrip("\ufeff").strip()
        if not content:
            self.json_failures += 1
            return {"error": "empty_response"}

        try:
            return json.loads(content)
        except Exception:
            pass

        cleaned = content.replace("```json", "").replace("```", "").lstrip("\ufeff").strip()
        json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)

        if json_match:
            try:
                return json.loads(json_match.group(0))
            except Exception:
                pass

        balanced_object = self._extract_balanced_json_object(cleaned)
        if balanced_object:
            try:
                return json.loads(balanced_object)
            except Exception:
                pass

        try:
            return json.loads(cleaned)
        except Exception:
            pass

        logging.warning("JSON parse failed | excerpt=%s", self._log_preview(content))
        self.json_failures += 1
        return {
            "error": "parse_failed",
            "raw_output": content,
        }

    def _retry_after_seconds(self, response) -> Optional[int]:
        if response is None:
            return None
        header_value = response.headers.get("Retry-After")
        if not header_value:
            return None
        try:
            return max(1, int(header_value))
        except (TypeError, ValueError):
            return None

    def _http_error_label(self, exc: requests.HTTPError) -> str:
        status_code = exc.response.status_code if exc.response is not None else "unknown"
        body = ""
        if exc.response is not None:
            try:
                body = ((exc.response.json() or {}).get("error") or "").strip()
            except Exception:
                body = (exc.response.text or "").strip()
        if body:
            return f"HTTP {status_code} {body}"
        return str(exc)
