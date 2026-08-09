"""LangGraph-native audiobook planning, synthesis, QA, retry, and assembly."""

from __future__ import annotations

import hashlib
import re
import time
from typing import Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from packages.agent_runtime import SqlCheckpointSaver
from packages.audiobook_generation.audio import assemble_wav, inspect_wav
from packages.audiobook_generation.contracts import (
    AudioQualityDecisionArtifact,
    AudioSynthesisArtifact,
    AudiobookChapterArtifact,
    AudiobookDecisionArtifact,
    AudiobookGenerationResult,
    AudiobookManifestArtifact,
    AudiobookPlanArtifact,
    NarrationSegmentArtifact,
    SpeechSynthesisProvider,
    SpeechTranscriptionProvider,
)
from packages.audiobook_generation.quality import word_error_rate
from packages.audiobook_generation.store import AudiobookGenerationStore
from packages.narrative_generation.contracts import GeneratedStoryArtifact
from packages.persistence_runtime import PersistenceRuntimeClient


ALLOWED_KOKORO_VOICES = {
    "af_bella", "af_heart", "af_nicole", "af_sarah", "af_sky",
    "am_adam", "am_eric", "am_liam", "am_michael", "am_onyx",
    "bf_alice", "bf_emma", "bf_isabella", "bf_lily",
    "bm_daniel", "bm_fable", "bm_george", "bm_lewis",
}


class AudiobookGenerationState(TypedDict, total=False):
    series_id: str
    story_id: str
    run_id: str
    context: dict[str, Any]
    narrator_voice: str
    max_chapters: int
    max_segment_chars: int
    max_attempts: int
    plan: dict[str, Any]
    segments: list[dict[str, Any]]
    syntheses: list[dict[str, Any]]
    audits: list[dict[str, Any]]
    chapters: list[dict[str, Any]]
    manifest: dict[str, Any] | None
    decision: dict[str, Any]
    run_metadata: dict[str, Any]


class AudiobookPlanningAgent:
    def __init__(self, *, store: AudiobookGenerationStore) -> None:
        self.store = store

    def run(self, state: AudiobookGenerationState) -> dict[str, Any]:
        started = time.perf_counter()
        story = GeneratedStoryArtifact.model_validate(state["context"]["story"])
        max_chapters = max(0, int(state.get("max_chapters") or 0))
        selected = story.chapters[:max_chapters] if max_chapters else story.chapters
        if not selected:
            raise ValueError(f"Story '{story.story_id}' has no chapters available for audiobook generation.")
        voice = str(state.get("narrator_voice") or "af_bella").strip()
        if voice not in ALLOWED_KOKORO_VOICES:
            raise ValueError(f"Unsupported Kokoro narrator voice '{voice}'.")
        plan = self.store.upsert_plan(AudiobookPlanArtifact(
            run_id=state["run_id"],
            series_id=state["series_id"],
            story_id=state["story_id"],
            title=story.title,
            narrator_voice=voice,
            max_segment_chars=max(400, int(state.get("max_segment_chars") or 1800)),
            selected_chapter_indices=[item.chapter_index for item in selected],
            metadata={"agent": "AudiobookPlanningAgent", "semantic_story_accepted": True},
        ))
        return {
            "plan": plan.model_dump(),
            "run_metadata": _stage_metadata(state, "audiobook_planning", started, chapter_count=len(selected), voice=voice),
        }


