# Phase 3 Current State — 2026-09-12

Status: **ACTIVE HANDOFF / AUTHORITATIVE CURRENT-STATE RECORD**

This record captures the current local-first analysis rebaseline so later sessions do not reconstruct progress from chat history. Always verify live `main`, open PRs/issues and current checks before continuing.

## Authoritative merged baseline

`main` at this handoff:

- `a3396e5cc829008a4bed2af87186726a3e201123`
- PR #222 — dependency-aware event participant-grounding challenger infrastructure

PR #222 exact qualified head:

- `1878167b6344dee34f435831169ac88003d2b3e0`
- Required Check Compatibility — success
- S.A.G.A. v2 Analysis Worker CI — success
- S.A.G.A. v2 LitBank Oracle Baseline — success
- Backend Architecture CI — success

Other important merged checkpoints:

- generic local literary-NLP subprocess boundary: PR #207 / `c1dfa9f9e57545a7a3565b21e779f2514abacd04`
- BookNLP subprocess challenger adapter: PR #210 / `9dfdd7e0c1234c021c9b2d2e5526a27b3d89bfe3`
- repeatable BookNLP component benchmark: PR #212 / `a3aba893f92e9e98e29d5e6f97e08672cc80637f`
- provider-neutral syntax evidence: PR #217
- combined deterministic-quote + gated BookNLP speaker V2: PR #221 / `0d4210f1098d59483497fc70e0d790ab6208d6ad`

The active follow-up branch is `v2/phase-3a-event-patient-audit`, which explains the direct syntactic patient-candidate coverage gap without changing production grounding rules.

## Locked architecture / owner direction

Phase 3 rebuilds textual book analysis around S.A.G.A.'s actual product goal: reverse-engineer novels/series into an evidence-linked narrative model rather than produce summaries.

Locked requirements:

- textual analysis works without paid AI APIs/subscriptions;
- Modal is reserved for image/media generation only;
- prefer deterministic/classical/local methods, then specialized local models, then bounded local generative reasoning only when cheaper tiers leave material ambiguity;
- the existing TypeScript durable worker, Supabase job/lease/run model, B2 source boundary and deterministic provenance remain the application/control-plane foundation;
- provider output is evidence; deterministic S.A.G.A. policy owns canonical IDs, merges, accepted/uncertain/rejected state, persistence and provenance;
- whole-book runtime/RAM/VRAM/model size/license/repeatability are part of provider selection;
- failed/rejected experiments remain durable repository evidence.

Relevant durable decisions: D-026 through D-030.

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

PR #193 added the scene annotation workspace, exact and relaxed ±1-paragraph evaluation, optimal one-to-one tolerant matching, structural floor, lexical floor and deterministic tests.

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

PR #221's merged combined V2 challenger preserves deterministic quote boundaries and maps BookNLP speaker evidence only through already-resolved S.A.G.A. identity spans.

Combined V2:

- matched-known accuracy `0.7007`;
- resolved-speaker accuracy `0.8040`;
- end-to-end recall `0.5994`;
- unresolved rate `0.1285`;
- cross-character contamination `0.1709`.

Versus rejected V1, V2 improves matched-known accuracy by `+0.1345`, end-to-end recall by `+0.1150`, and lowers unresolved rate by `-0.1589`; contamination rises from V1's ultra-conservative `0.1464` to `0.1709` but remains `0.0180` absolute below raw BookNLP. V2 retains about `80.6%` of BookNLP's incremental recall gain over the deterministic floor.

Decision: **combined V2 is the current public speaker challenger, not a production default**.

### Event triggers

| Candidate | Precision | Recall | F1 |
| --- | ---: | ---: | ---: |
| BookNLP-small | **0.8003** | **0.7591** | **0.7791** |
| lexical Tier-0 | 0.4914 | 0.0585 | 0.1045 |

BookNLP gains about `+0.6746` absolute trigger F1 and remains the strongest measured trigger challenger.

### Event participant grounding

PR #222 merged issue #214's first conservative dependency-aware character participant layer:

- direct `nsubj` -> actor;
- direct `dobj` -> patient;
- direct `nsubjpass` -> patient;
- `agent -> pobj` -> actor;
- attachment only through one already-linked S.A.G.A. identity span with matching structural locator;
- provider/coreference cluster IDs never canonical;
- no dative expansion;
- no conjunction inheritance.

The first scorer failed closed at zero coverage because the benchmark-only LitBank oracle locator was incompatible with the provider structural locator. That failed result remains preserved. Production matching was not weakened.

After benchmark-only locator alignment, the corrected scorer reused the exact same BookNLP inference and measured across `7,445` trigger predictions:

- any grounded participant: `3,881` (`52.13%`);
- actor: `3,406` (`45.75%`);
- patient: `822` (`11.04%`);
- actor + patient: `347` (`4.66%`);
- actor-opportunity events: `4,067`, grounding yield `83.75%`;
- direct `dobj`/`nsubjpass` patient-candidate events: `2,476`, grounding yield `33.20%`.

Trigger P/R/F1 remained exactly `0.8003 / 0.7591 / 0.7791`.

Corrected grounding report fingerprint:

`d2392c11869bf42d92d244af3cc58b4b39d360257726f8c6dc27587ff08f2ba0`

### Direct patient-candidate audit

The follow-up scorer-only audit ran on the same preserved BookNLP inference:

- exact measured scorer head: `dc71151491e8fafb8f92f3fad98921bdb57d1c2d`;
- attempted/completed/failed: `100 / 100 / 0`;
- typecheck: pass;
- tests: **`139 / 139` pass**;
- report fingerprint: `c8f36fb6a0af333c70c038e7dbe42ef94d78c3d1daf5b41fae24d6e4d412a571`;
- artifact ID: `10316914749`;
- artifact digest: `sha256:930dfb6844be99dad6fbdf4c8fd37382eadce56d3c232946bea978c8a727fc81`.

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

