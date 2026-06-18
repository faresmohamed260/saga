# S.A.G.A. Methodology And Implementation

## Purpose

S.A.G.A. is a narrative intelligence system for turning novels into reusable canon memory that can support analysis, retrieval, visual generation, and story generation.

The project now has two clearly distinct eras:

- `Prototype`
  The earlier legacy system that relied on filesystem artifacts, JSON contracts, and a more linear scene-analysis pipeline.
- `Current system`
  The production-oriented database-native system that stores canonical analysis state in SQLite, drives operations through the dashboard/runtime, and treats analysis as a staged, resumable workflow.

This document explains:

- the methodological role of the system
- the role of each major component
- how those components are implemented to achieve the goal
- what changed from prototype to current system
- why those changes were necessary

## Methodology

### Core Research / Product Goal

The system is designed to answer a practical generation problem:

How do we convert long-form fiction into structured, reusable memory that preserves canon consistency strongly enough to support downstream sequel planning, visual continuity, and controlled story generation?

That means the system must do more than summarize books. It must persist:

- who exists
- what happens
- where it happens
- how characters and world state change
- what visual traits persist
- what dynamic traits change by scene
- what context is needed later for retrieval and generation

### High-Level Method

The current system follows this methodology:

1. ingest books into a canonical local store
2. extract chapters and scenes
3. establish canonical identity using BookNLP-clean identity bundles
4. run focused analysis agents over the stored scenes
5. write structured outputs directly to SQLite
6. review and operate through the dashboard
7. use persisted canon data for retrieval, visual prompt generation, and decoder workflows

This design deliberately separates:

- `persistent facts`
  Example: identity, stable visual traits, baseline relationships
- `dynamic scene state`
  Example: injuries, outfits, temporary conditions, local scene state

That separation is central to both canonicalism and realism. It prevents the system from collapsing all evidence into one flat summary.

## System Comparison

### Prototype

The prototype proved that the project could:

- ingest books
- split them into chapters/scenes
- run LLM-assisted scene analysis
- export structured artifacts
- build early retrieval and dashboard views

Its methodology was useful for experimentation, but it had several structural weaknesses:

- outputs were distributed across filesystem artifacts and JSON contracts
- analysis health was harder to validate during long runs
- retries and resume behavior were brittle
- identity handling was noisier and easier to overwrite from scene-local output
- visual/world-state behavior was not deeply integrated into the core analysis path
- downstream services had to reconstruct truth from exported files instead of querying a canonical store

### Current System

The current system shifts from artifact-first experimentation to database-native production methodology.

Its methodological principles are:

- SQLite is the canonical operational store
- BookNLP-clean identity is the canonical identity path
- analysis is staged and inspectable
- dashboard operations are first-class, not a thin wrapper over ad-hoc scripts
- visual continuity is part of canon extraction, not only post-processing
- retries must be resumable and observable

## Component Roles And Implementation

## 1. Dashboard Runtime

### Role

The dashboard is the operator control surface for the system.

It exists so the user can:

- stage books
- create and validate import plans
- start analysis jobs
- inspect books, scenes, entities, events, states, visuals, and stories
- inspect provider health
- launch later workflows like decoder or rendering

### Implementation

Main implementation surfaces:

- [apps/dashboard_pro](/B:/Documents/PyCharm/graduationProject/apps/dashboard_pro)
- [apps/dashboard_api/app.py](/B:/Documents/PyCharm/graduationProject/apps/dashboard_api/app.py)

The frontend is a modular React application. The backend is FastAPI and serves:

- dashboard routes
- runtime job APIs
- database-backed inspection endpoints
- provider-health endpoints
- import and analysis control endpoints
- decoder and visual asset operations

Why this matters:

The dashboard is no longer a cosmetic browser for files. It is part of the execution model.

## 2. SQLite Canon Store

### Role

The database is the canonical source of truth for the current system.

It stores:

- books
- chapters
- scenes
- identity bundles
- entities
- events
- timelines
- relationships
- character profiles
- stable states
- visual prompts
- generated images
- generated stories
- dashboard jobs and logs

### Implementation

Main implementation surfaces:

- [saga/storage/models.py](/B:/Documents/PyCharm/graduationProject/saga/storage/models.py)
- [saga/storage/persistence.py](/B:/Documents/PyCharm/graduationProject/saga/storage/persistence.py)
- [docs/SQLITE_SCHEMA.md](/B:/Documents/PyCharm/graduationProject/docs/SQLITE_SCHEMA.md)

Why this changed from the prototype:

The legacy JSON-contract model was useful for early development, but it made it too easy for services to drift apart, duplicate state, and depend on stale filesystem artifacts. A normalized local database gives the system one durable operational truth.

