# Phase 3 Current State — 2026-09-12

Status: **ACTIVE HANDOFF / AUTHORITATIVE CURRENT-STATE RECORD**

This record captures the current local-first analysis rebaseline so later sessions do not reconstruct progress from chat history. Always verify live `main`, open PRs/issues and current checks before continuing.

## Authoritative merged baseline

`main` at this handoff:

- `161f84143cd14158aa72242beb46c669bf068de5`
- PR #223 — direct event patient-candidate failure-mode audit

PR #223 closed issue #214 after proving that the low direct patient-candidate grounding yield is not hiding a measured deterministic linked-character attachment defect.

Important merged checkpoints:

- generic local literary-NLP subprocess boundary: PR #207
- BookNLP subprocess challenger adapter: PR #210
- repeatable BookNLP component benchmark: PR #212
- provider-neutral syntax evidence: PR #217
- combined deterministic-quote + gated BookNLP speaker V2: PR #221
- dependency-aware event participant-grounding challenger: PR #222
- direct patient-candidate failure-mode audit: PR #223

Current active Phase-3B branch:

- `v2/phase-3b-booknlp-subprocess-proof`
- issue #224 — real BookNLP through generic subprocess boundary
- exact measured runtime head: `dfa58d7e505eaebbd56605cfb97e879d1d1136cb`
- heavyweight run `34759959737`: success
- artifact ID `10318109017`
- artifact digest `sha256:dbb49b34a31e0a711052c72cc19b8bce6d628114dde96d1897b9daf9791fd8a2`

Documentation commits on the branch may be newer than the measured runtime SHA. Qualify the exact final PR head before merge.

## Locked architecture / owner direction

Phase 3 rebuilds textual book analysis around S.A.G.A.'s actual product goal: reverse-engineer novels/series into an evidence-linked narrative model rather than produce summaries.

Locked requirements:

- textual analysis works without paid AI APIs/subscriptions;
- Modal is reserved for image/media generation only;
- S.A.G.A. Modal work may use only `modal-03` through `modal-41`;
- prefer deterministic/classical/local methods, then specialized local models, then bounded local generative reasoning only when cheaper tiers leave material ambiguity;
- the existing TypeScript durable worker, Supabase job/lease/run model, B2 source boundary and deterministic provenance remain the application/control-plane foundation;
- provider output is evidence; deterministic S.A.G.A. policy owns canonical IDs, merges, accepted/uncertain/rejected state, persistence and provenance;
- whole-book runtime/RAM/VRAM/model size/license/repeatability are part of provider selection;
- failed/rejected experiments remain durable repository evidence.

Relevant durable decisions: D-026 through D-031.

## Primary evaluation corpus

Primary product qualification remains the private/user-owned modern-fiction suite:

- *Harry Potter and the Philosopher's Stone*;
- *The Cruel Prince*;
- *Caraval*;
- ACOTAR series, with *A Court of Frost and Starlight* as historical regression anchor.

LitBank remains **secondary public/gold regression evidence** for component isolation and reproducibility. It cannot by itself promote a provider into production. BookNLP's speaker/event models use LitBank-derived literary annotations, so private-suite generalization evidence is especially important.

## Component benchmark scorecard

The compact authoritative ledger is:

- `docs/validation/PHASE_V2_3_COMPONENT_SCORECARD.md`

### Character identity

BookNLP-small remains **rejected for primary character identity** based on repeatable 100-document LitBank evidence:

- canonical precision `0.4613`;
- canonical recall `0.6030`;
- incorrect-merge rate `0.1934`;
- fragmentation rate `0.4607`;
- linked-mention precision `0.2158`;
- linked-mention recall `0.1161`;
- cluster purity `0.8667`.

GLiNER-small-v2.1 + F-Coref produced useful component smoke evidence but are not adoption-ready. Primary-suite qualification remains mandatory.

### Scene segmentation

Scene annotation/evaluation infrastructure exists, including exact and relaxed ±1-paragraph evaluation, optimal one-to-one tolerant matching, structural and lexical floors, and annotation finalization checks.

**No scene method is adopted.** Primary-suite annotations remain blocked by private source availability.

### Dialogue / quote detection

100-document pinned LitBank quote result:

| Candidate | Precision | Recall | F1 |
| --- | ---: | ---: | ---: |
| S.A.G.A. deterministic quote detector | **0.8570** | 0.8555 | **0.8563** |
| BookNLP-small | 0.7706 | **0.8640** | 0.8146 |

Decision: **retain deterministic quote boundaries as the current measured public-gold leader**.

### Speaker attribution

Raw component floors with oracle LitBank identity:

