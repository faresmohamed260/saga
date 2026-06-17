# S.A.G.A. Target System And Roadmap

This document is the locked-in target for S.A.G.A.

It defines:
- what the system is ultimately supposed to produce
- what parts of that target already exist
- what remains to be built
- how to evaluate progress without losing sight of the end goal

## Mission

S.A.G.A. is being built as a canon-aware narrative intelligence system.

The long-term goal is not only to analyze books, but to support:
- canon reconstruction
- point-in-time querying
- divergence planning
- mid-canon rewriting
- grounded outline generation
- future canon-aware story authoring

The system must be able to:
- locate an event in canon
- reconstruct what was true at that point
- identify what later canon depends on that event
- lock all canon before a divergence
- mark downstream canon as stable, unstable, or invalidated
- generate a grounded replacement outline that respects locked canon facts

## Locked-In Design Principles

- deterministic methods should handle as much low-level extraction as possible
- LLMs should be used mainly for semantic judgment and refinement
- tool/function-constrained LLM behavior is preferred over raw schema prompting
- code owns the output schema
- local evidence is treated as evidence, not truth
- stable outputs matter more than clever one-off behavior
- the existing stable system should be evolved incrementally, not rewritten recklessly

## Ideal Output Families

These are the output families S.A.G.A. should produce after analysis completes.

### 1. Event Ledger

Purpose:
- represent what happened in canonical story order
- provide stable anchors for querying, causality, and divergence

Each event should ideally include:
- `event_id`
- `title`
- `summary`
- `book_index`
- `chapter_index`
- `scene_index`
- `participants`
- `location`
- `time_signals`
- `preconditions`
- `direct_consequences`
- `causal_parents`
- `causal_children`
- `stakes`
- `tags`

### 2. Character Profiles

Purpose:
- provide durable identity and state for writing and reasoning

Each profile should ideally include:
- `character_id`
- `canonical_name`
- `aliases`
- `core_description`
- `traits`
- `personality`
- `speech_style`
- `goals`
- `fears`
- `loyalties`
- `abilities`
- `constraints`
- `important_history`
- `relationship_refs`
- `state_history`
- `state_at_event`

### 3. Relationship Profiles

Purpose:
- capture the changing dynamics between characters over time

Each profile should ideally include:
- `relationship_id`
- `source_character`
- `target_character`
- `relationship_type`
- `baseline_dynamic`
- `trust_level`
- `conflict_level`
- `romantic_signal`
- `shared_history`
- `change_log`
- `state_at_event`

### 4. Entity And Location Profiles

Purpose:
- track important non-character world elements

Each profile should ideally include:
- `entity_id`
- `name`
- `entity_type`
- `description`
- `rules_or_constraints`
- `connected_characters`
- `status_history`
- `state_at_event`

### 5. Canon Snapshots

Purpose:
- reconstruct what is true at a chosen point in the story

Each snapshot should ideally include:
- `snapshot_id`
- `anchor_event_id` or `scene_ref`
- `character_states`
- `relationship_states`
- `entity_states`
- `active_goals`
- `active_threats`
- `known_information`
- `unresolved_threads`

### 6. Causal Graph

Purpose:
- represent cause-and-effect and downstream dependency

Each graph should ideally include:
- `events`
- `caused_by`
- `causes`
- `required_for`
- `prevents`
- `critical_path`
- `flexible_events`
- `causal_chains`
- `divergence_points`

### 7. Arc Registry

Purpose:
- track multi-event developments above scene level

Each arc should ideally include:
- `arc_id`
- `title`
- `characters`
- `starting_event`
- `development_beats`
- `resolution_or_status`
- `dependencies`

### 8. Knowledge Registry

Purpose:
- track who knows what, and when they learn it

Each entry should ideally include:
- `subject`
- `knowledge_item`
- `acquired_at_event`
- `confidence`
- `source_event`

### 9. Constraint Registry

Purpose:
- encode canon rules a rewrite must respect

Each entry should ideally include:
- `constraint_id`
- `scope`
- `rule`
- `source`
- `locked_before_event`

### 10. Divergence Workspace

Purpose:
- support alternate-canon planning after a chosen divergence

Each divergence plan should ideally include:
- `divergence_event_id`
- `divergence_statement`
- `locked_canon_before`
- `stable_downstream_facts`
- `unstable_downstream_facts`
- `invalidated_events`
- `required_continuity_constraints`
- `target_arcs`

### 11. Rewrite Outline

Purpose:
- provide a grounded plan for new writing after divergence

Each outline beat should ideally include:
- `beat_id`
- `summary`
- `characters_involved`
- `based_on_locked_facts`
- `required_states`
- `relationship_movement`
- `causal_purpose`
- `continuity_notes`

## Current Progress Snapshot

This section should be updated as implementation advances.

### Mostly Present Today

- scene summaries
- event ledger
- event preconditions / consequences / stakes scaffolding
- canonical characters
- character mentions
- alias updates and alias map
- rejected non-characters
- entities present
- entity descriptions
- state changes
- relationship changes
- canon snapshots
- timeline
- character timelines
- character profiles
- provider-backed BookNLP-clean identity integration
- per-book and series identity adapter support
- visual world-state extraction
- target-aware character state retrieval
- causal graph
- search index
- dashboard review
- JSON export
- local evidence extraction
- tool-based analysis mode
- compare mode