## 3. Ingestion And Scene Preparation

### Role

This layer converts book files into structured text segments that the rest of the system can reason over.

It must:

- parse EPUB/PDF text
- identify chapters
- split chapter text into scenes
- preserve provenance such as chapter index and scene index

### Implementation

Main surfaces:

- [saga/services/epub_processor.py](/B:/Documents/PyCharm/graduationProject/saga/services/epub_processor.py)
- [saga/services/pdf_processor.py](/B:/Documents/PyCharm/graduationProject/saga/services/pdf_processor.py)
- [saga/agents/scene_extractor.py](/B:/Documents/PyCharm/graduationProject/saga/agents/scene_extractor.py)
- [saga/services/database_analysis_run_service.py](/B:/Documents/PyCharm/graduationProject/saga/services/database_analysis_run_service.py)

The current implementation persists chapter and scene rows immediately into SQLite. This is a major difference from the prototype, where exported contracts were often the effective handoff layer.

Why this changed:

The system needed durable state before analysis begins, so jobs can be resumed, audited, and extended later without repeating extraction.

## 4. Identity Pipeline

### Role

Identity establishes the canonical cast and alias space for each book and, where needed, for a series.

It must answer:

- who the stable characters are
- which aliases map to which character
- which entries are narrators or reference entities
- which noisy clusters should be suppressed

### Implementation

Main surfaces:

- [saga/identity/booknlp_identity_adapter.py](/B:/Documents/PyCharm/graduationProject/saga/identity/booknlp_identity_adapter.py)
- [saga/identity/series_identity_provider.py](/B:/Documents/PyCharm/graduationProject/saga/identity/series_identity_provider.py)
- [saga/identity/identity_analyzer.py](/B:/Documents/PyCharm/graduationProject/saga/identity/identity_analyzer.py)

Methodologically, the current system chooses:

- `BookNLP raw output` as the seed
- `BookNLP-clean adapted output` as the canonical provider-facing identity

The adapter exists because raw BookNLP output is useful but not production-safe on its own. It needs cleanup, alias consolidation, suppression of false entities, and conversion into the system’s canonical identity schema.

Why this changed:

The prototype allowed more scene-local or legacy resolver behavior to shape identity. That caused instability, noise, and inconsistent downstream memory. The current system moved identity upstream and made it provider-backed.

## 5. Analysis Agents

### Role

The analysis agents are the reasoning engine of the system.

They read stored scenes and populate the database with structured canon data.

Current major agent families include:

- events
- entities
- character profiles
- character visual baselines
- character visual scene states
- noncharacter visual baselines
- noncharacter scene states
- relationships
- timeline
- stable character states
- world-state consolidation
- visual prompt generation

### Implementation

Main surfaces:

- [saga/agents/db_event_agent.py](/B:/Documents/PyCharm/graduationProject/saga/agents/db_event_agent.py)
- [saga/agents/db_entity_agent.py](/B:/Documents/PyCharm/graduationProject/saga/agents/db_entity_agent.py)
- [saga/agents/db_character_profile_agent.py](/B:/Documents/PyCharm/graduationProject/saga/agents/db_character_profile_agent.py)
- [saga/agents/db_character_visual_baseline_agent.py](/B:/Documents/PyCharm/graduationProject/saga/agents/db_character_visual_baseline_agent.py)
- [saga/agents/db_character_visual_scene_state_agent.py](/B:/Documents/PyCharm/graduationProject/saga/agents/db_character_visual_scene_state_agent.py)
- [saga/agents/db_noncharacter_visual_baseline_agent.py](/B:/Documents/PyCharm/graduationProject/saga/agents/db_noncharacter_visual_baseline_agent.py)
- [saga/agents/db_noncharacter_scene_state_agent.py](/B:/Documents/PyCharm/graduationProject/saga/agents/db_noncharacter_scene_state_agent.py)
- [saga/agents/db_relationship_agent.py](/B:/Documents/PyCharm/graduationProject/saga/agents/db_relationship_agent.py)
- [saga/agents/db_timeline_agent.py](/B:/Documents/PyCharm/graduationProject/saga/agents/db_timeline_agent.py)
- [saga/agents/db_stable_character_state_agent.py](/B:/Documents/PyCharm/graduationProject/saga/agents/db_stable_character_state_agent.py)
- [saga/agents/db_world_state_consolidation_agent.py](/B:/Documents/PyCharm/graduationProject/saga/agents/db_world_state_consolidation_agent.py)

These agents are orchestrated by:

- [saga/services/database_analysis_run_service.py](/B:/Documents/PyCharm/graduationProject/saga/services/database_analysis_run_service.py)