class NarrationPreparationAgent:
    def __init__(self, *, store: AudiobookGenerationStore) -> None:
        self.store = store

    def run(self, state: AudiobookGenerationState) -> dict[str, Any]:
        started = time.perf_counter()
        story = GeneratedStoryArtifact.model_validate(state["context"]["story"])
        plan = AudiobookPlanArtifact.model_validate(state["plan"])
        selected = {int(value) for value in plan.selected_chapter_indices}
        segments: list[NarrationSegmentArtifact] = []
        for chapter in story.chapters:
            if chapter.chapter_index not in selected:
                continue
            narration = f"Chapter {chapter.chapter_index}. {chapter.title}.\n\n{chapter.prose}".strip()
            chunks = _chunk_narration(narration, max_chars=plan.max_segment_chars)
            for segment_index, text in enumerate(chunks, start=1):
                segments.append(NarrationSegmentArtifact(
                    segment_id=_stable_id("narration-segment", plan.run_id, chapter.chapter_index, segment_index, text),
                    run_id=plan.run_id,
                    series_id=plan.series_id,
                    story_id=plan.story_id,
                    chapter_index=chapter.chapter_index,
                    segment_index=segment_index,
                    source_scene_ids=list(chapter.scene_prose_ids),
                    voice=plan.narrator_voice,
                    text=text,
                    word_count=len(text.split()),
                    metadata={"agent": "NarrationPreparationAgent", "chapter_title": chapter.title},
                ))
        if not segments:
            raise ValueError("Narration preparation produced no synthesis segments.")
        persisted = self.store.replace_segments(
            series_id=plan.series_id, story_id=plan.story_id, run_id=plan.run_id, items=segments,
        )
        return {
            "segments": [item.model_dump() for item in persisted],
            "run_metadata": _stage_metadata(state, "narration_preparation", started, segment_count=len(persisted), word_count=sum(item.word_count for item in persisted)),
        }


class VoiceSynthesisAgent:
    def __init__(self, *, store: AudiobookGenerationStore, synthesis_provider: SpeechSynthesisProvider) -> None:
        self.store = store
        self.synthesis_provider = synthesis_provider

    def run(self, state: AudiobookGenerationState) -> dict[str, Any]:
        started = time.perf_counter()
        plan = AudiobookPlanArtifact.model_validate(state["plan"])
        segments = [NarrationSegmentArtifact.model_validate(item) for item in state.get("segments") or []]
        syntheses = [AudioSynthesisArtifact.model_validate(item) for item in state.get("syntheses") or []]
        audits = [AudioQualityDecisionArtifact.model_validate(item) for item in state.get("audits") or []]
        accepted = {item.segment_id for item in audits if item.accepted}
        max_attempts = max(1, int(state.get("max_attempts") or 2))
        rendered_now = 0
        for segment in segments:
            attempts = len([item for item in syntheses if item.segment_id == segment.segment_id])
            if segment.segment_id in accepted or attempts >= max_attempts:
                continue
            attempt = attempts + 1
            synthesis_id = _stable_id("audio-synthesis", segment.segment_id, attempt)
            call_started = time.perf_counter()
            try:
                raw = self.synthesis_provider.synthesize(
                    text=segment.text,
                    voice=segment.voice,
                    lang_code=plan.lang_code,
                    sample_rate=plan.sample_rate,
                    audio_format="wav",
                    normalize_audio=True,
                    trim_silence=False,
                    sentence_pause_ms=plan.sentence_pause_ms,
                )
                response = dict(raw.get("response") or raw)
                audio_bytes = bytes(response.get("audio_bytes") or b"")
                technical = inspect_wav(audio_bytes, expected_sample_rate=plan.sample_rate, expected_words=segment.word_count)
                synthesis = AudioSynthesisArtifact(
                    synthesis_id=synthesis_id,
                    run_id=plan.run_id,
                    series_id=plan.series_id,
                    story_id=plan.story_id,
                    segment_id=segment.segment_id,
                    chapter_index=segment.chapter_index,
                    segment_index=segment.segment_index,
                    attempt=attempt,
                    status="synthesized" if technical.get("passed") else "technical_rejection",
                    voice=segment.voice,
                    sample_rate=int(response.get("sample_rate") or plan.sample_rate),
                    duration_seconds=float(technical.get("duration_seconds") or response.get("duration_seconds") or 0.0),
                    byte_length=len(audio_bytes),
                    audio_sha256=hashlib.sha256(audio_bytes).hexdigest() if audio_bytes else "",
                    provider_account=str(raw.get("token_name") or response.get("token_name") or ""),
                    elapsed_seconds=round(time.perf_counter() - call_started, 4),
                    technical_metrics=technical,
                    telemetry=dict(response.get("telemetry") or {}),
                    metadata={"agent": "VoiceSynthesisAgent"},
                )
                if technical.get("passed"):
                    stored = self.store.store_segment_audio(synthesis=synthesis, audio_bytes=audio_bytes)
                    synthesis.bucket_name = str(stored.get("bucket_name") or "")
                    synthesis.object_path = str(stored.get("object_path") or "")
            except Exception as exc:
                synthesis = AudioSynthesisArtifact(
                    synthesis_id=synthesis_id,
                    run_id=plan.run_id,
                    series_id=plan.series_id,
                    story_id=plan.story_id,
                    segment_id=segment.segment_id,
                    chapter_index=segment.chapter_index,
                    segment_index=segment.segment_index,
                    attempt=attempt,
                    status="provider_error",
                    voice=segment.voice,
                    elapsed_seconds=round(time.perf_counter() - call_started, 4),
                    error=f"{type(exc).__name__}: {exc}",
                    metadata={"agent": "VoiceSynthesisAgent"},
                )
            syntheses.append(synthesis)
            rendered_now += 1
        persisted = self.store.replace_syntheses(
            series_id=plan.series_id, story_id=plan.story_id, run_id=plan.run_id, items=syntheses,
        )
        round_number = max([item.attempt for item in syntheses] or [1])
        return {
            "syntheses": [item.model_dump() for item in persisted],
            "run_metadata": _stage_metadata(state, f"synthesis_round_{round_number}", started, synthesized_count=rendered_now),
        }


