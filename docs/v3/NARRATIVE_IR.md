# S.A.G.A. v3 Narrative Intermediate Representation

Status: **DRAFT v0 — REBOOT BLOCKER**

The Narrative IR is the canonical semantic contract of S.A.G.A. v3. Models, heuristics and external providers may propose evidence, but they do not define the product ontology and they do not directly become canon.

## Design goals

The IR must support:

- exact source provenance;
- book- and series-scale identity;
- multiple mentions of the same entity/event;
- uncertainty and unresolved states;
- observations separate from accepted facts;
- narrative order separate from story-world time;
- event-sourced character/world state;
- derived graph projections;
- deterministic recomputation;
- model replacement without schema replacement.

## Core invariants

1. Every semantic object that claims support from the text references one or more `SourceSpan` records.
2. Provider/model IDs are never canonical IDs.
3. A `Mention` is not an `Entity`.
4. An `EventMention` is not an `Event`.
5. An `Observation` is not automatically an accepted `Fact`.
6. Narrative/source order is not equivalent to story-world chronology.
7. Derived summaries/descriptions are views over accepted evidence, not canonical evidence themselves.
8. Unknown/unresolved is a valid result and must not be converted into guessed canon.

## Structural primitives

### `Document`

A normalized source work or volume.

Required fields:

- `document_id`
- `series_id?`
- `source_object_id`
- `source_fingerprint`
- `normalization_version`
- `title?`
- `volume_index?`

### `SourceUnit`

A hierarchical structural unit.

Kinds:

- `chapter`
- `section`
- `paragraph`
- `sentence`
- `quote`

Required fields:

- `source_unit_id`
- `document_id`
- `parent_id?`
- `kind`
- `ordinal`
- `start_offset`
- `end_offset`
- `structural_fingerprint`

### `SourceSpan`

The smallest universal provenance pointer.

Required fields:

- `source_span_id`
- `document_id`
- `start_offset`
- `end_offset`
- `source_unit_id?`
- `text_fingerprint`

Offsets refer to the canonical normalized source text.

## Referential primitives

### `Mention`

A textual reference to something in the story world.

Examples:

- `Feyre`
- `she`
- `the High Lady`
- `the sword`
- `the city`

Required fields:

- `mention_id`
- `source_span_id`
- `mention_type`
- `surface_form`
- `normalized_form?`
- `candidate_entity_ids[]`
- `resolution_status`
- `confidence?`

`mention_type` is a semantic hint, not canon.

### `Entity`

A globally resolved story-world identity.

Kinds include:

- `character`
- `location`
- `object`
- `organization`
- `faction`
- `creature`
- `concept`
- `other`

Required fields:

- `entity_id`
- `scope` (`document` or `series`)
- `entity_type`
- `canonical_label`
- `status`
- `created_from_evidence[]`

Optional fields:

- `aliases[]`
- `parent_entity_id?`
- `external_keys?`

Canonical labels are presentation labels and may change without changing `entity_id`.

## Proposition and observation layer

### `Proposition`

An atomic interpretation anchored in text.

Examples:

- Feyre has blue-grey eyes.
- Rhys is in Velaris.
- Nesta distrusts Cassian.

Required fields:

- `proposition_id`
- `predicate`
- `arguments`
- `evidence_span_ids[]`
- `polarity`
- `modality`
- `epistemic_status`
- `producer_run_id`
- `confidence?`

A proposition may remain unresolved or be rejected.

### `Observation`

A typed proposition suitable for downstream aggregation.

Observation families:

- `attribute`
- `relationship`
- `state`
- `event_participant`
- `temporal`
- `causal`
- `speaker`

All observations inherit provenance and uncertainty from their source proposition(s).

## Event layer

### `EventMention`

A text-local expression of an occurrence.

Required fields:

- `event_mention_id`
- `trigger_span_id?`
- `support_span_ids[]`
- `event_type?`
- `participants[]`
- `polarity`
- `modality`
- `realis_status`
- `source_sequence`
- `producer_run_id`

### `Participant`

Typed role attached to an event mention or consolidated event.

Initial roles:

- `actor`
- `patient`
- `recipient`
- `experiencer`
- `instrument`
- `location`
- `source`
- `destination`
- `possessor`
- `other`

Fields:

- `participant_id`
- `role`
- `mention_id?`
- `entity_id?`
- `evidence_span_ids[]`
- `confidence?`

### `Event`

A story-world occurrence consolidating one or more event mentions.

Required fields:

- `event_id`
- `event_type`
- `event_mention_ids[]`
- `participant_entity_ids[]`
- `status`

Optional fields:

- `salience`
- `kernel_event_score`
- `temporal_anchor_id?`

Consolidation must never erase the original mentions.

