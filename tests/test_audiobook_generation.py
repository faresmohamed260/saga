from __future__ import annotations

import hashlib
import io
import math
import wave
from array import array
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from packages.audiobook_generation import audio
from packages.audiobook_generation.pipeline import AudiobookGenerationRuntime
from packages.audiobook_generation.quality import word_error_rate
from packages.narrative_generation.contracts import ChapterDraftArtifact, GeneratedStoryArtifact
from packages.narrative_generation.store import NarrativeGenerationStore
from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client
from packages.reasoning_runtime import ReasoningProfile, ReasoningRuntimeConfig, create_reasoning_client


class AudibleSpeechProvider:
    def __init__(self, *, corrupt_calls: set[int] | None = None) -> None:
        self.corrupt_calls = set(corrupt_calls or set())
        self.calls: list[dict] = []
        self.transcripts: dict[str, str] = {}

    def synthesize(self, **kwargs):
        self.calls.append(dict(kwargs))
        if len(self.calls) in self.corrupt_calls:
            payload = b"not-a-wav"
        else:
            payload = _audible_wav(str(kwargs["text"]), sample_rate=int(kwargs["sample_rate"]))
            self.transcripts[hashlib.sha256(payload).hexdigest()] = str(kwargs["text"])
        return {"response": {"audio_bytes": payload, "sample_rate": kwargs["sample_rate"]}, "token_name": "test-account"}


class LinkedTranscriptionProvider:
    def __init__(self, speech: AudibleSpeechProvider, *, bad: bool = False, fail: bool = False) -> None:
        self.speech = speech
        self.bad = bad
        self.fail = fail
        self.calls = 0

    def transcribe_audio(self, **kwargs):
        self.calls += 1
        if self.fail:
            raise RuntimeError("temporary transcription outage")
        if self.bad:
            return {"text": "completely unrelated transcription"}
        digest = hashlib.sha256(kwargs["audio_bytes"]).hexdigest()
        return {"text": self.speech.transcripts[digest], "model": "test-transcriber"}

    def last_request_metadata(self):
        return {"provider": "test", "resolved_model": "test-transcriber", "status": "ok"}


def _persistence(tmp_path: Path):
    profile = PersistenceProfile(
        name="audiobook-generation-test",
        provider="supabase",
        mode="test_harness",
        database_url=f"sqlite:///{tmp_path / 'audiobook.sqlite3'}",
        local_storage_root_dir=str(tmp_path / "storage"),
    )
    client = create_persistence_client(profile=profile, config=PersistenceRuntimeConfig(profile=profile))
    client.initialize()
    return client


def _seed(client, *, accepted: bool = True, prose: str | None = None) -> None:
    text = prose or ("Jude crossed the rain-dark courtyard and held the silver key against the locked gate. " * 12)
    NarrativeGenerationStore(client).upsert_story(GeneratedStoryArtifact(
        story_id="story-1",
        series_id="series-1",
        blueprint_id="blueprint-1",
        title="The Silver Threshold",
        premise="A guarded return.",
        chapters=[ChapterDraftArtifact(
            chapter_draft_id="chapter-1",
            series_id="series-1",
            story_id="story-1",
            blueprint_id="blueprint-1",
            chapter_index=1,
            title="The Gate",
            prose=text,
            scene_prose_ids=["scene-prose-1"],
        )],
        metadata={"semantic_support": {"accepted": accepted, "status": "accepted" if accepted else "rejected"}},
    ))


def _runtime(client, speech: AudibleSpeechProvider, transcription: LinkedTranscriptionProvider):
    return AudiobookGenerationRuntime(
        persistence=client,
        synthesis_provider=speech,
        transcription_provider=transcription,
        allow_in_memory_checkpointer=True,
    )


def _audible_wav(text: str, *, sample_rate: int = 24000) -> bytes:
    duration = max(0.5, len(text.split()) / 150 * 60)
    frequency = 180 + int(hashlib.sha256(text.encode()).hexdigest()[:4], 16) % 180
    samples = array("h", (int(7500 * math.sin(2 * math.pi * frequency * i / sample_rate)) for i in range(int(sample_rate * duration))))
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(samples.tobytes())
    return output.getvalue()


def test_end_to_end_generates_audited_chapter_and_manifest(tmp_path: Path):
    client = _persistence(tmp_path)
    _seed(client)
    speech = AudibleSpeechProvider()
    result = _runtime(client, speech, LinkedTranscriptionProvider(speech)).invoke(
        series_id="series-1", story_id="story-1", run_id="run-1", thread_id="thread-1", max_segment_chars=400,
    )

    assert result.decision.accepted is True
    assert result.manifest is not None
    assert len(result.segments) > 1
    assert len(result.audits) == len(result.segments)
    assert all(item.accepted and item.word_error_rate == 0 for item in result.audits)
    book_audio = client.objects.download_bytes(result.manifest.bucket_name, result.manifest.object_path)
    assert audio.inspect_wav(book_audio, expected_sample_rate=24000)["passed"] is True


