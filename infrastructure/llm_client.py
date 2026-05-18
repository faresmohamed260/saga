"""Shared JSON-first LLM client used across the production pipeline.

The client hides provider-specific request details and centralizes retry,
timeout, and logging behavior for dashboard and service code.
"""

import json
import logging
import os
import re
import time
from functools import lru_cache
from typing import Callable, Optional

import requests
try:
    from google import genai
except ImportError:  # pragma: no cover - optional runtime dependency
    genai = None

try:
    from mistralai import Mistral
except ImportError:  # pragma: no cover - optional runtime dependency
    Mistral = None

from infrastructure.ollama_account_rotator import OllamaAccountRotator


class LLMClient:
    """
    Multi-provider JSON-first LLM client.

    Supported modes:
    - deepseek: Ollama-backed DeepSeek model
    - gpt_oss: Ollama-backed GPT-OSS model
    - mistral: hosted Mistral API
    - gemini: hosted Gemini API

    The legacy "local" mode is still accepted as an alias for "deepseek"
    so existing modules keep working while the new architecture is rolled out.
    """

    MODE_LOCAL_ALIAS = "local"
    MODE_DEEPSEEK = "deepseek"
    MODE_GPT_OSS = "gpt_oss"
    MODE_MISTRAL = "mistral"
    MODE_GEMINI = "gemini"
    OLLAMA_LOCAL_URL = "http://localhost:11434/api/generate"
    OLLAMA_CLOUD_URL = "https://ollama.com/api/generate"

    def __init__(
        self,
        mode: str = MODE_GPT_OSS,
        mistral_model: str = "mistral-large-2512",
        gemini_model: str = "gemini-2.0-flash",
        deepseek_model: str = "deepseek-v3.1:671b-cloud",
        gpt_oss_model: str = "gpt-oss:120b-cloud",
        ollama_model_override: str = "",
        max_retries: int = 5,
        base_delay: float = 1.0,
        timeout: int = 180,
    ):
        requested_mode = (mode or self.MODE_GPT_OSS).lower()
        self.mode = self._normalize_mode(requested_mode)

        self.mistral_model = mistral_model
        self.gemini_model_name = gemini_model
        self.deepseek_model = deepseek_model
        self.gpt_oss_model = gpt_oss_model
        self.ollama_model_override = str(ollama_model_override or "").strip()

        self.mistral_api_key = os.getenv("MISTRAL_API_KEY")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")

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

        self.base_delay = max(0.0, float(base_delay))
        self.max_retries = max(1, int(max_retries))
        self.timeout = max(1, int(timeout))
        self.json_failures = 0
        self.ollama_account_rotator = OllamaAccountRotator()
        self.ollama_url = self.OLLAMA_LOCAL_URL
        self.ollama_headers: dict[str, str] = {}
        self.ollama_direct_cloud = False
        self._refresh_ollama_transport()

        if requested_mode == self.MODE_LOCAL_ALIAS:
            logging.warning("LLMClient mode='local' is deprecated; use 'deepseek' or 'gpt_oss'.")

    def generate_json(self, prompt: str, strict: bool = False, validator: Optional[Callable] = None) -> dict:
        start_time = time.time()

        if strict:
            prompt = self._apply_strict_mode(prompt)

        logging.info("LLM Request | Mode: %s | Prompt chars: %s", self.mode, len(prompt))

        if self.mode in {self.MODE_DEEPSEEK, self.MODE_GPT_OSS}:
            result = self._retry_wrapper(self._generate_json_ollama, prompt)
        elif self.mode == self.MODE_MISTRAL:
            result = self._retry_wrapper(self._generate_json_mistral, prompt)
            if "error" in result:
                logging.warning("Mistral failed; falling back to DeepSeek Ollama mode")
                result = self._retry_wrapper(
                    lambda current_prompt: self._generate_json_ollama(current_prompt, model_name=self.deepseek_model),
                    prompt,
                )
        elif self.mode == self.MODE_GEMINI:
            result = self._retry_wrapper(self._generate_json_gemini, prompt)
            if "error" in result:
                logging.warning("Gemini failed; falling back to DeepSeek Ollama mode")
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
                return {"error": "validation_failed", "raw_output": result}

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
        return result

    def _normalize_mode(self, mode: str) -> str:
        if mode == self.MODE_LOCAL_ALIAS:
            return self.MODE_DEEPSEEK

        valid_modes = {
            self.MODE_DEEPSEEK,
            self.MODE_GPT_OSS,
            self.MODE_MISTRAL,
            self.MODE_GEMINI,
        }
        if mode not in valid_modes:
            raise ValueError(f"Unsupported mode: {mode}")
        return mode

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
        if "429" in str(last_error) or "rate_limit" in str(last_error):
            if allow_rotation and self.mode in {self.MODE_DEEPSEEK, self.MODE_GPT_OSS}:
                rotation_result = self._rotate_ollama_account()
                if rotation_result.get("status") == "rotated":
                    logging.warning(
                        "Rotated Ollama account to %s after rate-limit exhaustion; retrying request once.",
                        rotation_result.get("label") or rotation_result.get("email") or "next account",
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
        if "429" in str(last_error) or "rate_limit" in str(last_error):
            if allow_rotation and self.mode in {self.MODE_DEEPSEEK, self.MODE_GPT_OSS}:
                rotation_result = self._rotate_ollama_account()
                if rotation_result.get("status") == "rotated":
                    logging.warning(
                        "Rotated Ollama account to %s after text rate-limit exhaustion; retrying once.",
                        rotation_result.get("label") or rotation_result.get("email") or "next account",
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

    def _safe_parse_json(self, content: str) -> dict:
        if not content:
            self.json_failures += 1
            return {"error": "empty_response"}

        try:
            return json.loads(content)
        except Exception:
            pass

        cleaned = content.replace("```json", "").replace("```", "").strip()
        json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)

        if json_match:
            try:
                return json.loads(json_match.group(0))
            except Exception:
                pass

        try:
            return json.loads(cleaned)
        except Exception:
            pass

        logging.warning("JSON parse failed")
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
