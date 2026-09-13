# Phase 3 Current State — through 2026-09-13

Status: **ACTIVE HANDOFF / AUTHORITATIVE CURRENT-STATE RECORD**

This record captures the current local-first analysis rebaseline so later sessions do not reconstruct progress from chat history. Always verify live `main`, open PRs/issues and current checks before continuing.

## Authoritative merged baseline

`main` at this handoff:

`7261d9c31adacdb80b7304f1e47808353f42e152`

Latest merged checkpoints:

- generic local literary-NLP subprocess boundary: PR #207;
- BookNLP subprocess challenger adapter: PR #210;
- repeatable BookNLP component benchmark: PR #212;
- provider-neutral syntax evidence: PR #217;
- combined deterministic-quote + gated BookNLP speaker V2: PR #221;
- dependency-aware event participant-grounding challenger: PR #222;
- direct patient-candidate failure-mode audit: PR #223;
- real BookNLP one-shot generic-subprocess proof: PR #225;
- persistent loaded BookNLP stdio runtime: PR #227.

Issues #214, #224 and #226 are complete.

The current BookNLP transport decision is durable as D-032: use persistent local stdio for repeated BookNLP analysis; retain the generic one-shot subprocess path as the simple correctness/reference implementation. This is a runtime decision, not production adoption of BookNLP.

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

Relevant durable decisions: D-026 through D-032.

## Primary evaluation corpus

Primary product qualification remains the private/user-owned modern-fiction suite:

- *Harry Potter and the Philosopher's Stone*;
- *The Cruel Prince*;
- *Caraval*;
- ACOTAR series, with *A Court of Frost and Starlight* as historical regression anchor.

LitBank remains **secondary public/gold regression evidence** for component isolation and reproducibility. It cannot by itself promote a provider into production. BookNLP's speaker/event models use LitBank-derived literary annotations, so private-suite generalization evidence is especially important.

The private EPUB binaries remain unavailable to the current execution environment. Historical paths remain under `B:/Documents/PyCharm/graduationProject/uploads/...`. Do not replace the private suite with public-domain novels.

## Component benchmark scorecard

The compact authoritative ledger is:

`docs/validation/PHASE_V2_3_COMPONENT_SCORECARD.md`

### Character identity

BookNLP-small remains **rejected for primary character identity** based on repeatable 100-document LitBank evidence:

- canonical precision `0.4613`;
- canonical recall `0.6030`;
- incorrect-merge rate `0.1934`;
- fragmentation rate `0.4607`;
- linked-mention precision `0.2158`;
- linked-mention recall `0.1161`;
- cluster purity `0.8667`.

The deterministic attachment-first resolver remains the policy foundation. Primary-suite qualification is still mandatory.

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

BookNLP gains about `+0.6746` absolute trigger F1 and remains the strongest measured public trigger challenger.

### Event participant grounding

The merged conservative dependency-aware **character** participant layer uses:

- direct `nsubj` -> actor;
- direct `dobj` -> patient;
- direct `nsubjpass` -> patient;
- `agent -> pobj` -> actor;
- attachment only through one already-linked S.A.G.A. identity span with matching structural locator;
- provider/coreference cluster IDs never canonical;
- no dative expansion;
- no conjunction inheritance.

Across `7,445` trigger predictions the corrected public diagnostic measured:

- any grounded participant: `3,881` (`52.13%`);
- actor: `3,406` (`45.75%`);
- patient: `822` (`11.04%`);
- actor + patient: `347` (`4.66%`);
- actor-opportunity grounding yield: `83.75%`;
- direct `dobj`/`nsubjpass` patient-candidate grounding yield: `33.20%`.

Trigger P/R/F1 stayed exactly `0.8003 / 0.7591 / 0.7791`.

The patient-candidate audit then completed `100 / 100` documents with zero failures and found across `2,546` direct syntactic patient candidates:

- grounded character `824` (`32.36%`);
- same character already grounded through another mention `4`;
- **true linked-character not grounded `0`**;
- ambiguous linked character `17`;
- **structural locator mismatch `0`**;
- **gold-linked person missing from oracle identity `0`**;
- no identity/entity evidence `1,503` (`59.03%`).

Within the no-evidence bucket, `80.90%` are `NOUN`, `15.04%` are `PRON`, and only `0.47%` are `PROPN`.

Interpretation: the low direct patient-candidate yield is **not** hiding a measured linked-character attachment failure. Do not add dative, conjunction inheritance or provider clusters merely to raise coverage.

These diagnostics do not measure participant correctness because LitBank event annotations lack S.A.G.A.-style actor/patient gold.

## BookNLP public component repeatability / resources

Two independent 100-document CPU runs produced the exact same semantic report fingerprint:

`e0ec94d8d1f678f98057a29117d365926a3253a4a6d5e6e0f7c96e36cab3bef9`

- run 1: wall clock `452.68 s`, peak RSS `1123.8 MiB`;
- run 2: wall clock `293.66 s`, peak RSS `1157.2 MiB`;
- task-model artifacts: `160,398,571 bytes`;
- each run: `100 / 100` documents completed, zero failures.

BookNLP model-weight licensing remains **unverified** and therefore blocks production adoption regardless of quality.

## Phase 3B BookNLP runtime evidence

### One-shot correctness/reference proof

PR #225 validated the real pinned BookNLP model through `saga-local-literary-subprocess-v1` on LitBank document `1023_bleak_house_brat` (`11,738` bytes/code points; `2,319` syntax tokens).

Direct preserved BookNLP output and the complete generic subprocess path produced exact provider-neutral evidence fingerprint:

