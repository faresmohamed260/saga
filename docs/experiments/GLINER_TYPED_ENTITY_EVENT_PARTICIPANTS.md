# GLiNER Typed World-Entity Event Participant Challenger

Status: **PUBLIC CHALLENGER MEASURED — DO NOT ADOPT FOR CURRENT DIRECT EVENT-PARTICIPANT COVERAGE**

Issue: `#231`

This experiment asks whether a purpose-built typed-span model can improve non-character event-participant evidence without weakening S.A.G.A.'s canonical-character or dependency-grounding rules.

The answer for the pinned GLiNER Small v2.1 configuration is **no** for the current direct event-argument ontology and role policy. GLiNER produces useful typed spans across LitBank, but those spans overlap the direct `nsubj`, `agent -> pobj`, `dobj`, and `nsubjpass` event candidates substantially less often than BookNLP's existing entity evidence.

This is a public coverage/evidence diagnostic. LitBank does not provide S.A.G.A.-style non-character actor/patient gold, so none of the participant counts below are precision, recall, or accuracy measurements.

## Exact evidence

- S.A.G.A. benchmark head: `25e51fe6ea88d18e4d9dfd9c32b2db75f2d34ba3`
- GitHub Actions run: `34767105089`
- job: `103749919389`
- LitBank commit: `3e50db0ffc033d7ccbb94f4d88f6b99210328ed8`
- documents attempted/completed/failed: **`100 / 100 / 0`**
- analysis-worker typecheck: **pass**
- model-light tests: **`160 / 160` pass**, up from the pre-GLiNER `153 / 153` floor
- semantic report fingerprint: `322b3e51561acf51a68bd6567170d5928abe62f2aed79d3d68cd4158ede2bfdd`
- aggregate artifact ID: `10320402913`
- aggregate artifact digest: `sha256:a20e650f02426bf99114e295cedaaea85cc660e756aac1209e11ff2b7da0ebfd`
- artifact size: `42,767` bytes

The uploaded artifact contains aggregate/runtime evidence only. Per-document raw GLiNER span outputs were removed before upload so the artifact does not become a source-text corpus.

## Pinned challenger

GLiNER code:

- repository: `urchade/GLiNER`
- commit: `cf9e5f7d9fb99158b592132a9ec7cbfabb43a9a0`
- package version at that commit: `0.2.29`
- license: `Apache-2.0`

Model:

- repository: `urchade/gliner_small-v2.1`
- revision: `f23104c107e3c57f5c7aa36d53a9667c67b4b866`
- license: `Apache-2.0`
- model artifacts: **`610,657,698` bytes**

Fixed configuration:

- labels: `person`, `location`, `facility`, `geopolitical entity`, `organization`, `vehicle`
- threshold: `0.5`
- deterministic character window: `1,400` code points
- overlap: `180` code points
- configured batch size: `12`

The experiment does **not** change the threshold or ontology after observing the result. Any such change is a new experiment.

## Provenance separation

BookNLP remains the source of:

- event triggers;
- dependency syntax;
- the existing canonical-character participant path.

GLiNER supplies **typed entity spans only**. The S.A.G.A. composition layer retains this separation explicitly; it does not construct a mixed evidence object that falsely claims one provider produced everything.

Provider labels and clusters are evidence only. They do not mint canonical characters or canonical world entities.

## Runtime/resource evidence

CPU-only full-corpus run:

- model download: `3.845 s`
- model initialization: `3.280 s`
- GLiNER inference wall clock: **`381.955 s`**
- process peak resident memory: **`1,581.84 MiB`**
- model artifacts: **`610,657,698 bytes`** (~`582.37 MiB`)
- GPU/VRAM: none

The workflow also captured an independent GNU `time -v` peak-RSS measurement in artifact `10320402913`. The process-level `resource.getrusage` value above is the directly surfaced measured peak and is the value used here rather than guessing the independent value from an opaque artifact.

For context only, the older stale GLiNER + F-Coref identity experiment had much higher memory use because it included F-Coref. Those old combined resource numbers are **not** used as the GLiNER-only baseline.

## Whole-corpus GLiNER detections