class AudioQAAgent:
    def __init__(self, *, store: AudiobookGenerationStore, transcription_provider: SpeechTranscriptionProvider) -> None:
        self.store = store
        self.transcription_provider = transcription_provider

    def run(self, state: AudiobookGenerationState) -> dict[str, Any]:
        started = time.perf_counter()
        plan = AudiobookPlanArtifact.model_validate(state["plan"])
        segments = {item.segment_id: item for item in [NarrationSegmentArtifact.model_validate(row) for row in state.get("segments") or []]}
        syntheses = [AudioSynthesisArtifact.model_validate(row) for row in state.get("syntheses") or []]
        audits = [AudioQualityDecisionArtifact.model_validate(row) for row in state.get("audits") or []]
        audited = {item.synthesis_id for item in audits}
        max_attempts = max(1, int(state.get("max_attempts") or 2))
        for synthesis in syntheses:
            if synthesis.synthesis_id in audited:
                continue
            segment = segments[synthesis.segment_id]
            technical_passed = synthesis.status == "synthesized" and bool(synthesis.technical_metrics.get("passed"))
            issues = list(synthesis.technical_metrics.get("issues") or [])
            transcript = ""
            wer = 1.0
            transcription_metadata: dict[str, Any] = {}
            if technical_passed:
                try:
                    result = self.transcription_provider.transcribe_audio(
                        audio_bytes=self.store.load_audio(synthesis),
                        filename=f"{synthesis.synthesis_id}.wav",
                        language=plan.language,
                        context_bias=_context_bias(segment.text),
                    )
                    transcript = str(result.get("text") or "").strip()
                    wer = word_error_rate(segment.text, transcript)
                    if not transcript:
                        issues.append("empty_transcription")
                    transcription_metadata = dict(getattr(self.transcription_provider, "last_request_metadata", lambda: {})() or {})
                except Exception as exc:
                    issues.append(f"transcription_error:{type(exc).__name__}")
            else:
                issues.append(synthesis.error or synthesis.status)
            accepted = technical_passed and transcript != "" and wer <= 0.25 and not any(item.startswith("transcription_error") for item in issues)
            if wer > 0.25 and transcript:
                issues.append(f"word_error_rate_exceeded:{wer:.4f}")
            status = "accepted" if accepted else ("retry_required" if synthesis.attempt < max_attempts else "rejected")
            audits.append(AudioQualityDecisionArtifact(
                audit_id=_stable_id("audio-quality-audit", synthesis.synthesis_id),
                run_id=plan.run_id,
                series_id=plan.series_id,
                story_id=plan.story_id,
                segment_id=segment.segment_id,
                synthesis_id=synthesis.synthesis_id,
                attempt=synthesis.attempt,
                accepted=accepted,
                status=status,
                technical_passed=technical_passed,
                transcription_text=transcript,
                word_error_rate=wer,
                word_match_rate=round(max(0.0, 1.0 - wer), 4),
                speaking_rate_wpm=float(synthesis.technical_metrics.get("speaking_rate_wpm") or 0.0),
                issues=_dedupe(issues),
                metadata={"agent": "AudioQAAgent", "transcription": transcription_metadata},
            ))
        persisted = self.store.replace_audits(
            series_id=plan.series_id, story_id=plan.story_id, run_id=plan.run_id, items=audits,
        )
        round_number = max([item.attempt for item in syntheses] or [1])
        return {
            "audits": [item.model_dump() for item in persisted],
            "run_metadata": _stage_metadata(state, f"audio_audit_round_{round_number}", started, audit_count=len(persisted)),
        }


