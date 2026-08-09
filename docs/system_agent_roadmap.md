# System Agent Roadmap

This document is a progress reference for the rebuilt S.A.G.A. system.

It describes:

- what the new architecture already provides
- what the system is supposed to do
- which agent groups remain to be built
- how those agent groups should be constrained

This document refers only to the active rebuilt architecture plus the legacy backup as a discovery reference.

## Current Rebuilt Foundation

The following reusable runtime/platform layers now exist in the active architecture:

- `packages/agent_runtime`
  - LangGraph-based execution runtime
  - native runtime-tool execution
  - structured traces, summaries, and reports
- `packages/reasoning_runtime`
  - reusable reasoning runtime
  - provider configuration support
  - rotation-ready provider loading
- `packages/web_search_runtime`
  - reusable web search and document fetch runtime
- `packages/retrieval_runtime`
  - reusable retrieval runtime
  - hybrid retrieval-oriented contract surface
- `packages/persistence_runtime`
  - reusable persistence and artifact storage runtime
  - provider config/state storage
  - object and artifact storage
- `packages/modal_runtime`
  - reusable Modal/general compute provider lifecycle runtime
  - account pool loading
  - runtime state handling
  - image-runtime endpoint orchestration
- `packages/generation_planning`
  - LangGraph-native story intent, canon grounding, and blueprint planning runtime
  - consumes persisted canon/CWM memory only
  - persists reusable story generation blueprints
  - validates blueprint reference integrity and visual/audio planning coverage
- `packages/narrative_generation`
  - LangGraph-native scene prose, chapter draft, continuity check, and revision runtime
  - consumes persisted generation blueprints
  - persists generated story records through the active persistence runtime
  - validates blueprint coverage and reference integrity
  - rejects deterministic provider fallback in quality gates
  - live-validated on Lost Sisters and Queen of Nothing persisted blueprints
- `packages/visual_generation`
  - LangGraph-native visual planning, prompt construction, rendering, quality audit, and bounded retry runtime
  - routes portable render contracts through the active Modal/ComfyUI provider
  - persists visual plans, prompts, images, audits, and final decisions
  - live-validated on accepted Lost Sisters and Queen of Nothing stories across all five target types
- `integrations/comfyui`
  - clean image runtime using the new Modal runtime and persisted provider config path
- `supabase/`
  - active persistence target and migration surface

These are infrastructure/runtime layers, not the main book-analysis or book-generation agents themselves.

## What The System Is For

The project is a story analysis and generation system for books.

At a high level, the intended system behavior is:

1. ingest source books
2. analyze them into structured canon memory
3. use that canon memory to generate new stories
4. visualize canon or generated story content
5. generate audiobook outputs

The legacy backup shows that the old monolithic/DB-native encoder was really a canon-construction pipeline, not a single extraction script.

## Canon Memory Surface

The legacy backup indicates that book analysis is expected to produce durable structured memory including:

- books
- chapters
- scenes
- canonical identities
- aliases
- narrator/reference identity data
- events
- entities
- character profiles
- character visual baselines
- non-character visual baselines
- character scene states
- non-character scene states
- relationships
- timeline records
- stable character states
- world state
- visual prompt records

This canon memory is the shared substrate for:

- retrieval
- story generation
- visual generation
- audiobook generation
- operator review

## Agent Families

The full system divides into two major families:

- analysis agents
- generation agents

### Analysis Agents

These agents build canon memory from raw books.

- `IngestionAgent`
- `SceneSegmentationAgent`
- `IdentityAgent`
- `EventAgent`
- `EntityAgent`
- `RelationshipAgent`
- `TimelineAgent`
- `CharacterProfileAgent`
- `StableStateAgent`
- `WorldStateAgent`
- `CharacterVisualBaselineAgent`
- `EntityVisualBaselineAgent`
- `CharacterSceneStateAgent`
- `EntitySceneStateAgent`
- `VisualPromptAgent`
- `RetrievalIndexingAgent`
- `CanonQAReviewAgent`

### Generation Agents

These agents consume canon memory to create new outputs.

#### Story Generation

- `StoryPlanningAgent`
- `CanonGroundingAgent`
- `NarrativeGenerationAgent`
- `ContinuityGuardAgent`
- `RewriteRevisionAgent`

#### Visual Generation

- `SceneSelectionAgent`
- `ImagePromptCompositionAgent`
- `CharacterRenderAgent`
- `EntityRenderAgent`
- `VisualConsistencyAgent`

#### Audiobook Generation

- `AudiobookPlanningAgent`
- `NarrationPreparationAgent`
- `VoiceSynthesisAgent`
- `AudioAssemblyAgent`
- `AudioQAAgent`

#### Cross-Cutting Support

