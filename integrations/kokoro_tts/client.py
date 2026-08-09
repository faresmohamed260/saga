"""Thin HTTP client for the deployed Kokoro Modal service."""

from __future__ import annotations

from typing import Any

import requests


class ModalKokoroTTSClient:
    def __init__(self, api_url: str, *, timeout_seconds: int = 300) -> None:
        self.api_url = str(api_url or "").strip()
        self.timeout_seconds = max(1, int(timeout_seconds))
        if not self.api_url:
            raise ValueError("api_url is required")

    def synthesize(
        self,
        *,
        text: str,
        voice: str = "af_bella",
        lang_code: str = "a",
        sample_rate: int = 24000,
        audio_format: str = "flac",
        normalize_audio: bool = True,
        trim_silence: bool = False,
        sentence_pause_ms: int = 0,
    ) -> dict[str, Any]:
        payload = {
            "text": str(text or ""),
            "voice": str(voice or "af_bella"),
            "lang_code": str(lang_code or "a"),
            "sample_rate": int(sample_rate or 24000),
            "audio_format": str(audio_format or "flac").strip().lower() or "flac",
            "normalize_audio": bool(normalize_audio),
            "trim_silence": bool(trim_silence),
            "sentence_pause_ms": int(sentence_pause_ms or 0),
        }
        response = requests.post(self.api_url, json=payload, timeout=self.timeout_seconds)
        response.raise_for_status()
        return {
            "audio_bytes": response.content,
            "media_type": str(response.headers.get("content-type") or "audio/wav"),
            "voice": str(response.headers.get("X-Kokoro-Voice") or payload["voice"]),
            "lang_code": str(response.headers.get("X-Kokoro-Lang-Code") or payload["lang_code"]),
            "sample_rate": int(response.headers.get("X-Kokoro-Sample-Rate") or payload["sample_rate"]),
            "audio_format": str(response.headers.get("X-Kokoro-Audio-Format") or payload["audio_format"]),
            "duration_seconds": float(response.headers.get("X-Kokoro-Duration-Seconds") or 0.0),
            "telemetry": {
                "request_id": str(response.headers.get("X-Kokoro-Request-Id") or ""),
                "chunk_count": int(response.headers.get("X-Kokoro-Chunk-Count") or 0),
                "total_samples": int(response.headers.get("X-Kokoro-Total-Samples") or 0),
                "encode_elapsed_seconds": float(response.headers.get("X-Kokoro-Encode-Elapsed-Seconds") or 0.0),
                "total_elapsed_seconds": float(response.headers.get("X-Kokoro-Total-Elapsed-Seconds") or 0.0),
            },
        }