class AudioAssemblyAgent:
    def __init__(self, *, store: AudiobookGenerationStore) -> None:
        self.store = store

    def run(self, state: AudiobookGenerationState) -> dict[str, Any]:
        started = time.perf_counter()
        plan = AudiobookPlanArtifact.model_validate(state["plan"])
        segments = [NarrationSegmentArtifact.model_validate(row) for row in state.get("segments") or []]
        syntheses = [AudioSynthesisArtifact.model_validate(row) for row in state.get("syntheses") or []]
        audits = [AudioQualityDecisionArtifact.model_validate(row) for row in state.get("audits") or []]
        accepted_audits = {item.segment_id: item for item in audits if item.accepted}
        synthesis_map = {item.synthesis_id: item for item in syntheses}
        chapter_groups: dict[int, list[NarrationSegmentArtifact]] = {}
        for segment in segments:
            chapter_groups.setdefault(segment.chapter_index, []).append(segment)
        chapters: list[AudiobookChapterArtifact] = []
        for chapter_index, rows in sorted(chapter_groups.items()):
            rows.sort(key=lambda item: item.segment_index)
            if any(item.segment_id not in accepted_audits for item in rows):
                continue
            accepted_syntheses = [synthesis_map[accepted_audits[item.segment_id].synthesis_id] for item in rows]
            audio, metrics = assemble_wav([self.store.load_audio(item) for item in accepted_syntheses], pause_ms=plan.sentence_pause_ms)
            chapter_audio_id = _stable_id("audiobook-chapter", plan.run_id, chapter_index)
            stored = self.store.store_assembled_audio(
                data=audio,
                filename=f"chapter-{chapter_index:03d}.wav",
                series_id=plan.series_id,
                story_id=plan.story_id,
                run_id=plan.run_id,
                chapter_id=chapter_audio_id,
                metadata={"kind": "chapter", **metrics},
            )
            title = str((rows[0].metadata or {}).get("chapter_title") or f"Chapter {chapter_index}")
            chapters.append(AudiobookChapterArtifact(
                chapter_audio_id=chapter_audio_id,
                run_id=plan.run_id,
                series_id=plan.series_id,
                story_id=plan.story_id,
                chapter_index=chapter_index,
                title=title,
                accepted_segment_ids=[item.segment_id for item in rows],
                duration_seconds=float(metrics["duration_seconds"]),
                sample_rate=int(metrics["sample_rate"]),
                byte_length=len(audio),
                bucket_name=str(stored.get("bucket_name") or ""),
                object_path=str(stored.get("object_path") or ""),
                metadata={"agent": "AudioAssemblyAgent", **metrics},
            ))
        persisted = self.store.replace_chapters(
            series_id=plan.series_id, story_id=plan.story_id, run_id=plan.run_id, items=chapters,
        )
        manifest = None
        if len(persisted) == len(chapter_groups) and persisted:
            book_audio, metrics = assemble_wav([self.store.load_audio(item) for item in persisted], pause_ms=plan.chapter_pause_ms)
            stored = self.store.store_assembled_audio(
                data=book_audio,
                filename=f"{plan.run_id}.wav",
                series_id=plan.series_id,
                story_id=plan.story_id,
                run_id=plan.run_id,
                metadata={"kind": "audiobook", **metrics},
            )
            manifest = self.store.upsert_manifest(AudiobookManifestArtifact(
                manifest_id=_stable_id("audiobook-manifest", plan.run_id),
                run_id=plan.run_id,
                series_id=plan.series_id,
                story_id=plan.story_id,
                title=plan.title,
                chapter_audio_ids=[item.chapter_audio_id for item in persisted],
                duration_seconds=float(metrics["duration_seconds"]),
                sample_rate=int(metrics["sample_rate"]),
                byte_length=len(book_audio),
                bucket_name=str(stored.get("bucket_name") or ""),
                object_path=str(stored.get("object_path") or ""),
                metadata={"agent": "AudioAssemblyAgent", **metrics},
            ))
        return {
            "chapters": [item.model_dump() for item in persisted],
            "manifest": manifest.model_dump() if manifest else None,
            "run_metadata": _stage_metadata(state, "audio_assembly", started, chapter_count=len(persisted), assembled=manifest is not None),
        }


