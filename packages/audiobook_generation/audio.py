"""Dependency-free PCM WAV inspection and assembly helpers."""

from __future__ import annotations

import io
import wave
from array import array
from typing import Any


def inspect_wav(audio_bytes: bytes, *, expected_sample_rate: int, expected_words: int = 0) -> dict[str, Any]:
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wav:
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            sample_rate = wav.getframerate()
            frame_count = wav.getnframes()
            frames = wav.readframes(frame_count)
    except Exception as exc:
        return {"passed": False, "issues": [f"corrupt_wav:{type(exc).__name__}"], "byte_length": len(audio_bytes)}
    duration = frame_count / max(1, sample_rate)
    issues: list[str] = []
    if channels != 1:
        issues.append(f"unexpected_channels:{channels}")
    if sample_width != 2:
        issues.append(f"unexpected_sample_width:{sample_width}")
    if sample_rate != expected_sample_rate:
        issues.append(f"unexpected_sample_rate:{sample_rate}")
    if duration <= 0.2:
        issues.append("audio_too_short")
    if len(audio_bytes) < 4096:
        issues.append("audio_payload_too_small")
    samples = array("h")
    samples.frombytes(frames)
    if samples:
        peak = max(abs(value) for value in samples)
        mean_square = sum(value * value for value in samples) / len(samples)
        rms = mean_square ** 0.5
        silence_ratio = sum(1 for value in samples if abs(value) <= 96) / len(samples)
        clipping_ratio = sum(1 for value in samples if abs(value) >= 32700) / len(samples)
    else:
        peak = 0
        rms = 0.0
        silence_ratio = 1.0
        clipping_ratio = 0.0
    speaking_rate = expected_words / max(duration / 60.0, 1e-6) if expected_words else 0.0
    if rms < 80:
        issues.append("silent_or_near_silent_audio")
    if silence_ratio >= 0.92:
        issues.append("excessive_silence")
    if clipping_ratio > 0.02:
        issues.append("excessive_clipping")
    if expected_words and not 75 <= speaking_rate <= 260:
        issues.append(f"implausible_speaking_rate:{speaking_rate:.1f}")
    return {
        "passed": not issues,
        "issues": issues,
        "byte_length": len(audio_bytes),
        "channels": channels,
        "sample_width": sample_width,
        "sample_rate": sample_rate,
        "frame_count": frame_count,
        "duration_seconds": round(duration, 4),
        "peak_amplitude": peak,
        "rms_amplitude": round(rms, 4),
        "silence_ratio": round(silence_ratio, 6),
        "clipping_ratio": round(clipping_ratio, 6),
        "speaking_rate_wpm": round(speaking_rate, 3),
    }


def assemble_wav(parts: list[bytes], *, pause_ms: int = 0) -> tuple[bytes, dict[str, Any]]:
    if not parts:
        raise ValueError("At least one WAV part is required.")
    params: tuple[int, int, int] | None = None
    frames: list[bytes] = []
    for part in parts:
        with wave.open(io.BytesIO(part), "rb") as wav:
            current = (wav.getnchannels(), wav.getsampwidth(), wav.getframerate())
            if params is None:
                params = current
            elif current != params:
                raise ValueError(f"WAV format mismatch: expected {params}, got {current}.")
            frames.append(wav.readframes(wav.getnframes()))
    assert params is not None
    channels, sample_width, sample_rate = params
    silence_frames = max(0, int(sample_rate * max(0, pause_ms) / 1000))
    silence = b"\x00" * silence_frames * channels * sample_width
    combined = silence.join(frames)
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(sample_width)
        wav.setframerate(sample_rate)
        wav.writeframes(combined)
    duration = len(combined) / max(1, channels * sample_width * sample_rate)
    return output.getvalue(), {
        "channels": channels,
        "sample_width": sample_width,
        "sample_rate": sample_rate,
        "duration_seconds": round(duration, 4),
        "part_count": len(parts),
        "pause_ms": max(0, pause_ms),
    }
