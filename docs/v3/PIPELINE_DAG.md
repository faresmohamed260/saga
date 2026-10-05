# S.A.G.A. v3 Pipeline DAG

Status: **DRAFT EXECUTION CONTRACT**

This document defines stage dependencies independently from any specific model implementation.

## Stage graph

```text
SOURCE_INGEST
   |
   v
SOURCE_COMPILE
   |
   +--------------------+
   |                    |
   v                    v
QUOTE_BOUNDARIES    SENTENCE_SYNTAX
   |                    |
   +---------+----------+
             v
      SEMANTIC_LEXER
             |
       +-----+------+----------------+
       |            |                |
       v            v                v
 ENTITY_MENTIONS EVENT_MENTIONS LOCAL_OBSERVATIONS
       |            |                |
       v            |                |
 ENTITY_LINKING     |                |
       |            |                |
       +------+-----+                |
              v                      |
        EVENT_PARTICIPANTS <----------+
              |
              v
        EVENT_LINKING
              |
      +-------+---------+----------------+
      |                 |                |
      v                 v                v
 SPEAKER_LINKING   SCENE_BOUNDARIES   ATTRIBUTE/RELATION
      |                 |              OBSERVATIONS
      +----------+------+----------------+
                 v
            NARRATIVE_IR
                 |
        +--------+---------+
        |                  |
        v                  v
   STATE_DELTAS      TEMPORAL_CANDIDATES
        |                  |
        |                  v
        |           TEMPORAL_SCORING
        |                  |
        |                  v
        |           TEMPORAL_SOLVER
        |                  |
        +---------+--------+
                  v
          CAUSAL_CANDIDATES
                  |
                  v
           CAUSAL_SCORING
                  |
                  v
        CANONICALIZATION
                  |
                  v
          CANONICAL_IR
        /      |       \
       v       v        v
    GRAPH    RETRIEVAL  GENERATIVE_VIEWS
```

## Stage contracts

### `SOURCE_INGEST`

Input: source object.

Output: immutable raw source reference.

Invalidated by: source bytes only.

### `SOURCE_COMPILE`

Input: source bytes + normalization version.

Output:

- normalized text;
- structural units;
- offsets;
- source fingerprint.

Invalidated by:

- source bytes;
- normalization/compiler version.

### `QUOTE_BOUNDARIES`

Input: normalized structural source.

Output: deterministic quote units/spans.

Must remain model-independent unless a future challenger proves materially better.

### `SENTENCE_SYNTAX`

Input: sentences.

Output: optional token/POS/dependency evidence.

Provider is replaceable.

### `SEMANTIC_LEXER`

Input: bounded semantic windows plus structure/syntax.

Output:

- entity mentions;
- event mentions;
- explicit attributes;
- local relation candidates;
- semantic labels.

This stage is high-recall and does not assign global canon IDs.

### `ENTITY_LINKING`

Input:

- mentions;
- local context;
- candidate entities/clusters;
- local coreference evidence.

Output:

- entity clusters;
- mention-to-entity links;
- unresolved mentions;
- merge/split evidence.

This stage runs at document scope and later series scope.

### `EVENT_PARTICIPANTS`

Input:

- event mentions;
- entity mentions/links;
- syntax;
- local observations.

Output: typed participant candidates with evidence.

### `EVENT_LINKING`

Input: event mentions and participant/context evidence.

Output: consolidated event clusters plus unresolved event mentions.

### `SPEAKER_LINKING`

Input:

- quote spans;
- local dialogue context;
- resolved character candidates;
- neighboring quote structure.

Output: `SpeakerObservation` records.

### `SCENE_BOUNDARIES`

Input:

- structural source;
- semantic/entity/event continuity features;
- local contextual embeddings/features.

Output: scene-boundary probabilities/candidates and final accepted boundaries.

### `ATTRIBUTE/RELATION_OBSERVATIONS`

Input: semantic candidates plus resolved entities/events.

Output:

- `AttributeObservation`;
- `RelationshipObservation`;
- other typed observations.

### `STATE_DELTAS`

Input:

- accepted/candidate events;
- state observations;
- event roles;
- semantic qualifiers.

Output: candidate state transitions. Persistent state is not directly written by extraction models.

### `TEMPORAL_CANDIDATES`

Input:

- events;
- temporal cues;
- scene/chapter structure;
- event similarity/coreference;
- source order.

Output: sparse candidate event pairs.

No all-pairs scoring.

### `TEMPORAL_SCORING`

Input: candidate event pairs and evidence packet.

Output: pairwise relation probabilities/labels.

### `TEMPORAL_SOLVER`

Input: accepted/candidate temporal constraints.

Output:

- consistent partial chronology;
- contradictions;
- unresolved pairs;
- derived transitive relations where logically valid.

### `CAUSAL_CANDIDATES`

Input:

- temporally compatible events;
- shared participants/entities;
- state prerequisites;
- discourse cues;
- semantic retrieval.

Output: sparse event-pair candidate set.

### `CAUSAL_SCORING`

Input: candidate pair + bounded evidence.

Output: causal relation candidate with confidence and evidence.

### `CANONICALIZATION`

Input: observations, candidate facts, constraints and provenance.

Output: accepted/rejected/unresolved/superseded facts.

Canonicalization is policy, not model output.

## Incremental invalidation

A stage artifact fingerprint is computed from:

```text
source/input artifact fingerprints
+ stage name
+ stage version
+ model/provider artifact fingerprint
+ configuration fingerprint
```

If the fingerprint does not change, the stage is reusable.

Example: replacing the entity linker invalidates:

- entity linking;
- downstream participant entity grounding;
- speaker identity resolution;
- event linking where entity identity is a feature;
- relationships/state/time/causality that depend on those identities.

It does **not** invalidate:

- source ingestion;
- normalization;
- quote boundaries;
- source structural hierarchy;
- semantic mention spans that are model-independent of identity linking.

## Scheduling groups

To minimize model churn and VRAM fragmentation, compatible stage work should be batched across the whole document.

Suggested groups:

1. deterministic source compilation;
2. CPU syntax/lexical passes;
3. semantic lexer batch;
4. global linking batch;
5. dialogue/scene specialist scoring;
6. event/frame specialist scoring;
7. structured-extraction escalation;
8. general reasoning escalation;
9. deterministic temporal/state/canonical solvers.

## Failure semantics

Every stage must distinguish:

- terminal invalid input;
- transient runtime failure;
- successful empty result;
- successful unresolved result;
- partial candidate result requiring escalation.

`unresolved` must never be represented as an infrastructure failure.