class AudiobookDecisionAgent:
    def __init__(self, *, store: AudiobookGenerationStore) -> None:
        self.store = store

    def run(self, state: AudiobookGenerationState) -> dict[str, Any]:
        started = time.perf_counter()
        plan = AudiobookPlanArtifact.model_validate(state["plan"])
        segments = [NarrationSegmentArtifact.model_validate(row) for row in state.get("segments") or []]
        latest = _latest_audits([AudioQualityDecisionArtifact.model_validate(row) for row in state.get("audits") or []])
        rejected = [item.segment_id for item in segments if not latest.get(item.segment_id) or not latest[item.segment_id].accepted]
        accepted = bool(segments) and not rejected and bool(state.get("manifest"))
        decision = self.store.upsert_decision(AudiobookDecisionArtifact(
            decision_id=_stable_id("audiobook-decision", plan.run_id),
            run_id=plan.run_id,
            series_id=plan.series_id,
            story_id=plan.story_id,
            accepted=accepted,
            status="accepted" if accepted else "rejected",
            requested_segment_count=len(segments),
            accepted_segment_count=len(segments) - len(rejected),
            rejected_segment_ids=rejected,
            reasons=[] if accepted else [f"{len(rejected)} narration segment(s) failed quality validation."],
            metadata={"agent": "AudiobookDecisionAgent", "max_attempts": int(state.get("max_attempts") or 2)},
        ))
        return {
            "decision": decision.model_dump(),
            "run_metadata": _stage_metadata(state, "audiobook_decision", started, accepted=accepted, rejected_count=len(rejected)),
        }


