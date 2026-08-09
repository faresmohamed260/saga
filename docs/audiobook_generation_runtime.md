# Audiobook Generation Runtime

`packages/audiobook_generation` is the active LangGraph-native audiobook slice. It consumes only generated stories that passed `require_narrative_semantic_acceptance(...)` and has no legacy dependency.

## Ownership

The package owns portable contracts and agents for:

- audiobook plans and narrator assignments
- bounded narration segments
- synthesis attempts and provider telemetry
- technical WAV inspection
- transcription-based semantic quality decisions
- chapter and full-book assembly
- bounded retry, infrastructure re-audit, and selective resume
- persisted manifests, decisions, and runtime reports

Concrete providers are injected through `SpeechSynthesisProvider` and `SpeechTranscriptionProvider`. The production composition root wires Supabase persistence/object storage, the persisted 47-account Modal pool and Kokoro service, and Mistral Voxtral transcription. The graph itself imports none of those provider implementations. Audio bytes are persisted immediately and never enter LangGraph checkpoint state.

## Graph

1. audiobook planning
2. narration preparation and sentence-safe segmentation
3. Kokoro synthesis
4. technical WAV and transcription/WER audit
5. bounded conditional retry
6. accepted-segment chapter and book assembly
7. fail-closed final decision

Stable segment IDs and run-scoped records make jobs resumable. Accepted segments are never regenerated. A transient transcription failure re-audits the existing technically valid WAV; synthesis is repeated only for technical or semantic audio failures.

## Quality Policy

Technical QA requires mono 16-bit PCM WAV at the planned sample rate, a nontrivial payload and duration, audible signal, bounded silence/clipping, and plausible speaking rate. Semantic QA transcribes each segment with `voxtral-mini-latest` and accepts word error rate at or below `0.25`. Provider errors and empty transcripts fail closed.

Only chapters whose every segment is accepted are assembled. A full manifest exists only when every selected chapter is assembled.

## Operations

Run a bounded audiobook job:

```powershell
python scripts/run_audiobook_generation.py `
  --series-id <series-id> `
  --story-id <accepted-story-id> `
  --run-id <run-id> `
  --max-chapters 1 `
  --max-attempts 2
```

Resume only unresolved work:

```powershell
python scripts/run_audiobook_generation.py `
  --series-id <series-id> `
  --story-id <story-id> `
  --run-id <run-id> `
  --retry-existing `
  --max-attempts 2
```

Required configuration follows `SAGA_RUNTIME_DB_*`, `SAGA_SUPABASE_*`, `MISTRAL_API_KEY`, and persisted `modal_kokoro_tts` provider config. Overrides are `SAGA_AUDIOBOOK_TRANSCRIPTION_*` and `SAGA_AUDIOBOOK_TTS_*`.

## Live Validation

Validation used accepted persisted stories and the production Supabase, Modal/Kokoro, and Mistral paths.

- *The Lost Sisters*: 102.855-second chapter, technical pass, Voxtral WER `0.1238`, accepted. Initial Kokoro synthesis was 63.4 seconds. A corrected transcription-only resume took 34.3 seconds and performed zero resynthesis.
- *The Queen of Nothing*: 88.18-second chapter, technical pass, Voxtral WER `0.0463`, accepted. Kokoro synthesis took 59.1 seconds and transcription took 15.7 seconds; complete process time was 92.6 seconds.
- Both outputs are mono 24 kHz 16-bit WAV. Mean levels were `-22.4 dB` and `-19.3 dB`; both peaked at `-0.3 dB` without technical clipping rejection.
- The clean persistence runtime now owns `modal_kokoro_tts` configuration for all 47 Modal accounts. Live runs used `member-01`.

Full WAVs, 20-second previews, and result JSON are under `tmp_live_audiobook_generation/`. Durable audio and reports are in Supabase object storage.
