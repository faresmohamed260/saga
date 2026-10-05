# S.A.G.A. v3 Canonical Persistence Draft

Status: **DRAFT LOGICAL SCHEMA — NO MIGRATION APPLIED**

PostgreSQL/Supabase is the intended canonical persistence layer for Narrative IR. Neo4j/vector stores/generated summaries are derived materializations and must be reconstructible.

This document is a logical schema. Physical indexes, partitioning and migration names are deliberately deferred until prototype cardinalities are measured.

## Design rules

1. Source/evidence records are immutable.
2. Semantic runs are append-only/versioned where practical.
3. Canonical identities use S.A.G.A. IDs, never provider IDs.
4. Candidate and accepted semantics remain distinct.
5. Every model-produced semantic record has run/stage/config provenance.
6. Series-level resolution must not erase document-level evidence.
7. Derived views can be rebuilt from canonical data.

## Source tables

### `narrative_documents`

- `id uuid pk`
- `project_id uuid`
- `series_id uuid null`
- `source_object_id uuid/text`
- `source_fingerprint text unique within source scope`
- `normalization_version text`
- `title text null`
- `volume_index int null`
- `created_at timestamptz`

### `narrative_source_units`

- `id uuid pk`
- `document_id uuid fk`
- `parent_id uuid null fk self`
- `kind text`
- `ordinal bigint`
- `start_offset bigint`
- `end_offset bigint`
- `structural_fingerprint text`

Expected kinds: chapter, section, paragraph, sentence, quote.

### `narrative_source_spans`

- `id uuid pk`
- `document_id uuid fk`
- `source_unit_id uuid null fk`
- `start_offset bigint`
- `end_offset bigint`
- `text_fingerprint text`

## Run/provenance tables

### `narrative_analysis_runs`

- `id uuid pk`
- `document_id uuid fk`
- `architecture_version text`
- `pipeline_fingerprint text`
- `status text`
- `started_at timestamptz`
- `completed_at timestamptz null`

### `narrative_stage_runs`

- `id uuid pk`
- `analysis_run_id uuid fk`
- `stage_name text`
- `stage_version text`
- `producer_kind text`
- `producer_name text`
- `producer_version text`
- `model_artifact_fingerprint text null`
- `configuration_fingerprint text`
- `input_artifact_fingerprint text`
- `output_artifact_fingerprint text`
- `status text`
- `metrics jsonb`
- `started_at timestamptz`
- `completed_at timestamptz null`

Unique candidate key:

`(analysis_run_id, stage_name, output_artifact_fingerprint)`

## Entity layer

### `narrative_mentions`

- `id uuid pk`
- `document_id uuid fk`
- `source_span_id uuid fk`
- `mention_type text`
- `surface_form text`
- `normalized_form text null`
- `producer_stage_run_id uuid fk`
- `status text`
- `confidence real null`

### `narrative_entities`

- `id uuid pk`
- `project_id uuid`
- `series_id uuid null`
- `document_id uuid null`
- `scope text`
- `entity_type text`
- `canonical_label text`
- `status text`
- `created_by_stage_run_id uuid null`
- `created_at timestamptz`

### `narrative_mention_entity_links`

- `mention_id uuid fk`
- `entity_id uuid fk`
- `stage_run_id uuid fk`
- `decision text`
- `score real null`
- `rank int null`
- `reason jsonb null`

Primary/unique strategy should permit multiple historical candidate links while one current accepted link is selected by policy.

### `narrative_entity_aliases`

- `id uuid pk`
- `entity_id uuid fk`
- `alias text`
- `alias_kind text`
- `support jsonb`
- `status text`

## Proposition/observation layer

### `narrative_propositions`

- `id uuid pk`
- `document_id uuid fk`
- `predicate text`
- `arguments jsonb`
- `polarity text`
- `modality text`
- `epistemic_status text`
- `confidence real null`
- `producer_stage_run_id uuid fk`
- `status text`

### `narrative_proposition_evidence`

- `proposition_id uuid fk`
- `source_span_id uuid fk`
- `evidence_role text`

## Event layer

### `narrative_event_mentions`

- `id uuid pk`
- `document_id uuid fk`
- `trigger_span_id uuid null fk`
- `event_type text null`
- `polarity text`
- `modality text`
- `realis_status text`
- `source_sequence bigint`
- `producer_stage_run_id uuid fk`
- `confidence real null`

### `narrative_event_mention_evidence`

- `event_mention_id uuid fk`
- `source_span_id uuid fk`
- `evidence_role text`

### `narrative_events`

- `id uuid pk`
- `project_id uuid`
- `document_id uuid null`
- `series_id uuid null`
- `event_type text`
- `status text`
- `salience real null`
- `kernel_event_score real null`
- `created_by_stage_run_id uuid fk`

