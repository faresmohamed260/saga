"""Modal application for the Kokoro speech synthesis provider."""

from __future__ import annotations

import io
import os
import time
import traceback
import uuid
from typing import Any

import modal
import numpy as np
import soundfile as sf
from pydantic import BaseModel, Field


APP_NAME = os.environ.get("MODAL_KOKORO_APP_NAME", "saga-tts-runtime")
MODAL_VERSION = "1.4.2"
PYTHON_VERSION = "3.11"
CPU_SIZE = int(os.environ.get("MODAL_KOKORO_CPU", "4"))
MEMORY_MB = int(os.environ.get("MODAL_KOKORO_MEMORY_MB", "8192"))
FUNCTION_TIMEOUT_SECONDS = int(os.environ.get("MODAL_KOKORO_TIMEOUT_SECONDS", "900"))
CONTAINER_IDLE_SECONDS = int(os.environ.get("MODAL_KOKORO_IDLE_SECONDS", "60"))
DEFAULT_LANG_CODE = os.environ.get("MODAL_KOKORO_LANG_CODE", "a")
DEFAULT_VOICE = os.environ.get("MODAL_KOKORO_DEFAULT_VOICE", "af_bella")
DEFAULT_SAMPLE_RATE = int(os.environ.get("MODAL_KOKORO_SAMPLE_RATE", "24000"))
# FLAC keeps the provider boundary compact while preserving lossless output.
DEFAULT_AUDIO_FORMAT = os.environ.get("MODAL_KOKORO_AUDIO_FORMAT", "flac").strip().lower() or "flac"

image = (
    modal.Image.debian_slim(python_version=PYTHON_VERSION)
    .apt_install("ffmpeg", "libsndfile1")
    .pip_install(
        f"modal=={MODAL_VERSION}",
        "fastapi[standard]==0.121.0",
        "kokoro",
        "numpy",
        "soundfile",
    )
)

app = modal.App(name=APP_NAME, image=image)


class SynthesizeRequest(BaseModel):
    text: str = Field(min_length=1)
    voice: str = DEFAULT_VOICE
    lang_code: str = DEFAULT_LANG_CODE
    sample_rate: int = DEFAULT_SAMPLE_RATE
    audio_format: str = DEFAULT_AUDIO_FORMAT
    normalize_audio: bool = True
    trim_silence: bool = False
    sentence_pause_ms: int = 0


def _apply_normalization(audio: np.ndarray) -> np.ndarray:
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak <= 0.0:
        return audio
    return np.clip(audio / peak * 0.97, -1.0, 1.0)


def _apply_trim(audio: np.ndarray, threshold: float = 0.0005) -> np.ndarray:
    if not audio.size:
        return audio
    active = np.flatnonzero(np.abs(audio) > threshold)
    if active.size == 0:
        return audio
    start = int(active[0])
    end = int(active[-1]) + 1
    return audio[start:end]


def _encode_audio(audio: np.ndarray, *, sample_rate: int, audio_format: str) -> tuple[bytes, str]:
    fmt = str(audio_format or "wav").strip().lower() or "wav"
    media_type = "audio/wav"
    if fmt == "flac":
        media_type = "audio/flac"
    elif fmt != "wav":
        raise ValueError(f"Unsupported audio_format '{audio_format}'")

    buffer = io.BytesIO()
    sf.write(buffer, audio, sample_rate, format=fmt.upper())
    return buffer.getvalue(), media_type


