from __future__ import annotations

import io
import re
import wave
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import perf_counter
from typing import Any

from integrations.kokoro_tts.pool_manager import ModalTTSPoolManager
from packages.reasoning_runtime.contracts import ReasoningClient
from saga.providers.reasoning_runtime_adapter import MODE_GPT_OSS, create_runtime_client


TONE_INSTRUCTIONS = {
    "classic": "Use polished, natural audiobook narration with clear transitions and restrained dramatic emphasis.",
    "dramatic": "Use heightened dramatic cadence, sharper contrast in sentence rhythm, and stronger emotional emphasis while staying faithful to the chapter.",
    "epic": "Use sweeping, cinematic narration with elevated phrasing and a grand sense of momentum while preserving the chapter's events and dialogue.",
}


class AudiobookGenerationService:
    def __init__(
        self,
        *,
        llm_client: ReasoningClient | None = None,
        tts_pool: ModalTTSPoolManager | None = None,
    ) -> None:
        self.llm_client = llm_client or create_runtime_client(mode=MODE_GPT_OSS, allow_cross_provider_fallback=False)
        self.tts_pool = tts_pool or ModalTTSPoolManager()

    def rewrite_chapter_text(
        self,
        *,
        chapter_title: str,
        chapter_text: str,
        tone: str,
        fallback_mode: str = "strict_rewrite",
    ) -> dict[str, Any]:
        source_text = str(chapter_text or "").strip()
        if not source_text:
            return {
                "transcript_text": "",
                "source_provider": self.llm_client.provider_name(),
                "source_model": self.llm_client.resolved_model_name(),
                "metadata": {"rewrite_mode": "empty_source"},
            }

        # Keep very large chapters moving through the pipeline; they can still be synthesized from source text.
        if len(source_text) > 24000:
            return {
                "transcript_text": source_text,
                "source_provider": self.llm_client.provider_name(),
                "source_model": self.llm_client.resolved_model_name(),
                "metadata": {"rewrite_mode": "source_passthrough_large_chapter"},
            }

        tone_key = str(tone or "classic").strip().lower()
        tone_instruction = TONE_INSTRUCTIONS.get(tone_key, TONE_INSTRUCTIONS["classic"])
        system_prompt = (
            "You are an audiobook narration editor. "
            "Rewrite source chapter text into clean listenable narration. "
            "Preserve canon facts, sequence, names, and dialogue meaning. "
            "Do not add commentary, labels, bullets, markdown, or summaries. "
            "Return only the final narration prose."
        )
        prompt = (
            f"Chapter title: {chapter_title or 'Untitled chapter'}\n"
            f"Tone target: {tone_key}\n"
            f"Style instruction: {tone_instruction}\n\n"
            "Rewrite the chapter so it reads smoothly when spoken aloud. "
            "Keep quoted dialogue intact where present, smooth awkward formatting, and remove artifacts that sound unnatural in TTS.\n\n"
            "Source chapter text:\n"
            f"{source_text}"
        )
        transcript_text = self.llm_client.generate_text(
            prompt,
            system_prompt=system_prompt,
            temperature=0.4,
            max_tokens=4096,
        ).strip()
        rewrite_mode = "llm_rewrite"
        if not transcript_text:
            if str(fallback_mode or "").strip().lower() == "fallback_to_source":
                transcript_text = source_text
                rewrite_mode = "source_passthrough_empty_generation"
            else:
                raise RuntimeError("Audiobook rewrite returned empty text.")
        return {
            "transcript_text": transcript_text,
            "source_provider": self.llm_client.provider_name(),
            "source_model": self.llm_client.resolved_model_name(),
            "metadata": {"rewrite_mode": rewrite_mode, "tone": tone_key, "fallback_mode": str(fallback_mode or "strict_rewrite").strip().lower()},
        }

    def synthesize_audio(
        self,
        *,
        transcript_text: str,
        voice: str,
        lang_code: str,
        sample_rate: int,
        audio_format: str,
        normalize_audio: bool,
        trim_silence: bool,
        sentence_pause_ms: int,
        progress_logger: Any | None = None,
    ) -> dict[str, Any]:
        resolved_text = str(transcript_text or "").strip()
        resolved_format = str(audio_format or "wav").strip().lower() or "wav"
        if not resolved_text:
            raise ValueError("transcript_text is required")

        chunks = self._chunk_transcript_text(resolved_text)
        if callable(progress_logger):
            progress_logger(
                "tts_chunk_plan",
                chunk_count=len(chunks),
                transcript_chars=len(resolved_text),
                audio_format=resolved_format,
                sample_rate=sample_rate,
            )
        if len(chunks) <= 1 or resolved_format != "wav":
            started_at = perf_counter()
            payload = self.tts_pool.synthesize(
                text=resolved_text,
                voice=voice,
                lang_code=lang_code,
                sample_rate=sample_rate,
                audio_format=resolved_format,
                normalize_audio=normalize_audio,
                trim_silence=trim_silence,
                sentence_pause_ms=sentence_pause_ms,
            )
            if callable(progress_logger):
                telemetry = payload.get("telemetry") if isinstance(payload.get("telemetry"), dict) else {}
                progress_logger(
                    "tts_single_render_completed",
                    elapsed_seconds=round(perf_counter() - started_at, 2),
                    byte_length=len(payload.get("audio_bytes") or b""),
                    duration_seconds=payload.get("duration_seconds"),
                    telemetry=telemetry,
                )
            return payload

        rendered_chunks: list[dict[str, Any]] = []
        if hasattr(self.tts_pool, "get_live_endpoints") and hasattr(self.tts_pool, "synthesize_via_endpoint"):
            try:
                endpoints = list(self.tts_pool.get_live_endpoints(max_endpoints=min(len(chunks), 4)))
            except Exception:
                endpoints = []
            if len(endpoints) > 1:
                if callable(progress_logger):
                    progress_logger(
                        "tts_parallel_pool_ready",
                        chunk_count=len(chunks),
                        endpoint_count=len(endpoints),
                        endpoints=[str(item.get("token_name") or "") for item in endpoints],
                    )
                rendered_chunks = [None] * len(chunks)  # type: ignore[list-item]
                with ThreadPoolExecutor(max_workers=min(len(endpoints), len(chunks))) as executor:
                    future_map: dict[Any, tuple[int, str, float, dict[str, Any]]] = {}
                    for chunk_index, chunk_text in enumerate(chunks, start=1):
                        endpoint = dict(endpoints[(chunk_index - 1) % len(endpoints)])
                        if callable(progress_logger):
                            progress_logger(
                                "tts_chunk_render_started",
                                chunk_index=chunk_index,
                                chunk_count=len(chunks),
                                chunk_chars=len(chunk_text),
                                token_name=str(endpoint.get("token_name") or ""),
                            )
                        future = executor.submit(
                            self.tts_pool.synthesize_via_endpoint,
                            endpoint,
                            text=chunk_text,
                            voice=voice,
                            lang_code=lang_code,
                            sample_rate=sample_rate,
                            audio_format=resolved_format,
                            normalize_audio=normalize_audio,
                            trim_silence=trim_silence,
                            sentence_pause_ms=sentence_pause_ms,
                        )
                        future_map[future] = (chunk_index, chunk_text, perf_counter(), endpoint)
                    for future in as_completed(future_map):
                        chunk_index, chunk_text, started_at, endpoint = future_map[future]
                        payload = future.result()
                        rendered_chunks[chunk_index - 1] = payload
                        if callable(progress_logger):
                            telemetry = payload.get("telemetry") if isinstance(payload.get("telemetry"), dict) else {}
                            progress_logger(
                                "tts_chunk_render_completed",
                                chunk_index=chunk_index,
                                chunk_count=len(chunks),
                                chunk_chars=len(chunk_text),
                                elapsed_seconds=round(perf_counter() - started_at, 2),
                                byte_length=len(payload.get("audio_bytes") or b""),
                                duration_seconds=payload.get("duration_seconds"),
                                token_name=str(payload.get("token_name") or endpoint.get("token_name") or ""),
                                telemetry=telemetry,
                            )
                if callable(progress_logger):
                    progress_logger("tts_merge_started", chunk_count=len(rendered_chunks))
                merged = self._merge_wav_payloads(rendered_chunks, fallback_voice=voice, fallback_lang_code=lang_code, fallback_sample_rate=sample_rate)
                if callable(progress_logger):
                    telemetry = merged.get("telemetry") if isinstance(merged.get("telemetry"), dict) else {}
                    progress_logger(
                        "tts_merge_completed",
                        chunk_count=len(rendered_chunks),
                        byte_length=len(merged.get("audio_bytes") or b""),
                        duration_seconds=merged.get("duration_seconds"),
                        telemetry=telemetry,
                    )
                return merged

        for chunk_index, chunk_text in enumerate(chunks, start=1):
            if callable(progress_logger):
                progress_logger(
                    "tts_chunk_render_started",
                    chunk_index=chunk_index,
                    chunk_count=len(chunks),
                    chunk_chars=len(chunk_text),
                )
            started_at = perf_counter()
            payload = self.tts_pool.synthesize(
                text=chunk_text,
                voice=voice,
                lang_code=lang_code,
                sample_rate=sample_rate,
                audio_format=resolved_format,
                normalize_audio=normalize_audio,
                trim_silence=trim_silence,
                sentence_pause_ms=sentence_pause_ms,
            )
            rendered_chunks.append(payload)
            if callable(progress_logger):
                telemetry = payload.get("telemetry") if isinstance(payload.get("telemetry"), dict) else {}
                progress_logger(
                    "tts_chunk_render_completed",
                    chunk_index=chunk_index,
                    chunk_count=len(chunks),
                    chunk_chars=len(chunk_text),
                    elapsed_seconds=round(perf_counter() - started_at, 2),
                    byte_length=len(payload.get("audio_bytes") or b""),
                    duration_seconds=payload.get("duration_seconds"),
                    telemetry=telemetry,
                )
        if callable(progress_logger):
            progress_logger("tts_merge_started", chunk_count=len(rendered_chunks))
        merged = self._merge_wav_payloads(rendered_chunks, fallback_voice=voice, fallback_lang_code=lang_code, fallback_sample_rate=sample_rate)
        if callable(progress_logger):
            telemetry = merged.get("telemetry") if isinstance(merged.get("telemetry"), dict) else {}
            progress_logger(
                "tts_merge_completed",
                chunk_count=len(rendered_chunks),
                byte_length=len(merged.get("audio_bytes") or b""),
                duration_seconds=merged.get("duration_seconds"),
                telemetry=telemetry,
            )
        return merged

    def _chunk_transcript_text(self, transcript_text: str, *, max_chars: int = 2500) -> list[str]:
        normalized = re.sub(r"\n{3,}", "\n\n", str(transcript_text or "").strip())
        if not normalized:
            return []
        if len(normalized) <= max_chars:
            return [normalized]

        chunks: list[str] = []
        current = ""
        paragraphs = [part.strip() for part in normalized.split("\n\n") if part.strip()]
        for paragraph in paragraphs:
            if len(paragraph) > max_chars:
                for sentence in self._split_long_paragraph(paragraph, max_chars=max_chars):
                    if current and len(current) + 2 + len(sentence) > max_chars:
                        chunks.append(current.strip())
                        current = sentence
                    else:
                        current = f"{current}\n\n{sentence}".strip() if current else sentence
                continue
            if current and len(current) + 2 + len(paragraph) > max_chars:
                chunks.append(current.strip())
                current = paragraph
            else:
                current = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if current.strip():
            chunks.append(current.strip())
        return chunks

    def _split_long_paragraph(self, paragraph: str, *, max_chars: int) -> list[str]:
        sentence_parts = re.split(r"(?<=[.!?])\s+", paragraph.strip())
        chunks: list[str] = []
        current = ""
        for sentence in [part.strip() for part in sentence_parts if part.strip()]:
            if len(sentence) > max_chars:
                for start in range(0, len(sentence), max_chars):
                    piece = sentence[start : start + max_chars].strip()
                    if piece:
                        if current:
                            chunks.append(current.strip())
                            current = ""
                        chunks.append(piece)
                continue
            if current and len(current) + 1 + len(sentence) > max_chars:
                chunks.append(current.strip())
                current = sentence
            else:
                current = f"{current} {sentence}".strip() if current else sentence
        if current.strip():
            chunks.append(current.strip())
        return chunks

    def _merge_wav_payloads(
        self,
        payloads: list[dict[str, Any]],
        *,
        fallback_voice: str,
        fallback_lang_code: str,
        fallback_sample_rate: int,
    ) -> dict[str, Any]:
        if not payloads:
            raise RuntimeError("No TTS payloads were rendered.")

        params = None
        frame_chunks: list[bytes] = []
        media_type = "audio/wav"
        duration_seconds = 0.0
        token_name = ""
        api_url = ""
        source_telemetry: list[dict[str, Any]] = []
        for payload in payloads:
            wav_bytes = payload.get("audio_bytes") or b""
            with wave.open(io.BytesIO(wav_bytes), "rb") as reader:
                current_params = (
                    reader.getnchannels(),
                    reader.getsampwidth(),
                    reader.getframerate(),
                    reader.getcomptype(),
                    reader.getcompname(),
                )
                if params is None:
                    params = current_params
                elif current_params != params:
                    raise RuntimeError("Incompatible WAV chunks returned from TTS provider.")
                frame_chunks.append(reader.readframes(reader.getnframes()))
            media_type = str(payload.get("media_type") or media_type)
            duration_seconds += float(payload.get("duration_seconds") or 0.0)
            token_name = str(payload.get("token_name") or token_name)
            api_url = str(payload.get("api_url") or api_url)
            telemetry = payload.get("telemetry")
            if isinstance(telemetry, dict):
                source_telemetry.append(telemetry)

        if params is None:
            raise RuntimeError("Unable to read WAV parameters from TTS payloads.")

        target = io.BytesIO()
        with wave.open(target, "wb") as writer:
            writer.setnchannels(params[0])
            writer.setsampwidth(params[1])
            writer.setframerate(params[2])
            writer.setcomptype(params[3], params[4])
            for frame_chunk in frame_chunks:
                writer.writeframes(frame_chunk)

        return {
            "audio_bytes": target.getvalue(),
            "media_type": media_type,
            "voice": str(payloads[-1].get("voice") or fallback_voice),
            "lang_code": str(payloads[-1].get("lang_code") or fallback_lang_code),
            "sample_rate": int(payloads[-1].get("sample_rate") or fallback_sample_rate),
            "audio_format": "wav",
            "duration_seconds": round(duration_seconds, 3),
            "token_name": token_name,
            "api_url": api_url,
            "telemetry": {
                "merged_chunk_count": len(payloads),
                "source_chunks": source_telemetry,
            },
        }
