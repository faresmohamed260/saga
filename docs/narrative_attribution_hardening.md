# Narrative Attribution Hardening

Production attribution hardening lives in the active rebuilt architecture only. It is not an identity/coref concern unless canonical identity resolution is proven wrong.

## Ownership

- `packages.analysis_foundation`: owns deterministic scene-level narrative grounding.
- `packages.canon_extraction`: consumes grounding and rejects unsupported participants/relationships at artifact creation.
- `packages.character_world_modeling`: consumes grounded canon evidence and treats recipient, addressee, contextual, and mentioned-only evidence as non-primary profile/state support.

No legacy code, dashboard code, or book-specific logic owns this behavior.

## Contracts

Analysis foundation persists `SceneNarrativeGrounding` under `scene.metadata["narrative_grounding"]`:

- narrator perspective
- narrator character id/name when inferable
- addressee character ids/names when inferable
- direct evidence spans
- confidence
- diagnostics

Canon extraction passes `narrative_grounding` into event/entity/relationship prompts and post-processing. Character/world modeling carries the same grounding inside scene evidence and adds `character_event_role` to evidence rows.

## Deterministic Gates

- First-person narrator placeholders resolve only through grounded narrator ids.
- Ambiguous second-person/addressee placeholders are rejected unless one addressee is inferable.
- Possessive object provenance such as `Madoc's seal` is not character participation.
- Tertiary disclosure targets such as `ask Locke to inform Madoc` are not primary participants.
- Named active claims require source-scene action support when the named character appears in that scene.
- Character-to-character artifact usage and location association relationships are rejected.
- Comparative family/romance context is rejected as a direct relationship.
- CWM ignores low-support LLM synthesis and emits conservative deterministic profile/state fallbacks.

## Metrics

Primary pass/fail metric:

- `attribution_f1`

Supporting metrics:

- `participant_precision`
- `participant_recall`
- `narrator_attribution_accuracy`
- `unsupported_ref_rate`
- `contamination_rate`

Evaluator:

```powershell
python scripts/evaluate_narrative_attribution.py `
  --series-id real-holly-black-lost-sisters-v10 `
  --database-url "<SAGA_RUNTIME_DB_URL>" `
  --cases-json tests\fixtures\narrative_attribution\lost_sisters_attribution_cases.json `
  --output-json tmp_live_canon_extraction_pg\lost_sisters_v10_attribution_eval_r18.json
```

## Latest Real Validation

Source:

- `D:\Books\Ebooks\Holly Black\The Lost Sisters\The Lost Sisters.epub`

Analysis foundation:

- Thread: `narrative-grounding-af-v10-r13`
- Runtime: `45.3517s`
- Provider/model: `modal_xcore_litbank` / `sapienzanlp/xcore-litbank`
- Grounding: `15/15` scenes first-person, `15/15` narrator resolved, `15/15` addressee present, diagnostics `[]`
- Report: `providers/analysis-foundation/reports/validation/051b84ea6e62-real-holly-black-lost-sisters-v10-narrative-grounding-af-v10-r13-analysis-foundation-report.json`

Canon extraction:

- Thread: `narrative-grounding-canon-v10-r18`
- Runtime: `425.3303s`
- Counts: `36` events, `112` entities, `32` relationships, `36` timeline rows
- Provider/model: `ollama` / `gpt-oss:120b-cloud`
- Report: `providers/canon-extraction/reports/validation/eeca0e779c6a-real-holly-black-lost-sisters-v10-narrative-grounding-canon-v10-r18-canon-extraction-report.json`

Attribution evaluation:

- Output: `tmp_live_canon_extraction_pg\lost_sisters_v10_attribution_eval_r18.json`
- `participant_precision`: `1.0`
- `participant_recall`: `1.0`
- `attribution_f1`: `1.0`
- `narrator_attribution_accuracy`: `1.0`
- `unsupported_ref_rate`: `0.0`
- `contamination_rate`: `0.0`

Before/after comparison:

- Baseline file: `tmp_live_canon_extraction_pg\lost_sisters_v9_attribution_eval_r12_fixture.json`
- Current file: `tmp_live_canon_extraction_pg\lost_sisters_v10_attribution_eval_r18.json`
- `attribution_f1`: `0.6154` -> `1.0`
- `narrator_attribution_accuracy`: `0.0` -> `1.0`
- `contamination_rate`: `0.6667` -> `0.0`
- Baseline contamination examples:
  - note-to-Locke event included `char-madoc` and missed narrator `char-taryn`
  - midnight meeting missed narrator `char-taryn`
  - marriage conditions included forbidden `char-vivi` and missed narrator `char-taryn`

Character/world modeling:

- Thread: `narrative-grounding-cwm-v10-r19`
- Runtime stage time: `358.0327s`
- Counts: `18` character profiles, `18` stable character states, `112` world states
- Report: `providers/character-world-modeling/reports/validation/b61b53b2534b-real-holly-black-lost-sisters-v10-narrative-grounding-cwm-v10-r19-character-world-modeling-report.json`

Manual downstream audit passed for:

- Locke did not inherit `Madoc's seal`.
- Heather did not inherit note-to-Locke assistance.
- Jude did not inherit marriage/wedding claims.
- Madoc did not inherit marriage/wedding claims.
- No real self-edge relationship string was found.
- Low-support Heather/Madoc profiles use conservative grounded fallback text.

## Remaining Risks

- Provider extraction remains nondeterministic in wording and decomposition, so regression checks should target semantic invariants rather than exact event counts.
- Some character profiles can still be sparse when canon evidence has no primary grounded action for that character; this is intentional and safer than hallucinated detail.
- First-seen summaries for high-support characters can still reflect broad scene context and may need a later dedicated profile-quality pass.