Within the no-entity bucket:

- `NOUN` `1,216` (`80.90%`);
- `PRON` `226` (`15.04%`);
- `PROPN` only `7` (`0.47%`).

Interpretation: the low direct patient-candidate yield is **not** hiding a measured S.A.G.A. linked-character attachment failure. It is mostly a broad syntactic-domain effect from direct objects and unannotated common nouns/pronouns.

Decision: **keep the strict character-grounding policy unchanged**. Do not add dative, conjunction inheritance or provider clusters merely to raise coverage. These diagnostics still do not measure participant correctness because LitBank event annotations lack S.A.G.A.-style actor/patient gold.

Detailed evidence:

- `docs/experiments/BOOKNLP_EVENT_DEPENDENCY_GROUNDING.md`
- `docs/experiments/BOOKNLP_EVENT_PATIENT_AUDIT.md`

## BookNLP public component repeatability / resources

Two independent 100-document CPU runs on exact benchmark implementation head `f013f23f11d2883e8ef1f2e70f9e181e8556df08` produced the exact same semantic report fingerprint:

`e0ec94d8d1f678f98057a29117d365926a3253a4a6d5e6e0f7c96e36cab3bef9`

- run 1: wall clock `452.68 s`, peak RSS `1123.8 MiB`;
- run 2: wall clock `293.66 s`, peak RSS `1157.2 MiB`;
- model artifacts: `160,398,571 bytes`;
- each run: `100 / 100` documents completed, zero failures.

Both heavyweight attempts passed typecheck and `111 / 111` analysis-worker tests.

BookNLP model-weight licensing remains **unverified** and therefore blocks production adoption regardless of quality.

## Phase 3B local literary-NLP execution boundary

PR #207 established the generic local execution/validation boundary:

- `LocalLiteraryEvidenceProvider` interface;
- versioned `saga-local-literary-subprocess-v1` health/analyze/error protocol;
- `shell: false` process execution;
- bounded stdin/stdout/stderr/time;
- terminal/retryable provider error classification;
- exact provider/configuration/input fingerprint checks;
- exact Unicode source-span validation and structural-locator containment;
- duplicate/malformed/partial evidence rejection;
- sanitized inherited environment;
- model-light CI only.

PR #210 instantiated the BookNLP-specific adapter/process/runner behind that boundary. PR #217 exposed validated provider-neutral syntax evidence.

Important distinction: the real 100-document BookNLP benchmarks used the dedicated benchmark harness, not the generic subprocess provider end-to-end. Therefore the following remains open:

- real BookNLP health/analyze through `saga-local-literary-subprocess-v1` with exact preinstalled artifacts/caches;
- one-shot provider startup/runtime measurement through that boundary;
- optional persistent loopback comparison only if startup cost justifies it.

Subprocess remains an experimental transport baseline, not a permanent winner.

## Private source availability blocker

The user-owned primary-suite EPUB binaries remain unavailable to the current execution environment. Historical paths remain under `B:/Documents/PyCharm/graduationProject/uploads/...`.

Do not replace the private suite with public-domain novels. Continue source-neutral infrastructure only where it advances the architecture without pretending to satisfy the product gate.

## Historical full-analysis breadth reference

The old graduation prototype processed the complete *The Cruel Prince* and reported 111,351 words, 35 chapters, 135 scenes, 53 unique characters, 55 locations, 24 key causal events, average tension 5.49/10 and reported climax chapter 16.

These are **coverage/reference observations, not gold truth**.

## Immediate continuation order

1. Qualify and merge the patient-candidate failure-mode audit so its zero-linked-miss result and denominator semantics become durable repository evidence.
2. Execute and measure real BookNLP end-to-end through the generic subprocess boundary with exact preinstalled artifacts/caches; compare persistent loopback only if one-shot startup/runtime evidence justifies it.
3. For event analysis, target new semantic capability rather than synthetic character-coverage inflation: explicit non-character entity participants and/or negation/modality/realis evaluation.
4. When private EPUB access returns, generate scene/dialogue/event annotation workspaces for Harry Potter, The Cruel Prince, Caraval and ACOFAS and score all surviving candidates.
5. Adopt no identity, scene, speaker or event default before private-suite evidence, repeatability, resource cost, failure-mode review and production-compatible licensing.
6. Preserve negative experiments and exact source/model/config/resource fingerprints.
7. Do not use Modal for textual analysis, add paid AI dependencies, or deploy Vercel without fresh explicit owner approval.

## References

- Phase 3 tracker: issue #185
- BookNLP provider adapter: PR #210
- public component benchmark: PR #212
- combined speaker challenger: issue #213 / PR #221 merged
- event grounding: issue #214 / PR #222 merged
- scene protocol: `docs/experiments/SCENE_SEGMENTATION_BENCHMARK.md`
- dialogue protocol: `docs/experiments/DIALOGUE_SPEAKER_BENCHMARK.md`
- event protocol: `docs/experiments/EVENT_CANDIDATE_BENCHMARK.md`
- BookNLP component result: `docs/experiments/BOOKNLP_COMPONENT_BENCHMARK.md`
- event grounding result: `docs/experiments/BOOKNLP_EVENT_DEPENDENCY_GROUNDING.md`
- event patient audit: `docs/experiments/BOOKNLP_EVENT_PATIENT_AUDIT.md`
- local provider protocol: `docs/v2/LOCAL_LITERARY_PROVIDER_PROTOCOL.md`
- component scorecard: `docs/validation/PHASE_V2_3_COMPONENT_SCORECARD.md`