Before event-role intersection, GLiNER emitted:

| Label | Detections |
| --- | ---: |
| person | 4,514 |
| location | 1,008 |
| organization | 187 |
| vehicle | 126 |
| facility | 89 |
| geopolitical entity | 31 |

These global counts show that GLiNER is not simply failing to detect entities. The weak result below is specifically about overlap with S.A.G.A.'s current direct event-participant candidate positions and ontology.

## Event-participant comparison

The scorer reuses exactly the same BookNLP trigger/syntax artifact and the same S.A.G.A. oracle-identity/event-grounding path used by the BookNLP typed-entity diagnostic.

Candidate denominators remained identical:

- direct actor/patient candidate tokens: **`6,701`**
- candidate events: **`5,085`**
- actor candidates: `4,155`
- patient candidates: `2,546`

Dependency-path distribution remained:

- `nsubj`: `4,066`
- `dobj`: `2,304`
- `nsubjpass`: `242`
- `agent -> pobj`: `89`

### Coverage

| Metric | GLiNER | BookNLP baseline | Delta |
| --- | ---: | ---: | ---: |
| clean typed non-character candidate tokens | `47 / 6,701` (**0.70%**) | `146 / 6,701` (**2.18%**) | **-1.48 pp** |
| candidate events gaining typed evidence | `44 / 5,085` (**0.87%**) | `142 / 5,085` (**2.79%**) | **-1.93 pp** |
| relative candidate coverage | **0.322x** BookNLP | `1.000x` | — |
| relative event gain | **0.310x** BookNLP | `1.000x` | — |

GLiNER therefore retains only about `32%` of BookNLP's candidate-token coverage and `31%` of its event-level gain for this narrow role contract.

### GLiNER candidate status

Across the same `6,701` candidates:

- already grounded canonical character: `4,265`
- clean typed non-character: **`47`**
- ambiguous typed non-character: `0`
- malformed typed non-character: `0`
- structural-locator mismatch: `0`
- GLiNER person-only evidence: `16`
- unknown-only evidence: `0`
- no GLiNER entity evidence at the candidate token: `2,373`

### Grounded non-character categories

- location: `18`
- vehicle: `18`
- organization: `7`
- facility: `4`
- geopolitical: `0`

By role:

- patient/location: `15`
- patient/vehicle: `13`
- patient/facility: `3`
- patient/organization: `3`
- actor/vehicle: `5`
- actor/organization: `4`
- actor/location: `3`
- actor/facility: `1`

## Trigger regression guard

The entity-provider swap did not alter the event-trigger path.

- previous public trigger F1: `0.7791`
- current full-precision F1: `0.7791290702236171`
- full-precision delta: `+0.0000290702`
- rounded public P/R/F1 remains `0.8003 / 0.7591 / 0.7791`

Interpretation: **no measured trigger regression**. The microscopic full-precision difference versus the stored four-decimal value is rounding, not an improvement claim.

## Decision

For the current six-label ontology and direct dependency-role policy:

1. **Do not adopt GLiNER as the world-entity event-participant provider.** It is materially below BookNLP's already sparse public coverage baseline.
2. **Do not tune the threshold after seeing this result** and present that as the same experiment.
3. **Do not enable dative expansion, conjunction inheritance, provider clusters, or looser structural matching** merely to improve the coverage number.
4. Preserve the provider-neutral typed-entity source contract and GLiNER normalizer; they are useful infrastructure for later typed-span experiments.
5. Treat GLiNER's Apache-2.0 code/model licensing as a production-compatibility advantage only. It does not override the quality and private-corpus qualification gates.
6. BookNLP remains the stronger measured provider for this narrow public coverage diagnostic, but its model-weight license remains unverified and therefore still blocks production adoption.
7. A future ontology expansion (`artifact`, `object`, factions/groups, creatures/species, etc.) must be a separate explicit architecture/benchmark decision. These classes must not be silently mapped into the current labels to make this benchmark look better.

## Adoption status

**No production adoption change.**

The private modern-fiction suite remains unavailable in the current execution environment, and participant correctness remains unmeasured on suitable gold. This experiment therefore narrows the search space rather than promoting a model.