### Partially Present Today

- character profile richness
  - a formal profile artifact now exists, but deeper personality, goals, fears, and richer durable state remain incomplete
- relationship profiles
  - stable profile builders exist, but relationship typing/evolution still needs depth and stricter consistency
- entity/location profiles
  - entity registry exists, but still needs stronger dedupe, richer semantics, and stricter normalization
- stable character states
  - builder exists, but output is still thinner than the richer profile and visual-state layers
- visual continuity depth
  - visual state extraction now exists, but the system still needs stronger first-appearance baselines and richer change tracking for generation-grade continuity
- ambiguity and confidence reporting
  - some ambiguity metadata exists, but not yet as a complete reporting layer
- point-in-time querying
  - canon snapshots and target-aware state retrieval exist, but not yet the full event-anchored query surface

### Not Yet Complete

- arc registry
- knowledge registry
- constraint registry
- divergence workspace
- rewrite outline generator
- downstream dependency classification for rewrites
- event-level stable APIs like `snapshot_before(event_id)` or `get_character_profile_at(event_id)`

## Target Runtime Flow

The intended analysis flow is:

```text
raw text
  -> deterministic chunking
  -> local evidence extraction
  -> evidence filtering/scoring
  -> context retrieval
  -> structured or tool-based LLM refinement
  -> deterministic normalization
  -> event / identity / state / relationship outputs
  -> profile, snapshot, timeline, and causal synthesis
  -> export / review / query
```

The intended rewrite flow is:

```text
user selects divergence point
  -> locate event in event ledger
  -> reconstruct canon snapshot before/after event
  -> identify dependent downstream canon
  -> classify stable vs unstable vs invalidated facts
  -> build divergence workspace
  -> generate grounded rewrite outline
  -> retrieve profiles/snapshots/constraints per outline beat
  -> write new chapter(s)
```

## Implementation Phases

### Phase 1: Deterministic Evidence Foundation

Goal:
- reduce dependence on raw LLM discovery

Target components:
- local mention/entity extraction
- basic clustering/coreference
- candidate character/entity/alias generation
- evidence filtering/scoring

Status:
- in progress and already partially implemented

Current files:
- [analysis/local_entity_extractor.py](/B:/Documents/PyCharm/graduationProject/analysis/local_entity_extractor.py)
- [analysis/evidence_schema.py](/B:/Documents/PyCharm/graduationProject/analysis/evidence_schema.py)
- [analysis/evidence_filter.py](/B:/Documents/PyCharm/graduationProject/analysis/evidence_filter.py)

### Phase 2: LLM As Refinement Layer

Goal:
- move from raw discovery to evidence-driven refinement

Target components:
- scene analyzer consuming local evidence
- identity analyzer consuming local evidence
- structured normalization
- compare mode against the baseline path

Status:
- mostly implemented

Current files:
- [analysis/identity_analyzer.py](/B:/Documents/PyCharm/graduationProject/analysis/identity_analyzer.py)

### Phase 3: Tool-Constrained Analysis

Goal:
- stop trusting raw LLM schema output

Target components:
- tool runtime
- validated tool vocabulary
- tool telemetry
- stronger tool-first extraction

Status:
- in progress and partially implemented

Current files:
- [analysis/tool_runtime.py](/B:/Documents/PyCharm/graduationProject/analysis/tool_runtime.py)

Remaining work:
- expand tool vocabulary further
- reduce remaining prompt-shaped extraction behavior
- measure ignored/invalid tool call patterns

### Phase 4: Durable Narrative Artifacts

Goal:
- produce the actual long-term output families

Target components:
- formal event ledger
- formal character profiles
- formal relationship profiles
- formal entity/location profiles
- formal canon snapshot model

Status:
- partial

Needs dedicated modules and export surfaces.

### Phase 5: Point-In-Time Querying

Goal:
- answer canon-state questions at arbitrary narrative points

Target components:
- `get_event(event_id)`
- `snapshot_before(event_id)`
- `snapshot_after(event_id)`
- `get_character_profile_at(character_id, event_id)`
- `get_relationship_state_at(a, b, event_id)`

Status:
- not complete

### Phase 6: Divergence And Rewrite Planning

Goal:
- support mid-canon rewrite workflows

Target components:
- divergence planner
- dependency classifier
- stable/unstable fact partitioning
- rewrite outline generator

Status:
- not started as a dedicated subsystem

## Evaluation Criteria

Every redesign step should be judged against:

- repeatability
- malformed output rate
- identity fragmentation rate
- duplicate canonical rate
- event coverage
- relationship usefulness
- state usefulness
- runtime
- token/call cost
- downstream compatibility

## Definition Of Success

S.A.G.A. is successful when it can:

- reconstruct canon state at a chosen event
- explain which later canon depends on that event
- lock canon before a divergence
- derive grounded constraints for what comes next
- generate a replacement outline that remains faithful to the extracted canon

Until then, every new feature should be evaluated by whether it moves the system closer to that capability.