Why this changed:

The prototype concentrated too much responsibility into broader scene-analysis passes and later contract-build steps. The current system moved toward narrower database-native agent roles so each analytical responsibility can be inspected, resumed, and improved independently.

## 6. Visual World State And Prompt Generation

### Role

This layer supports visual continuity and image generation.

It must produce:

- baseline visual traits per entity
- scene-level visual changes
- prompt-ready structured descriptions
- generated images tied back to the entity rows

### Implementation

Main surfaces:

- [saga/services/entity_visual_prompt_service.py](/B:/Documents/PyCharm/graduationProject/saga/services/entity_visual_prompt_service.py)
- [saga/services/comfyui_character_sheet_service.py](/B:/Documents/PyCharm/graduationProject/saga/services/comfyui_character_sheet_service.py)
- [saga/storage/persistence.py](/B:/Documents/PyCharm/graduationProject/saga/storage/persistence.py)

Methodologically, the current system separates:

- baseline visual identity
- dynamic scene visual state
- rendering prompts
- rendered output images

Why this changed:

The prototype treated visual state more as an add-on. The current system needed it as part of the core analytical memory because later image generation depends on structured, provenance-aware visual data.

## 7. Decoder And Story Generation

### Role

The decoder turns canon memory into controlled long-form story generation.

It must support multiple modes such as:

- pre-canon
- mid-canon
- post-canon
- alternate universe

### Implementation

Main surfaces:

- [saga/services/database_decoder_service.py](/B:/Documents/PyCharm/graduationProject/saga/services/database_decoder_service.py)
- [saga/services/generated_story_epub_service.py](/B:/Documents/PyCharm/graduationProject/saga/services/generated_story_epub_service.py)
- [apps/dashboard_api/app.py](/B:/Documents/PyCharm/graduationProject/apps/dashboard_api/app.py)
- [apps/dashboard_pro](/B:/Documents/PyCharm/graduationProject/apps/dashboard_pro)

The current system stores generated stories in the database and exposes them through the dashboard and EPUB export.

Why this changed:

The prototype generation path was less integrated with the operational store. The current system needed decoder outputs to be inspectable, exportable, and tied to the same canon database as the analysis.

## 8. Provider Infrastructure

### Role

Provider infrastructure is responsible for model transport, account rotation, health inspection, and controlled failure behavior.

### Implementation

Main surfaces:

- [saga/providers/llm_client.py](/B:/Documents/PyCharm/graduationProject/saga/providers/llm_client.py)
- [saga/providers/ollama_account_rotator.py](/B:/Documents/PyCharm/graduationProject/saga/providers/ollama_account_rotator.py)
- [saga/providers/general_compute_account_rotator.py](/B:/Documents/PyCharm/graduationProject/saga/providers/general_compute_account_rotator.py)
- [saga/providers/codex_session_store.py](/B:/Documents/PyCharm/graduationProject/saga/providers/codex_session_store.py)

Current methodological rules include:

- same-provider rotation is allowed for long canonical runs
- cross-provider fallback is non-canonical
- provider failures must be visible and diagnosable
- dashboard health should expose provider/account state

Why this changed:

The prototype path was more vulnerable to silent degradation during long runs. The current system had to make provider behavior explicit because reliability is part of methodology, not only infrastructure.

## Why The Migration Happened

The move from prototype to current system was not cosmetic. It happened because the earlier architecture made several critical goals difficult:

- repeatable canon extraction
- identity stability
- resumable long-running jobs
- high-trust dashboard operations
- database-backed retrieval and generation
- direct inspection of structured outputs
- integration with visual generation and later decoder workflows

The current system changes were made to solve those exact problems:

- JSON contracts were replaced by SQLite-backed canonical storage
- legacy resolver behavior was replaced by BookNLP-clean identity
- broad monolithic flows were split into focused agent stages
- dashboard operations became first-class and runtime-backed
- visual state became part of analysis memory
- retry behavior became a product concern, not only a script concern

## Implementation Philosophy

The current implementation follows these practical rules:

- persist early
- keep one canonical store
- separate stable facts from scene-local change
- isolate analytical responsibilities into inspectable stages
- make failures explicit
- allow resume where safe
- expose the operational state in the dashboard

## Current Outcome

The current system should be understood as the production-oriented successor to the prototype.

The prototype demonstrated the concept.

The current system operationalizes it by:

- centering the pipeline on SQLite
- using BookNLP-clean identity as the canonical character source
- running staged database-native agents
- exposing the process through the dashboard runtime
- supporting retrieval, visuals, and decoder workflows from the same persistent memory

That is the core methodological and implementation shift of the project.
