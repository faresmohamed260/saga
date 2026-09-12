# Event Candidate / Participant Benchmark Protocol

Status: **ACTIVE PHASE-3 EXPERIMENT CONTRACT**

## Purpose

This benchmark establishes the provider-neutral event-trigger and participant-grounding measurement layer required before S.A.G.A. adopts an event evidence provider.

The current repository slice is intentionally source-neutral so work can continue while the private primary-fiction EPUBs are unavailable. It does **not** establish production quality. Harry Potter, The Cruel Prince, Caraval and ACOTAR remain the product-promotion gate.

## Product boundary

An event candidate is source-grounded evidence that something narratively relevant may have happened. It is not yet a final canonical event, causal edge, state transition or timeline fact.

The benchmark keeps two questions separate:

1. did a provider identify the correct event trigger span?;
2. did it ground the correct canonical character participants and roles?

Provider output remains evidence. Later deterministic S.A.G.A. policy and higher narrative layers decide whether candidates are accepted, consolidated, assigned modality/realis, linked to state changes, or used in causal/timeline graphs.

## Reference representation

`saga-event-reference-v1` stores no source prose. Each gold event records:

- source SHA-256 and normalized-input fingerprint;
- section stable key;
- exact absolute Unicode code-point trigger offsets;
- annotation protocol version;
- participant status: `known` or `unknown`;
- canonical character keys with coarse roles (`actor`, `patient`, `other`) only when participant status is `known`.

Unknown participants are intentionally unscored rather than converted into fake negative labels.

When private EPUBs are available, annotations should deliberately cover:

- explicit physical actions;
- transfers/possession changes;
- arrivals/departures and movement;
- attacks/injuries/deaths;
- discoveries and revelations;
- speech acts when they matter as events;
- stative or mental predicates that should **not** automatically become atomic events;
- negated/hypothetical/conditional actions;
- repeated descriptions of the same event;
- events with omitted or implicit participants;
- events involving multiple characters or non-character entities;
- event mentions inside dialogue versus narration.

## Metrics

### Trigger detection

Exact trigger-span precision, recall and F1 are primary. A prediction matches only when section key and absolute start/end offsets exactly match the reference.

The evaluator additionally reports:

- duplicate prediction count/rate;
- unsupported prediction count/rate.

Multiple predictions at the same exact trigger span are visible as duplicate false positives rather than silently collapsed into perfect precision.

### Participant grounding

For exact matched triggers with known participant gold, compare `(role, canonicalCharacterKey)` pairs and report participant precision, recall and F1.

A missed event trigger also contributes false-negative participants for known gold, so participant recall remains end-to-end rather than rewarding only the easiest detected events.

For matched triggers whose participant gold is unknown, predicted participants are reported as unscored assignments.

## Tier-0 lexical event floor

The first implementation is deliberately weaker than the contract's eventual dependency-aware baseline. It is named and documented as a **dependency-free lexical floor** so benchmark infrastructure can be qualified without pretending that a hand-written lexicon solves literary event extraction.

It:

- matches a small configurable set of high-confidence inflected event verbs;
- anchors each trigger exactly to normalized source offsets;
- attaches at most one preceding canonical character as coarse `actor` and one following canonical character as coarse `patient`;
- requires participant mentions to remain within a bounded context and not cross sentence-ending punctuation;
- consumes already-resolved S.A.G.A. character evidence and never mints identities;
- disables pronoun participants by default;
- records a configuration fingerprint and deterministic output fingerprint.

The initial lexicon intentionally emphasizes overt actions such as `grabbed`, `entered`, `attacked`, `opened`, `killed`, `returned`, `took`, etc. High recall is **not** expected. The floor exists to prove exact evidence contracts, evaluation behavior and contamination visibility.

Known limitations include:

- no POS/dependency parser;
- no lemmatization beyond configured forms;
- no negation/modality/realis handling;
- no multiword event triggers;
- actor/patient roles inferred only from coarse local order;
- no non-character participant grounding yet;
- no event consolidation across mentions;
- no distinction between narratively central and incidental actions.

These limitations are benchmark targets, not hidden implementation details.

## Planned challengers

1. dependency/POS-aware deterministic or lightweight-local event candidate extraction;
2. BookNLP literary event triggers normalized to the same provider-neutral contract;
3. combined candidate pass with deterministic deduplication and participant grounding;
4. bounded local schema-constrained normalization only for surviving candidates if cheaper methods leave a measured gap.

Later work may extend annotation/evaluation to modality/realis, non-character participants, event consolidation and state-change support, but those fields should be added only when the product contract and measurements justify them.

## Promotion rule

No event method can become the production default from synthetic tests, the lexical floor, LitBank/public benchmarks, published BookNLP metrics, or one private excerpt.

Promotion requires:

1. deterministic merge-gate tests pass;
2. exact source/model/config fingerprints are retained;
3. primary-suite event/participant annotations exist;
4. trigger precision/recall, participant grounding, duplicate rate and unsupported-event rate are reviewed together;
5. modality/realis failure modes are measured before canonical event persistence depends on them;
6. whole-book runtime/RAM/VRAM/model-size/license evidence is recorded where applicable;
7. repeatability is demonstrated;
8. chosen software/model licensing is production-compatible.

The private modern-fiction suite governs product promotion if it disagrees with public benchmark evidence.

## Architecture boundaries

- no paid AI API is required;
- no Modal textual inference is permitted;
- provider output remains evidence, not canonical event truth;
- canonical character participant keys come from the S.A.G.A. resolved identity layer;
- exact source offsets remain immutable anchors;
- no causal graph, state ledger or timeline relation is inferred merely because a trigger candidate exists;
- dependency/model challengers remain replaceable behind the same benchmark contract.

Tracks #203 and parent Phase-3 tracker #185.