`8be0f789a80ecf47c0b902b51e0492c17ef016023c3e215df6a4d57ff3e27add`

Counts matched exactly:

- identity mentions `230`;
- entities `230`;
- quotes `5`;
- event triggers `20`;
- syntax tokens `2,319`.

Independent one-shot measurements:

- `health()` `2.578 s`, `analyze()` `6.314 s`, peak process-tree RSS `1037.2 MiB`;
- `health()` `2.847 s`, `analyze()` `8.930 s`, peak process-tree RSS `1040.5 MiB`.

Prepared offline runtime footprint is about `439 MiB`; the three immutable BookNLP task weights are `160,398,571 bytes` of that total.

### Persistent loaded runtime

PR #227 / issue #226 measured one loaded Python BookNLP child behind bounded local stdio.

Exact implementation/benchmark head:

`2fa30b185cb037180f3e7762f2166067096e08c5`

The same heavyweight workflow run `34762397330` was executed twice on that exact SHA on separate hosted runners.

Attempt 1:

- startup/health `3.694 s`;
- analyze `4.977 / 4.627 / 4.368 s`;
- median analyze **`4.627 s`**;
- speedup vs one-shot `6.314 s`: `1.36x`;
- speedup vs one-shot `8.930 s`: `1.93x`;
- peak process-tree RSS `1007.1 MiB`;
- artifact ID `10319696420`;
- digest `sha256:4d064dd228fa6d1ec8b812de3e7b42db778aec3d76671911154da46c78badbc8`.

Attempt 2:

- startup/health `3.134 s`;
- analyze `3.039 / 2.745 / 2.853 s`;
- median analyze **`2.853 s`**;
- speedup vs one-shot `6.314 s`: `2.21x`;
- speedup vs one-shot `8.930 s`: `3.13x`;
- peak process-tree RSS `1028.7 MiB`;
- artifact ID `10319368057`;
- digest `sha256:0e3462ed6a35ef758f1163f5cb78625df0086c40c37d9ab626ef37326e698456`.

Across both attempts:

- all **six** analyses reproduced exact evidence fingerprint `8be0f789a80ecf47c0b902b51e0492c17ef016023c3e215df6a4d57ff3e27add`;
- exact evidence counts stayed `230 / 230 / 5 / 20 / 2,319`;
- typecheck passed;
- analysis-worker tests passed **145 / 145**, up from the pre-persistence `139 / 139` baseline;
- offline model loading passed;
- malformed-request recovery passed;
- controlled shutdown passed.

An intermediate lifecycle test exposed a real cleanup bug: an invalid shutdown response could reject before terminating the child. Final implementation cleans up the child even when shutdown validation fails.

Interpretation:

- repeated analyze latency improves materially on both independent runners;
- startup/health itself is not faster than one-shot health;
- peak RSS stays close to one-shot, so this is not a material memory win;
- the durable benefit is avoiding repeated model/runtime recreation;
- whole Hugging Face/spaCy cache size/hash is mutable bookkeeping and is not stable model identity.

Decision: **persistent local stdio is the preferred BookNLP runtime transport for repeated analysis.** The one-shot subprocess remains the simple correctness/reference path. Do not add a BookNLP HTTP sidecar merely for model lifetime.

This does **not** change BookNLP model quality/adoption state.

Detailed evidence:

- `docs/experiments/BOOKNLP_SUBPROCESS_RUNTIME_PROOF.md`
- `docs/experiments/BOOKNLP_PERSISTENT_RUNTIME_PROOF.md`
- `docs/v2/LOCAL_LITERARY_PROVIDER_PROTOCOL.md`
- D-032 in `docs/DECISIONS.md`.

## Adoption blockers still in force

- private modern-fiction EPUBs are unavailable to the current execution environment;
- BookNLP model-weight licensing remains unverified;
- BookNLP speaker/event models use LitBank-derived annotations, so LitBank is not an independent product-generalization test;
- no production speaker/event method is adopted;
- event participant correctness remains unmeasured on suitable gold;
- scene quality remains unmeasured on the primary suite.

## Immediate continuation order

1. Return Phase-3 development from runtime plumbing to **new semantic event capability**.
2. Prefer explicit **non-character entity participants** and/or negation/modality/realis over attachment-rule expansion that merely raises character coverage.
3. For any source-neutral/public diagnostic, separate coverage from correctness and do not claim participant quality without suitable gold.
4. When private EPUB access returns, create/score scene/dialogue/event annotations for Harry Potter, The Cruel Prince, Caraval and ACOFAS and use those results for product promotion decisions.
5. Adopt no identity, scene, speaker or event default before private-suite evidence, repeatability, resource cost, failure-mode review and production-compatible licensing.
6. Preserve negative experiments and exact source/model/config/resource fingerprints.
7. Do not use Modal for textual analysis, use Modal accounts outside `modal-03` through `modal-41`, add paid AI dependencies, or deploy Vercel without fresh explicit owner approval.

## References

- Phase 3 tracker: issue #185
- BookNLP provider adapter: PR #210
- public component benchmark: PR #212
- combined speaker challenger: PR #221
- event grounding: PR #222
- event patient audit: PR #223
- one-shot runtime proof: PR #225 / `docs/experiments/BOOKNLP_SUBPROCESS_RUNTIME_PROOF.md`
- persistent runtime proof: PR #227 / `docs/experiments/BOOKNLP_PERSISTENT_RUNTIME_PROOF.md`
- local provider protocol: `docs/v2/LOCAL_LITERARY_PROVIDER_PROTOCOL.md`
- component scorecard: `docs/validation/PHASE_V2_3_COMPONENT_SCORECARD.md`