def _modal_log(event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    print(payload, flush=True)


@app.cls(
    image=image,
    cpu=CPU_SIZE,
    memory=MEMORY_MB,
    timeout=FUNCTION_TIMEOUT_SECONDS,
    scaledown_window=CONTAINER_IDLE_SECONDS,
)
class KokoroTTSService:
    @modal.enter()
    def load_pipeline(self) -> None:
        from kokoro import KPipeline

        self._pipeline_factory = KPipeline
        self._pipeline_lang_code = ""
        self._pipeline = None

    def _pipeline_for(self, lang_code: str):
        resolved_lang_code = str(lang_code or DEFAULT_LANG_CODE).strip() or DEFAULT_LANG_CODE
        if self._pipeline is None or self._pipeline_lang_code != resolved_lang_code:
            self._pipeline = self._pipeline_factory(lang_code=resolved_lang_code)
            self._pipeline_lang_code = resolved_lang_code
        return self._pipeline

    @modal.method()
    def status(self) -> dict[str, Any]:
        return {
            "ready": True,
            "provider": "kokoro_tts",
            "app_name": APP_NAME,
            "default_voice": DEFAULT_VOICE,
            "default_lang_code": DEFAULT_LANG_CODE,
            "default_sample_rate": DEFAULT_SAMPLE_RATE,
            "default_audio_format": DEFAULT_AUDIO_FORMAT,
            "container_idle_seconds": CONTAINER_IDLE_SECONDS,
        }

    @modal.method()
    def synthesize(
        self,
        *,
        text: str,
        voice: str = DEFAULT_VOICE,
        lang_code: str = DEFAULT_LANG_CODE,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        audio_format: str = DEFAULT_AUDIO_FORMAT,
        normalize_audio: bool = True,
        trim_silence: bool = False,
        sentence_pause_ms: int = 0,
    ) -> dict[str, Any]:
        request_id = uuid.uuid4().hex[:12]
        started_at = time.perf_counter()
        resolved_text = str(text or "").strip()
        if not resolved_text:
            raise ValueError("text is required")

        resolved_voice = str(voice or DEFAULT_VOICE).strip() or DEFAULT_VOICE
        resolved_lang = str(lang_code or DEFAULT_LANG_CODE).strip() or DEFAULT_LANG_CODE
        resolved_sample_rate = max(8_000, int(sample_rate or DEFAULT_SAMPLE_RATE))
        resolved_format = str(audio_format or DEFAULT_AUDIO_FORMAT).strip().lower() or DEFAULT_AUDIO_FORMAT
        _modal_log(
            "tts_request_started",
            request_id=request_id,
            voice=resolved_voice,
            lang_code=resolved_lang,
            text_chars=len(resolved_text),
            sample_rate=resolved_sample_rate,
            audio_format=resolved_format,
            normalize_audio=bool(normalize_audio),
            trim_silence=bool(trim_silence),
            sentence_pause_ms=int(sentence_pause_ms or 0),
        )

        try:
            pipeline = self._pipeline_for(resolved_lang)
            generator = pipeline(resolved_text, voice=resolved_voice)

            chunks: list[np.ndarray] = []
            emitted_chunks = 0
            total_samples = 0
            pause_samples = max(0, int(resolved_sample_rate * max(0, sentence_pause_ms) / 1000))
            for _, _, audio in generator:
                chunk = np.asarray(audio, dtype=np.float32)
                if not chunk.size:
                    continue
                emitted_chunks += 1
                total_samples += int(chunk.size)
                chunks.append(chunk)
                _modal_log(
                    "tts_chunk_produced",
                    request_id=request_id,
                    chunk_index=emitted_chunks,
                    chunk_samples=int(chunk.size),
                    accumulated_samples=total_samples,
                )
                if pause_samples > 0:
                    chunks.append(np.zeros(pause_samples, dtype=np.float32))
                    total_samples += pause_samples
                    _modal_log(
                        "tts_pause_inserted",
                        request_id=request_id,
                        chunk_index=emitted_chunks,
                        pause_samples=pause_samples,
                        accumulated_samples=total_samples,
                    )

            if not chunks:
                raise RuntimeError("Kokoro returned no audio chunks")

            concat_started_at = time.perf_counter()
            _modal_log("tts_concat_started", request_id=request_id, chunk_count=emitted_chunks, total_samples=total_samples)
            full_audio = np.concatenate(chunks)
            _modal_log(
                "tts_concat_completed",
                request_id=request_id,
                chunk_count=emitted_chunks,
                total_samples=int(full_audio.size),
                elapsed_seconds=round(time.perf_counter() - concat_started_at, 3),
            )
            if trim_silence:
                full_audio = _apply_trim(full_audio)
            if normalize_audio:
                full_audio = _apply_normalization(full_audio)

            encode_started_at = time.perf_counter()
            _modal_log("tts_encode_started", request_id=request_id, total_samples=int(full_audio.size), audio_format=resolved_format)
            audio_bytes, media_type = _encode_audio(
                full_audio,
                sample_rate=resolved_sample_rate,
                audio_format=resolved_format,
            )
            encode_elapsed = round(time.perf_counter() - encode_started_at, 3)
            duration_seconds = round(float(len(full_audio)) / float(max(1, resolved_sample_rate)), 3)
            total_elapsed = round(time.perf_counter() - started_at, 3)
            _modal_log(
                "tts_request_completed",
                request_id=request_id,
                chunk_count=emitted_chunks,
                total_samples=int(full_audio.size),
                byte_length=len(audio_bytes),
                duration_seconds=duration_seconds,
                encode_elapsed_seconds=encode_elapsed,
                total_elapsed_seconds=total_elapsed,
            )
            return {
                "audio_bytes": audio_bytes,
                "media_type": media_type,
                "sample_rate": int(resolved_sample_rate),
                "audio_format": resolved_format,
                "voice": resolved_voice,
                "lang_code": resolved_lang,
                "duration_seconds": duration_seconds,
                "byte_length": len(audio_bytes),
                "telemetry": {
                    "request_id": request_id,
                    "chunk_count": emitted_chunks,
                    "total_samples": int(full_audio.size),
                    "encode_elapsed_seconds": encode_elapsed,
                    "total_elapsed_seconds": total_elapsed,
                },
                "controls": {
                    "normalize_audio": bool(normalize_audio),
                    "trim_silence": bool(trim_silence),
                    "sentence_pause_ms": int(sentence_pause_ms or 0),
                },
            }
        except Exception as exc:
            _modal_log(
                "tts_request_failed",
                request_id=request_id,
                error=repr(exc),
                traceback=traceback.format_exc(),
                elapsed_seconds=round(time.perf_counter() - started_at, 3),
            )
            raise

    @modal.fastapi_endpoint(method="POST", docs=True)
    def api(self, request: SynthesizeRequest):
        from fastapi import Response

        payload = self.synthesize.local(**request.model_dump())
        telemetry = payload.get("telemetry") if isinstance(payload.get("telemetry"), dict) else {}
        headers = {
            "X-Kokoro-Voice": str(payload["voice"]),
            "X-Kokoro-Lang-Code": str(payload["lang_code"]),
            "X-Kokoro-Sample-Rate": str(payload["sample_rate"]),
            "X-Kokoro-Audio-Format": str(payload["audio_format"]),
            "X-Kokoro-Duration-Seconds": str(payload["duration_seconds"]),
            "X-Kokoro-Request-Id": str(telemetry.get("request_id") or ""),
            "X-Kokoro-Chunk-Count": str(telemetry.get("chunk_count") or ""),
            "X-Kokoro-Total-Samples": str(telemetry.get("total_samples") or ""),
            "X-Kokoro-Encode-Elapsed-Seconds": str(telemetry.get("encode_elapsed_seconds") or ""),
            "X-Kokoro-Total-Elapsed-Seconds": str(telemetry.get("total_elapsed_seconds") or ""),
        }
        return Response(content=payload["audio_bytes"], media_type=payload["media_type"], headers=headers)

    @modal.fastapi_endpoint(method="GET", docs=True)
    def health(self):
        return self.status.local()


@app.local_entrypoint()
def entrypoint(
    text: str,
    voice: str = DEFAULT_VOICE,
    lang_code: str = DEFAULT_LANG_CODE,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    audio_format: str = DEFAULT_AUDIO_FORMAT,
    normalize_audio: bool = True,
    trim_silence: bool = False,
    sentence_pause_ms: int = 0,
) -> None:
    service = KokoroTTSService()
    payload = service.synthesize.remote(
        text=text,
        voice=voice,
        lang_code=lang_code,
        sample_rate=sample_rate,
        audio_format=audio_format,
        normalize_audio=normalize_audio,
        trim_silence=trim_silence,
        sentence_pause_ms=sentence_pause_ms,
    )
    print(
        {
            "provider": "kokoro_tts",
            "voice": payload["voice"],
            "lang_code": payload["lang_code"],
            "audio_format": payload["audio_format"],
            "sample_rate": payload["sample_rate"],
            "duration_seconds": payload["duration_seconds"],
            "byte_length": len(payload["audio_bytes"]),
        }
    )