def test_technical_failure_retries_only_failed_segment(tmp_path: Path):
    client = _persistence(tmp_path)
    _seed(client, prose="Jude raised the silver key before the gate opened.")
    speech = AudibleSpeechProvider(corrupt_calls={1})
    result = _runtime(client, speech, LinkedTranscriptionProvider(speech)).invoke(
        series_id="series-1", story_id="story-1", run_id="run-retry", thread_id="thread-retry", max_attempts=2,
    )

    assert result.decision.accepted is True
    assert len(speech.calls) == 2
    assert [item.status for item in result.syntheses] == ["technical_rejection", "synthesized"]


def test_resume_reuses_accepted_audio_and_retries_only_rejected(tmp_path: Path):
    client = _persistence(tmp_path)
    _seed(client, prose="Jude raised the silver key before the gate opened.")
    speech = AudibleSpeechProvider()
    transcription = LinkedTranscriptionProvider(speech, bad=True)
    runtime = _runtime(client, speech, transcription)
    first = runtime.invoke(
        series_id="series-1", story_id="story-1", run_id="run-resume", thread_id="thread-resume", max_attempts=1,
    )
    assert first.decision.accepted is False
    transcription.bad = False
    resumed = runtime.retry_rejected(series_id="series-1", story_id="story-1", run_id="run-resume", max_attempts=2)

    assert resumed.decision.accepted is True
    assert len(speech.calls) == 2
    assert len(resumed.syntheses) == 2


def test_resume_reaudits_transcription_outage_without_resynthesis(tmp_path: Path):
    client = _persistence(tmp_path)
    _seed(client, prose="Jude raised the silver key before the gate opened.")
    speech = AudibleSpeechProvider()
    transcription = LinkedTranscriptionProvider(speech, fail=True)
    runtime = _runtime(client, speech, transcription)
    first = runtime.invoke(
        series_id="series-1", story_id="story-1", run_id="run-reaudit", thread_id="thread-reaudit", max_attempts=1,
    )
    assert first.decision.accepted is False
    transcription.fail = False
    resumed = runtime.retry_rejected(series_id="series-1", story_id="story-1", run_id="run-reaudit", max_attempts=2)

    assert resumed.decision.accepted is True
    assert len(speech.calls) == 1
    assert len(resumed.syntheses) == 1


def test_transcription_mismatch_fails_closed_after_bound(tmp_path: Path):
    client = _persistence(tmp_path)
    _seed(client, prose="Jude raised the silver key before the gate opened.")
    speech = AudibleSpeechProvider()
    result = _runtime(client, speech, LinkedTranscriptionProvider(speech, bad=True)).invoke(
        series_id="series-1", story_id="story-1", run_id="run-bad", thread_id="thread-bad", max_attempts=2,
    )

    assert result.decision.accepted is False
    assert result.manifest is None
    assert len(speech.calls) == 2
    assert result.audits[-1].status == "rejected"


def test_unaccepted_narrative_is_rejected_before_provider_call(tmp_path: Path):
    client = _persistence(tmp_path)
    _seed(client, accepted=False)
    speech = AudibleSpeechProvider()
    with pytest.raises(ValueError, match="has not passed narrative semantic support"):
        _runtime(client, speech, LinkedTranscriptionProvider(speech)).invoke(
            series_id="series-1", story_id="story-1", run_id="run-gated", thread_id="thread-gated",
        )
    assert speech.calls == []


def test_word_error_rate_uses_word_level_edit_distance():
    assert word_error_rate("one two three", "one two three") == 0
    assert word_error_rate("one two three", "one four three") == pytest.approx(1 / 3, abs=0.0001)


def test_mistral_transcription_uses_sdk_multipart_aliases():
    client = create_reasoning_client(
        profile_name="transcription",
        config=ReasoningRuntimeConfig(profiles={"transcription": ReasoningProfile(
            name="transcription", mode="mistral", model_override="voxtral-mini-latest",
        )}),
    )
    complete = Mock(return_value=SimpleNamespace(text="spoken words", language="en", model="voxtral-mini-latest"))
    client._mistral_client = SimpleNamespace(audio=SimpleNamespace(transcriptions=SimpleNamespace(complete=complete)))

    result = client.transcribe_audio(audio_bytes=b"wav-data", filename="sample.wav", context_bias=["Jude"])

    assert result["text"] == "spoken words"
    request = complete.call_args.kwargs
    assert request["file"] == {"fileName": "sample.wav", "content": b"wav-data", "Content-Type": "audio/wav"}