## Character/world state

### `StateObservation`

A source-supported statement about state.

Fields:

- `state_observation_id`
- `subject_entity_id`
- `predicate`
- `value`
- `evidence_span_ids[]`
- `polarity`
- `modality`
- `confidence?`

### `StateDelta`

An interpreted change caused or implied by an event.

Fields:

- `state_delta_id`
- `subject_entity_id`
- `predicate`
- `from_value?`
- `to_value`
- `causing_event_id?`
- `evidence_span_ids[]`
- `story_time_interval?`
- `status`

Persistent/current state is computed from accepted deltas and constraints rather than written directly by extraction models.

## Attribute and trait layer

### `AttributeObservation`

A direct or inferred descriptor.

Examples:

- eye color
- hair color
- occupation
- title
- temperament evidence

Fields:

- `attribute_observation_id`
- `subject_entity_id`
- `attribute`
- `value`
- `evidence_span_ids[]`
- `observation_kind` (`explicit`, `behavioral`, `reported`, `inferred`)
- `confidence?`

Stable traits are derived from multiple observations and counterevidence; they are not blindly copied from one passage.

## Relationship layer

### `RelationshipObservation`

A single source-supported relation signal between entities.

Fields:

- `relationship_observation_id`
- `subject_entity_id`
- `object_entity_id`
- `predicate`
- `directionality`
- `evidence_span_ids[]`
- `polarity`
- `confidence?`

### `RelationshipState`

A derived time-aware interpretation over observations.

Fields:

- `relationship_state_id`
- `subject_entity_id`
- `object_entity_id`
- `relationship_type`
- `valid_from?`
- `valid_to?`
- `supporting_observation_ids[]`
- `confidence`

## Time

### `NarrativePosition`

Deterministic position in the source.

Represented through document/unit ordinals and offsets.

### `TemporalConstraint`

A partial-order or interval relation.

Supported relations begin with:

- `before`
- `after`
- `during`
- `contains`
- `overlaps`
- `simultaneous`
- `starts`
- `finishes`
- `unknown`

Fields:

- `temporal_constraint_id`
- `left_event_id`
- `relation`
- `right_event_id`
- `evidence_span_ids[]`
- `confidence?`
- `status`

Canonical chronology is solved from accepted constraints; it is not a generated list.

## Causality

### `CausalCandidate`

A candidate causal relation between accepted or candidate events.

Relations may include:

- `causes`
- `enables`
- `prevents`
- `motivates`
- `contributes_to`
- `consequence_of`
- `unknown`

Fields:

- `causal_candidate_id`
- `source_event_id`
- `target_event_id`
- `relation`
- `candidate_generation_reason[]`
- `evidence_span_ids[]`
- `confidence?`
- `status`

## Dialogue

### `SpeakerObservation`

Fields:

- `speaker_observation_id`
- `quote_source_unit_id`
- `speaker_entity_id?`
- `candidate_entity_ids[]`
- `evidence_span_ids[]`
- `confidence?`
- `status`

The quote span remains structural source truth; speaker identity is semantic interpretation.

## Canonicalization

### `Fact`

A fact is an accepted semantic interpretation supported by one or more propositions/observations.

Fields:

- `fact_id`
- `fact_type`
- `subject`
- `predicate`
- `object/value`
- `support_ids[]`
- `valid_from?`
- `valid_to?`
- `confidence`
- `acceptance_policy_version`
- `status`

Possible statuses:

- `candidate`
- `accepted`
- `rejected`
- `unresolved`
- `superseded`
- `contradicted`

## Provenance fields shared by semantic records

Every model-produced record must be traceable to:

- `analysis_run_id`
- `stage_name`
- `stage_version`
- `producer_kind`
- `producer_name`
- `producer_version`
- `model_artifact_fingerprint?`
- `configuration_fingerprint`
- `input_artifact_fingerprint`
- `created_at`

## Derived views that must not become canonical source

The following are generated from the IR and can always be rebuilt:

- character profiles/descriptions;
- relationship summaries;
- chapter/scene summaries;
- timelines rendered as ordered lists;
- graph visualizations;
- character arcs;
- themes/tension summaries;
- image-generation prompts;
- retrieval documents/embeddings;
- Neo4j projections.

## Open design questions for v0 -> v1

- whether `Proposition` should be a stored first-class table or represented through typed observations;
- exact series-level entity promotion rules;
- event-role ontology depth;
- ontology for fictional species/powers/abilities;
- fact contradiction representation;
- how alternate timelines/dreams/hypotheticals are scoped;
- whether narrator beliefs and quoted-character beliefs need separate epistemic contexts.

These questions do not block initial v3 prototyping, but they must be resolved before the IR is declared stable.
