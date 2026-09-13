# BookNLP Event Semantic Qualifier Diagnostic

Status: **PUBLIC SOURCE-GROUNDED QUALIFIER SLICE COMPLETE — PREVALENCE ONLY, NO FACTUALITY ADOPTION**

Tracks issue #233 and parent #185.

## Question

Can S.A.G.A. add a conservative event-level evidence layer for explicit negation, modal auxiliaries and irrealis cues using the already-preserved BookNLP trigger/dependency evidence, without changing trigger or participant policy and without introducing another model?

## Policy

Implementation version:

`saga-event-semantic-qualifier-v1`

The layer is separate from canonical event truth. For each validated BookNLP event trigger it requires exact trigger/syntax agreement and follows only same-sentence direct dependency edges.

### Negation

An event is marked `negated` only when an explicit `neg` dependency cue is attached directly to the trigger or to one of its direct auxiliaries.

Absence of such a cue remains `undetermined`; it is not interpreted as positive polarity.

### Modality

An event is marked `modalized` only when a direct `aux` / `auxpass` token has a lemma in the pinned modal set:

- `can`
- `could`
- `may`
- `might`
- `must`
- `shall`
- `should`
- `will`
- `would`

The source syntax token remains attached as evidence. The layer does not convert modal words into unsupported certainty scores.

### Realis / irrealis

The first policy emits `irrealis_cued` only when positive evidence exists:

- a pinned modal auxiliary; or
- a direct `mark` dependency with lemma `if` or `unless`.

Everything else remains `undetermined`.

This is deliberately **not** a complete factuality system. It does not yet claim support for counterfactual scope, reported belief, desire/intention, questions, future interpretation, nested modality, or discourse-level factuality.

## Evidence run

Exact implementation/scorer head:

`6fe886f89a2f3dc9a3ba942077993928e7417fa6`

GitHub Actions:

- run: `34769179181`
- job: `103755506965`
- LitBank commit: `3e50db0ffc033d7ccbb94f4d88f6b99210328ed8`
- attempted/completed/failed: **`100 / 100 / 0`**
- typecheck: **pass**
- analysis-worker tests: **`168 / 168` pass**, up from `160 / 160` before this qualifier contract
- new model inference: **none**
- preserved BookNLP source run: `34727310506`
- preserved source artifact SHA256: `006875873bd58ec53cc976a46d000313107228f4d4dbf6c5dc450cf9b7ba4f6a`

The test-count increase is regression/contract coverage only. It is not a model-quality improvement.

## Trigger regression gate

The event trigger population and public-gold score are unchanged:

- predicted triggers: **`7,445`**
- trigger precision: `0.8002686367`
- trigger recall: `0.7590775895`
- trigger F1: `0.7791290702` = **`0.7791` rounded**
- trigger-count delta versus the established baseline: **`0`**

The qualifier layer therefore changes neither event-trigger quality nor the trigger denominator.

## Qualifier prevalence

Across `7,445` BookNLP event triggers:

| Diagnostic | Count | Rate |
| --- | ---: | ---: |
| events with any explicit qualifier cue | **53** | **0.71%** |
| explicit negation | **3** | **0.04%** |
| modalized | **45** | **0.60%** |
| explicit conditional cue | **5** | **0.07%** |
| irrealis-cued | **50** | **0.67%** |
| unmarked / undetermined | **7,392** | **99.29%** |

No overlap appeared in this public corpus between the measured categories:

- negated + modalized: `0`
- negated + conditional: `0`
- modalized + conditional: `0`
- all three: `0`

### Modal evidence

The 45 modal cues were:

- `could`: `24`
- `can`: `11`
- `will`: `5`
- `must`: `4`
- `shall`: `1`

The first run produced no direct-role event cues for `may`, `might`, `should`, or `would` under the strict dependency policy.

### Conditional evidence

- `if`: `5`
- `unless`: `0`

## Reproducibility record

Report fingerprint:

`051c172829a3864d4c9e295a6672d7fd31f6a9f5f7d5f6ba01109899a16ef803`

Aggregate artifact:

- ID: `10321247725`
- digest: `sha256:ea7e41f8282d2f46641af5ca54ca83c2f77f9e9ab4a265153f4c4d5e44d9507a`
- size: `24,889` bytes

The uploaded artifact contains aggregate/per-document diagnostic counts and fingerprints only; it does not upload raw novel text or raw span dumps.

## Interpretation

The first qualifier layer succeeds at its intended architectural goal: S.A.G.A. can carry explicit, source-anchored polarity/modality/irrealis evidence separately from event identity and participant grounding without another model call.

The public prevalence is **extremely sparse**. Only `0.71%` of BookNLP triggers receive any cue under the first strict policy. This must not be misread as evidence that the other `99.29%` of events are factual, positive, certain or realis. They are simply **undetermined by this evidence layer**.

The `3` negated events are especially too few to treat this policy as complete negation coverage. Before broadening the rule, any next step should audit dependency/failure modes or add suitable factuality annotations; it should not loosen scope merely to increase percentages.

LitBank supplies event-trigger gold but no S.A.G.A.-style polarity/modality/realis gold. Therefore the counts above are **prevalence/coverage diagnostics, not precision, recall, accuracy or factuality correctness**.

## Decision

- Keep the provider-neutral semantic qualifier evidence contract.
- Keep the strict source/syntax validation and `undetermined` default.
- Do **not** promote this layer to a complete event-factuality classifier.
- Do **not** change trigger or participant adoption decisions.
- Do **not** infer positive polarity or realis from missing cues.
- Do **not** broaden dependency scope post hoc without a measured failure-mode audit or suitable gold.
- Private modern-fiction qualification remains required before any production semantic/factuality adoption.