class AudiobookGenerationRuntime:
    def __init__(
        self,
        *,
        persistence: PersistenceRuntimeClient,
        synthesis_provider: SpeechSynthesisProvider,
        transcription_provider: SpeechTranscriptionProvider,
        checkpointer: BaseCheckpointSaver | None = None,
        allow_in_memory_checkpointer: bool = False,
    ) -> None:
        self.persistence = persistence
        self.store = AudiobookGenerationStore(persistence)
        self.synthesis_provider = synthesis_provider
        self.transcription_provider = transcription_provider
        resolved = _resolve_checkpointer(persistence, checkpointer, allow_in_memory_checkpointer)
        self.graph = build_audiobook_generation_graph(
            store=self.store,
            synthesis_provider=synthesis_provider,
            transcription_provider=transcription_provider,
            checkpointer=resolved,
        )

    def invoke(
        self,
        *,
        series_id: str,
        story_id: str,
        run_id: str,
        thread_id: str,
        narrator_voice: str = "af_bella",
        max_chapters: int = 0,
        max_segment_chars: int = 1800,
        max_attempts: int = 2,
    ) -> AudiobookGenerationResult:
        context = self.store.load_context(series_id=series_id, story_id=story_id)
        state = self.graph.invoke(
            {
                "series_id": series_id,
                "story_id": story_id,
                "run_id": run_id,
                "context": _serialize_context(context),
                "narrator_voice": narrator_voice,
                "max_chapters": max(0, int(max_chapters)),
                "max_segment_chars": max(400, int(max_segment_chars)),
                "max_attempts": max(1, int(max_attempts)),
                "syntheses": [],
                "audits": [],
                "run_metadata": {},
            },
            config={"configurable": {"thread_id": thread_id}},
        )
        return _result_from_state(state)

    def retry_rejected(
        self,
        *,
        series_id: str,
        story_id: str,
        run_id: str,
        max_attempts: int = 2,
    ) -> AudiobookGenerationResult:
        plan = self.store.list_plan(series_id=series_id, story_id=story_id, run_id=run_id)
        segments = self.store.list_segments(series_id=series_id, story_id=story_id, run_id=run_id)
        syntheses = self.store.list_syntheses(series_id=series_id, story_id=story_id, run_id=run_id)
        audits = self.store.list_audits(series_id=series_id, story_id=story_id, run_id=run_id)
        if not segments:
            raise FileNotFoundError(f"No persisted audiobook run '{run_id}' was found.")
        state: AudiobookGenerationState = {
            "series_id": series_id,
            "story_id": story_id,
            "run_id": run_id,
            "plan": plan.model_dump(),
            "segments": [item.model_dump() for item in segments],
            "syntheses": [item.model_dump() for item in syntheses],
            "audits": [item.model_dump() for item in audits],
            "max_attempts": max(1, int(max_attempts)),
            "run_metadata": {},
        }
        synthesis_agent = VoiceSynthesisAgent(store=self.store, synthesis_provider=self.synthesis_provider)
        audit_agent = AudioQAAgent(store=self.store, transcription_provider=self.transcription_provider)
        latest = _latest_audits(audits)
        retryable_audit_ids = {
            item.audit_id
            for item in latest.values()
            if not item.accepted and any(issue.startswith("transcription_error:") for issue in item.issues)
        }
        if retryable_audit_ids:
            retained = [item for item in audits if item.audit_id not in retryable_audit_ids]
            state["audits"] = [item.model_dump() for item in retained]
            self.store.replace_audits(
                series_id=series_id,
                story_id=story_id,
                run_id=run_id,
                items=retained,
            )
            state.update(audit_agent.run(state))
        while _route_after_audio_qa(state) == "retry":
            state.update(synthesis_agent.run(state))
            state.update(audit_agent.run(state))
        state.update(AudioAssemblyAgent(store=self.store).run(state))
        state.update(AudiobookDecisionAgent(store=self.store).run(state))
        return _result_from_state(state)


def build_audiobook_generation_graph(
    *,
    store: AudiobookGenerationStore,
    synthesis_provider: SpeechSynthesisProvider,
    transcription_provider: SpeechTranscriptionProvider,
    checkpointer: BaseCheckpointSaver | None = None,
):
    graph = StateGraph(AudiobookGenerationState)
    graph.add_node("audiobook_planning", AudiobookPlanningAgent(store=store).run)
    graph.add_node("narration_preparation", NarrationPreparationAgent(store=store).run)
    graph.add_node("voice_synthesis", VoiceSynthesisAgent(store=store, synthesis_provider=synthesis_provider).run)
    graph.add_node("audio_qa", AudioQAAgent(store=store, transcription_provider=transcription_provider).run)
    graph.add_node("audio_assembly", AudioAssemblyAgent(store=store).run)
    graph.add_node("audiobook_decision", AudiobookDecisionAgent(store=store).run)
    graph.add_edge(START, "audiobook_planning")
    graph.add_edge("audiobook_planning", "narration_preparation")
    graph.add_edge("narration_preparation", "voice_synthesis")
    graph.add_edge("voice_synthesis", "audio_qa")
    graph.add_conditional_edges("audio_qa", _route_after_audio_qa, {"retry": "voice_synthesis", "assemble": "audio_assembly"})
    graph.add_edge("audio_assembly", "audiobook_decision")
    graph.add_edge("audiobook_decision", END)
    return graph.compile(checkpointer=checkpointer)