### `narrative_event_links`

- `event_mention_id uuid fk`
- `event_id uuid fk`
- `stage_run_id uuid fk`
- `decision text`
- `score real null`

### `narrative_event_participants`

- `id uuid pk`
- `event_mention_id uuid null fk`
- `event_id uuid null fk`
- `role text`
- `mention_id uuid null fk`
- `entity_id uuid null fk`
- `confidence real null`
- `producer_stage_run_id uuid fk`

### `narrative_event_participant_evidence`

- `participant_id uuid fk`
- `source_span_id uuid fk`

## Dialogue

### `narrative_speaker_observations`

- `id uuid pk`
- `quote_source_unit_id uuid fk`
- `speaker_entity_id uuid null fk`
- `candidate_entities jsonb`
- `confidence real null`
- `status text`
- `producer_stage_run_id uuid fk`

## Attributes and relationships

### `narrative_attribute_observations`

- `id uuid pk`
- `subject_entity_id uuid fk`
- `attribute text`
- `value jsonb`
- `observation_kind text`
- `confidence real null`
- `status text`
- `producer_stage_run_id uuid fk`

### `narrative_relationship_observations`

- `id uuid pk`
- `subject_entity_id uuid fk`
- `object_entity_id uuid fk`
- `predicate text`
- `directionality text`
- `polarity text`
- `confidence real null`
- `status text`
- `producer_stage_run_id uuid fk`

### `narrative_relationship_states`

- `id uuid pk`
- `subject_entity_id uuid fk`
- `object_entity_id uuid fk`
- `relationship_type text`
- `valid_from_event_id uuid null fk`
- `valid_to_event_id uuid null fk`
- `confidence real`
- `status text`
- `policy_version text`

## State

### `narrative_state_observations`

- `id uuid pk`
- `subject_entity_id uuid fk`
- `predicate text`
- `value jsonb`
- `polarity text`
- `modality text`
- `confidence real null`
- `status text`
- `producer_stage_run_id uuid fk`

### `narrative_state_deltas`

- `id uuid pk`
- `subject_entity_id uuid fk`
- `predicate text`
- `from_value jsonb null`
- `to_value jsonb`
- `causing_event_id uuid null fk`
- `valid_from_event_id uuid null fk`
- `valid_to_event_id uuid null fk`
- `status text`
- `policy_version text`

## Temporal layer

### `narrative_temporal_constraints`

- `id uuid pk`
- `left_event_id uuid fk`
- `relation text`
- `right_event_id uuid fk`
- `confidence real null`
- `status text`
- `producer_stage_run_id uuid fk`

### `narrative_temporal_solutions`

- `id uuid pk`
- `analysis_run_id uuid fk`
- `solver_version text`
- `solution_fingerprint text`
- `contradictions jsonb`
- `metrics jsonb`

Derived pair/order materializations should reference this solution rather than overwrite original constraints.

## Causal layer

### `narrative_causal_candidates`

- `id uuid pk`
- `source_event_id uuid fk`
- `target_event_id uuid fk`
- `relation text`
- `candidate_generation_reason jsonb`
- `confidence real null`
- `status text`
- `producer_stage_run_id uuid fk`

## Canonical facts

### `narrative_facts`

- `id uuid pk`
- `project_id uuid`
- `fact_type text`
- `subject_ref jsonb`
- `predicate text`
- `object_value jsonb`
- `valid_from_event_id uuid null fk`
- `valid_to_event_id uuid null fk`
- `confidence real`
- `acceptance_policy_version text`
- `status text`
- `created_at timestamptz`

### `narrative_fact_support`

- `fact_id uuid fk`
- `support_kind text`
- `support_id uuid`
- `weight real null`

Application code must validate support kind/reference consistency.

## Review/training data

### `narrative_reviews`

- `id uuid pk`
- `reviewer_id uuid`
- `task_type text`
- `target_kind text`
- `target_id uuid`
- `decision text`
- `correction jsonb null`
- `created_at timestamptz`

### `narrative_training_examples`

Prefer a generated/materialized export rather than duplicating all source text in the primary schema. Training exports must preserve source license/privacy boundaries.

## Evidence attachment

Typed semantic records should use explicit join tables to `narrative_source_spans` rather than embedding unvalidated offsets in JSON.

## RLS/security

All narrative tables inherit the owning project/book access boundary. Service-worker write operations require scoped server credentials; client reads remain owner-authorized through RLS-safe views/RPCs.

## Neo4j projection rule

Neo4j node/edge identifiers must contain the canonical Postgres IR IDs. Deleting the graph database and rebuilding it from these tables must be a supported operation.

## Migration constraint

Do not create these tables on `main` during preparation. Physical migration begins only after the v3 prototype demonstrates the minimum quality gate and the names/cardinalities are reviewed against measured artifacts.