| Metric | BookNLP-small | Deterministic floor |
| --- | ---: | ---: |
| matched-known accuracy | **0.7830** | 0.3265 |
| resolved-speaker accuracy | **0.8057** | 0.5278 |
| end-to-end speaker recall | **0.6765** | 0.2793 |
| unresolved rate | **0.0282** | 0.3815 |
| cross-character contamination | **0.1889** | 0.2921 |

Merged combined V2 challenger:

- matched-known accuracy `0.7007`;
- resolved-speaker accuracy `0.8040`;
- end-to-end recall `0.5994`;
- unresolved rate `0.1285`;
- cross-character contamination `0.1709`.

Versus rejected V1, V2 improves matched-known accuracy by `+0.1345`, end-to-end recall by `+0.1150`, and lowers unresolved rate by `-0.1589`; contamination remains `0.0180` absolute below raw BookNLP.

Decision: **combined V2 is the current public speaker challenger, not a production default**.

### Event triggers

| Candidate | Precision | Recall | F1 |
| --- | ---: | ---: | ---: |
| BookNLP-small | **0.8003** | **0.7591** | **0.7791** |
| lexical Tier-0 | 0.4914 | 0.0585 | 0.1045 |

BookNLP gains about `+0.6746` absolute trigger F1 and remains the strongest measured trigger challenger.

### Event participant grounding

The merged conservative dependency-aware character participant layer uses:

- direct `nsubj` -> actor;
- direct `dobj` -> patient;
- direct `nsubjpass` -> patient;
- `agent -> pobj` -> actor;
- attachment only through one already-linked S.A.G.A. identity span with matching structural locator;
- provider/coreference cluster IDs never canonical;
- no dative expansion;
- no conjunction inheritance.

The corrected scorer reused the exact same preserved BookNLP inference and measured across `7,445` trigger predictions:

- any grounded participant: `3,881` (`52.13%`);
- actor: `3,406` (`45.75%`);
- patient: `822` (`11.04%`);
- actor + patient: `347` (`4.66%`);
- actor-opportunity events: `4,067`, grounding yield `83.75%`;
- direct `dobj`/`nsubjpass` patient-candidate events: `2,476`, grounding yield `33.20%`.

Trigger P/R/F1 remained exactly `0.8003 / 0.7591 / 0.7791`.

### Direct patient-candidate audit

The merged scorer-only audit ran on the same preserved BookNLP inference:

- attempted/completed/failed: `100 / 100 / 0`;
- typecheck: pass;
- tests: `139 / 139` pass;
- report fingerprint: `c8f36fb6a0af333c70c038e7dbe42ef94d78c3d1daf5b41fae24d6e4d412a571`.

Across `2,546` direct syntactic patient candidates:

- grounded character `824` (`32.36%`);
- same character already grounded through another mention `4` (`0.16%`);
- **true linked-character not grounded `0`**;
- ambiguous linked character `17` (`0.67%`);
- **structural locator mismatch `0`**;
- **gold-linked person missing from oracle identity `0`**;
- unresolved person gold `8` (`0.31%`);
- non-person gold `142` (`5.58%`);
- provider non-person only `15` (`0.59%`);
- provider person only `33` (`1.30%`);
- no identity/entity evidence `1,503` (`59.03%`).

The candidate denominator is dominated by `dobj` (`2,304 / 2,546`, `90.49%`), where only `29.77%` map to grounded characters. Passive subjects (`nsubjpass`) map to grounded characters `57.02%` of the time.

Within the no-entity bucket, `NOUN` accounts for `1,216 / 1,503` (`80.90%`), `PRON` `226` (`15.04%`), and `PROPN` only `7` (`0.47%`).

Interpretation: the low direct patient-candidate yield is **not** hiding a measured S.A.G.A. linked-character attachment failure. Do not add dative, conjunction inheritance or provider clusters merely to raise coverage.

These diagnostics still do not measure participant correctness because LitBank event annotations lack S.A.G.A.-style actor/patient gold.

## BookNLP public component repeatability / resources

Two independent 100-document CPU runs produced the exact same semantic report fingerprint:

`e0ec94d8d1f678f98057a29117d365926a3253a4a6d5e6e0f7c96e36cab3bef9`

- run 1: wall clock `452.68 s`, peak RSS `1123.8 MiB`;
- run 2: wall clock `293.66 s`, peak RSS `1157.2 MiB`;
- task-model artifacts: `160,398,571 bytes`;
- each run: `100 / 100` documents completed, zero failures.

BookNLP model-weight licensing remains **unverified** and therefore blocks production adoption regardless of quality.

## Phase 3B real BookNLP subprocess proof

Issue #224 has now produced the real-model boundary evidence that was previously missing.

Pinned document:

- LitBank `1023_bleak_house_brat`;
- source `11,738` bytes/code points;
- `2,319` syntax tokens.

Direct preserved BookNLP native output and the complete generic subprocess path produced the exact same provider-neutral evidence fingerprint:

`8be0f789a80ecf47c0b902b51e0492c17ef016023c3e215df6a4d57ff3e27add`

Exact evidence counts on both sides:

- identity mentions `230`;
- entities `230`;
- quotes `5`;
- event triggers `20`;
- syntax tokens `2,319`.

Second exact-head proof run (`34759959737`):

- `health()` `2.847 s`;
- one-shot generic `analyze()` `8.930 s`;
- complete process-tree wall clock `12.678 s`;
- peak aggregate process-tree RSS `1040.5 MiB`;
- typecheck pass;
- tests `139 / 139` pass;
- artifact ID `10318109017`;
- artifact digest `sha256:dbb49b34a31e0a711052c72cc19b8bce6d628114dde96d1897b9daf9791fd8a2`.

An earlier independent proof run produced the same semantic evidence/counts with `health()` `2.578 s`, `analyze()` `6.314 s`, and `1037.2 MiB` peak process-tree RSS.

Prepared offline artifact footprint:

- BookNLP task weights `160,398,571 bytes` (~`153.0 MiB`);
- transformer cache `284,705,427 bytes` (~`271.5 MiB`);
- spaCy model `15,242,123 bytes` (~`14.5 MiB`);
- total `460,346,121 bytes` (~`439.0 MiB`).

One loaded BookNLP instance on the same document measured:

- initialization `1.229 s`;
- repeated processing `4.505 s` and `4.140 s`;
- identical native output fingerprints;
- peak RSS `732.0 MiB`.

On the same run, one-shot generic `analyze()` was about `2.16x` the second warm processing pass.

Decision: **the generic subprocess semantic boundary is validated for real BookNLP, and the measured one-shot process/model recreation overhead is material enough to justify a persistent loaded Python runtime challenger.** Persisting only the outer Node wrapper would not solve the measured model-runtime recreation.

This is a runtime-architecture experiment decision, not a BookNLP quality promotion. Detailed evidence: `docs/experiments/BOOKNLP_SUBPROCESS_RUNTIME_PROOF.md`.

Whole Hugging Face/spaCy cache-directory manifest hashes varied across independent preparations while immutable task-weight digests and semantic evidence stayed stable. Treat whole cache directories as mutable runtime caches, not stable model identities.

## Private source availability blocker

The user-owned primary-suite EPUB binaries remain unavailable to the current execution environment. Historical paths remain under `B:/Documents/PyCharm/graduationProject/uploads/...`.

Do not replace the private suite with public-domain novels. Continue source-neutral infrastructure only where it advances the architecture without pretending to satisfy the product gate.

## Immediate continuation order

1. Qualify and merge issue #224's real BookNLP generic-subprocess proof on the exact final PR head.
2. Open and measure a persistent **loaded Python** BookNLP provider/runtime challenger against the validated one-shot baseline. Require exact semantic equality, bounded/private transport, secret isolation, timeout/failure handling, and resource measurements before considering a transport change.
3. For event analysis, target new semantic capability rather than synthetic character-coverage inflation: explicit non-character entity participants and/or negation/modality/realis evaluation.
4. When private EPUB access returns, generate scene/dialogue/event annotation workspaces for Harry Potter, The Cruel Prince, Caraval and ACOFAS and score all surviving candidates.
5. Adopt no identity, scene, speaker or event default before private-suite evidence, repeatability, resource cost, failure-mode review and production-compatible licensing.
6. Preserve negative experiments and exact source/model/config/resource fingerprints.
7. Do not use Modal for textual analysis, use Modal accounts outside `modal-03` through `modal-41`, add paid AI dependencies, or deploy Vercel without fresh explicit owner approval.

## References

- Phase 3 tracker: issue #185
- BookNLP provider adapter: PR #210
- public component benchmark: PR #212
- combined speaker challenger: PR #221 merged
- event grounding: PR #222 merged
- event patient audit: PR #223 merged
- runtime proof: issue #224 / `docs/experiments/BOOKNLP_SUBPROCESS_RUNTIME_PROOF.md`
- scene protocol: `docs/experiments/SCENE_SEGMENTATION_BENCHMARK.md`
- dialogue protocol: `docs/experiments/DIALOGUE_SPEAKER_BENCHMARK.md`
- event protocol: `docs/experiments/EVENT_CANDIDATE_BENCHMARK.md`
- BookNLP component result: `docs/experiments/BOOKNLP_COMPONENT_BENCHMARK.md`
- event grounding result: `docs/experiments/BOOKNLP_EVENT_DEPENDENCY_GROUNDING.md`
- event patient audit: `docs/experiments/BOOKNLP_EVENT_PATIENT_AUDIT.md`
- local provider protocol: `docs/v2/LOCAL_LITERARY_PROVIDER_PROTOCOL.md`
- component scorecard: `docs/validation/PHASE_V2_3_COMPONENT_SCORECARD.md`