- `RetrievalGroundingAgent`
- `GenerationSafetyPolicyAgent`
- `ArtifactPackagingAgent`

## Recommended Top-Level Agent Groups

For implementation, the agents should be grouped into orchestrated slices rather than built as one giant graph.

### Group 1: Analysis Foundation

- `IngestionAgent`
- `SceneSegmentationAgent`
- `IdentityAgent`

Purpose:

- normalize books into stable chapters/scenes
- create canonical identity context before deeper analysis

### Group 2: Canon Extraction

- `EventAgent`
- `EntityAgent`
- `RelationshipAgent`
- `TimelineAgent`

Purpose:

- extract what happens, who/what exists, and how the canon progresses

### Group 3: Character And World Modeling

- `CharacterProfileAgent`
- `StableStateAgent`
- `WorldStateAgent`

Purpose:

- synthesize durable stateful canon knowledge

### Group 4: Visual Grounding

- `CharacterVisualBaselineAgent`
- `EntityVisualBaselineAgent`
- `CharacterSceneStateAgent`
- `EntitySceneStateAgent`
- `VisualPromptAgent`

Purpose:

- make canon visually renderable and continuity-aware

### Group 5: Retrieval And QA

- `RetrievalIndexingAgent`
- `CanonQAReviewAgent`

Purpose:

- make canon queryable
- detect weak artifacts before downstream generation

### Group 6: Story Generation

- `StoryPlanningAgent`
- `CanonGroundingAgent`
- `NarrativeGenerationAgent`
- `ContinuityGuardAgent`
- `RewriteRevisionAgent`

### Group 7: Visual Generation

- `SceneSelectionAgent`
- `ImagePromptCompositionAgent`
- `CharacterRenderAgent`
- `EntityRenderAgent`
- `VisualConsistencyAgent`

### Group 8: Audiobook Generation

- `AudiobookPlanningAgent`
- `NarrationPreparationAgent`
- `VoiceSynthesisAgent`
- `AudioAssemblyAgent`
- `AudioQAAgent`

## Global Constraints For Every Agent Group

Every future agent group should preserve the same architectural constraints:

- use only the active rebuilt architecture
- stay abstracted, decoupled, scalable, and professional
- do not adapt to or depend on isolated legacy code
- use runtime packages as the source of truth
- do not bypass runtime packages with ad hoc direct integrations
- persist durable outputs through the active persistence runtime
- use LangGraph natively through `packages/agent_runtime`
- prefer deterministic code for schema ownership and state transitions
- use LLMs for bounded reasoning/judgment, not for unstructured system glue
- define explicit artifact families and ownership boundaries
- keep each agent responsible for one clear output family
- validate using real data after each group is built

## System-Level Architectural Rule

The analysis side produces canon memory.

The generation side must consume canon memory rather than raw books whenever analysis artifacts exist.

That means story, visual, and audiobook agents should ground themselves in:

- retrieval results
- canonical identity
- timeline/state/profile artifacts
- visual/world-state artifacts

They should not reconstruct canon ad hoc from source text unless explicitly operating in a fallback or bootstrap mode.

## Progress Snapshot

### Built

- reusable runtime foundation
- persistence/storage runtime
- reasoning runtime
- web search runtime
- retrieval runtime
- Modal/general compute runtime
- LangGraph execution runtime
- clean ComfyUI image runtime
- runtime secret ownership and provider config paths
- live validation for key runtime surfaces
- production analysis foundation group
- production canon extraction group
- production character/world modeling group
- story generation planning sub-slice
- narrative generation live-validated runtime slice
- retrieval-grounded narrative semantic-support and revision gate
- production visual generation and visual grounding agent group
- persisted-image re-audit and rejected-target selective retry operations
- production audiobook generation agent group
- transcription-gated audio QA, chapter/book assembly, and selective resume operations
- production top-level orchestration and dependency policy
- resumable cross-slice job lineage and versioned EPUB/manifest packaging
- durable queue admission, capability concurrency limits, leases, cancellation, retries, and telemetry export
- fresh real-book production qualification through all nine stages
- cooperative canon cancellation and shared round-robin reasoning-provider allocation
- clean release-stabilization branch with reviewable architecture, dashboard, and release-control commits
- fail-closed production promotion requiring clean source, full Git SHA, and immutable image digests
- CI migration rollback, architecture-boundary, dependency-audit, container-build, and release-manifest gates

### Remaining Hardening

- provider-native token/compute usage and price-rate telemetry where upstream APIs expose it
- stricter visual anatomy/action-alignment policy beyond the current automated acceptance thresholds

## Immediate Next Step

Merge the stabilization pull request after CI passes, then publish immutable images from `main`. The next implementation slice should add provider-native cost telemetry; visual quality-policy hardening follows as a separate concern.