def _route_after_audio_qa(state: AudiobookGenerationState) -> str:
    segments = [NarrationSegmentArtifact.model_validate(row) for row in state.get("segments") or []]
    syntheses = [AudioSynthesisArtifact.model_validate(row) for row in state.get("syntheses") or []]
    latest = _latest_audits([AudioQualityDecisionArtifact.model_validate(row) for row in state.get("audits") or []])
    max_attempts = max(1, int(state.get("max_attempts") or 2))
    for segment in segments:
        attempts = len([item for item in syntheses if item.segment_id == segment.segment_id])
        if (not latest.get(segment.segment_id) or not latest[segment.segment_id].accepted) and attempts < max_attempts:
            return "retry"
    return "assemble"


def _chunk_narration(text: str, *, max_chars: int) -> list[str]:
    normalized = " ".join(str(text or "").split())
    if not normalized:
        return []
    sentences = [item.strip() for item in re.split(r"(?<=[.!?])\s+", normalized) if item.strip()]
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        pieces = _split_oversized(sentence, max_chars=max_chars)
        for piece in pieces:
            candidate = f"{current} {piece}".strip()
            if current and len(candidate) > max_chars:
                chunks.append(current)
                current = piece
            else:
                current = candidate
    if current:
        chunks.append(current)
    return chunks


def _split_oversized(text: str, *, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    words = text.split()
    pieces: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > max_chars:
            pieces.append(current)
            current = word
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces


def _latest_audits(items: list[AudioQualityDecisionArtifact]) -> dict[str, AudioQualityDecisionArtifact]:
    latest: dict[str, AudioQualityDecisionArtifact] = {}
    for item in items:
        current = latest.get(item.segment_id)
        if current is None or item.attempt >= current.attempt:
            latest[item.segment_id] = item
    return latest


def _context_bias(text: str) -> list[str]:
    words = re.findall(r"\b[A-Z][a-zA-Z'-]{2,}\b", text)
    return _dedupe(words)[:50]


def _serialize_context(context: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in context.items():
        if key == "book_map":
            continue
        if isinstance(value, list):
            result[key] = [item.model_dump() if hasattr(item, "model_dump") else item for item in value]
        elif hasattr(value, "model_dump"):
            result[key] = value.model_dump()
        else:
            result[key] = value
    return result


def _result_from_state(state: AudiobookGenerationState) -> AudiobookGenerationResult:
    return AudiobookGenerationResult(
        series_id=state["series_id"],
        story_id=state["story_id"],
        plan=AudiobookPlanArtifact.model_validate(state["plan"]),
        segments=[NarrationSegmentArtifact.model_validate(item) for item in state.get("segments") or []],
        syntheses=[AudioSynthesisArtifact.model_validate(item) for item in state.get("syntheses") or []],
        audits=[AudioQualityDecisionArtifact.model_validate(item) for item in state.get("audits") or []],
        chapters=[AudiobookChapterArtifact.model_validate(item) for item in state.get("chapters") or []],
        manifest=AudiobookManifestArtifact.model_validate(state["manifest"]) if state.get("manifest") else None,
        decision=AudiobookDecisionArtifact.model_validate(state["decision"]),
        run_metadata=dict(state.get("run_metadata") or {}),
    )


def _resolve_checkpointer(persistence: PersistenceRuntimeClient, checkpointer: BaseCheckpointSaver | None, allow_memory: bool) -> BaseCheckpointSaver:
    if checkpointer is not None:
        return checkpointer
    if getattr(persistence, "engine", None) is not None:
        return SqlCheckpointSaver(engine=persistence.engine)
    if allow_memory:
        return InMemorySaver()
    raise ValueError("AudiobookGenerationRuntime requires a durable checkpointer or initialized persistence engine.")


def _stage_metadata(state: AudiobookGenerationState, stage: str, started: float, **metrics: Any) -> dict[str, Any]:
    metadata = dict(state.get("run_metadata") or {})
    stages = dict(metadata.get("stage_metrics") or {})
    stages[stage] = {"elapsed_seconds": round(time.perf_counter() - started, 4), **metrics}
    metadata["stage_metrics"] = stages
    return metadata


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = ":".join(str(part or "") for part in parts)
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]}"


def _dedupe(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = " ".join(str(value or "").split())
        if text and text.casefold() not in seen:
            seen.add(text.casefold())
            result.append(text)
    return result
