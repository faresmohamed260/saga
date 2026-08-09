# Migration Reference

This document is the working reference for the current system rewrite.

It summarizes:

- the project goal
- the target architecture
- the migration rules
- what has already been rebuilt
- what still remains

It is intentionally practical. It is not a historical write-up of the old system. It is the reference for the new architecture we are building.

## 1. Goal

The goal is to transform the current SAGA system from a legacy, tightly coupled, mixed-concern codebase into a professional platform that is:

- scalable
- modular
- decoupled
- reusable
- easier to deploy, test, and maintain

The system purpose remains the same:

- analyze existing books
- extract canonical story knowledge
- generate new canon-aware books
- visualize stories with image generation
- generate audiobooks

What changes is the architecture.

Instead of embedding provider logic, persistence details, workflow glue, and agent behavior directly inside legacy application code, the new system moves shared capabilities into clean runtime/service boundaries.

## 2. Architecture Direction

The architecture direction is best described as:

**a strangler-fig migration from a legacy monolith into a modular, hexagonal, service-oriented AI platform**

The main architectural ideas are:

- **Strangler migration**: rebuild one slice cleanly, cut traffic over, then delete the legacy slice
- **Hexagonal architecture**: business logic depends on contracts, not provider SDK details
- **Service-oriented design**: reasoning, retrieval, web search, image generation, TTS, coref, persistence, and storage are treated as reusable capability services
- **Modular monolith first**: keep one repo while enforcing strong boundaries; split physical deployments where scale or operational need justifies it

## 3. Migration Rules

These rules define how the rewrite should proceed.

1. When a capability is rebuilt cleanly in the new architecture, it becomes the only supported active path.
2. Legacy compatibility is not a goal by itself.
3. We do not keep duplicate active implementations for the same responsibility.
4. Once the new implementation fully covers an old slice, the old slice should be removed.
5. Agents should consume reusable platform capabilities, not local legacy helpers or vendor-specific glue.
6. Infrastructure logic must live inside runtimes/services, not inside domain workflows or agents.

In short:

**rebuild -> cut over -> delete legacy**

## 4. Target System Shape

The target system has five layers.

### 4.1 Capability Platform

Reusable, product-agnostic runtimes and services.

Current/target capability areas:

- reasoning runtime
- retrieval runtime
- web search runtime
- image runtime
- TTS runtime
- coreference / identity runtime
- compute / deployment runtime
- unified persistence/storage runtime

These should be usable outside SAGA.

### 4.2 Application / Domain Layer

SAGA-specific workflows and use cases.

Examples:

- ingestion
- chapter and scene preparation
- canonical analysis
- visual prompt construction
- story generation
- audiobook generation
- dashboard jobs and pipelines

This layer may orchestrate runtimes, but should not know provider internals.

### 4.3 Agent Layer

Role-based agents built on LangGraph.

Agents should:

- reason
- decide which tools to use
- call runtime-native tools

Agents should not:

- manage provider rotation
- manage Modal accounts
- know database engine details
- embed provider SDK logic directly

### 4.4 Interface Layer

User-facing surfaces:

- dashboard API
- dashboard frontend
- admin/provider configuration surfaces

These should remain thin and call application services, not provider logic directly.

### 4.5 Infrastructure Layer

Operational concerns:

- Modal deployments
- Ollama / general compute providers
- database engine
- storage backend
- secrets/configuration
- monitoring and diagnostics

This is the outer layer and should be swappable.

## 5. Preferred Data Architecture

The long-term data split should be:

- **Postgres / Supabase** for structured operational data
- **artifact storage** for files and generated media

Structured data includes:

- books
- chapters
- scenes
- entities
- events
- relationships
- prompts
- jobs
- provider configs
- generated stories
- audiobook records

Artifact storage includes:

- source uploads
- generated images
- thumbnails
- exports
- temporary render outputs
- audio files
- identity outputs

SQLite is acceptable as a transitional store, but it is not the intended long-term platform database for the website-backed system.

## 6. Current Platform Components

These are the major reusable components that now define the new architecture direction.

### 6.1 Reasoning Runtime

Purpose:

- provide text/json reasoning through clean contracts
- own provider selection and request behavior
- expose LangGraph-native tools

Current notes:

- packaged as reusable runtime code under `packages/reasoning_runtime`
- native LangGraph tool surface exists
- live inference has been tested
- native Codex provider path was removed
- general compute pool mutation bug was fixed

### 6.2 Web Search Runtime

Purpose:

- provide generic search/fetch/wiki capability
- stay independent of SAGA-specific agent logic
- expose LangGraph-native tools

Current notes:

- packaged under `packages/web_search_runtime`
- native LangGraph tools exist
- live agent smoke tested with search, fetch, and MediaWiki search

### 6.3 Retrieval Runtime

Purpose:

- provide portable document retrieval
- support hybrid retrieval-oriented workflows
- expose LangGraph-native tools

Current notes:

- packaged under `packages/retrieval_runtime`
- native LangGraph tools exist
- live agent smoke tested using real embeddings

### 6.4 Unified Persistence/Storage Runtime

Purpose:

- provide reusable structured persistence, vector storage, and object storage operations
- expose one provider-oriented runtime surface for database and storage concerns

Current notes:

- packaged under `packages/persistence_runtime`
- Supabase is implemented as a provider rather than the runtime itself
- native LangGraph tools exist for structured rows, vectors, and object storage
- live validation has been completed against the self-hosted Supabase stack

### 6.5 Agent Runtime

Purpose:

- provide a reusable LangGraph execution surface
- allow agents to use runtime-native tools directly

Current notes:

- implemented under `packages/agent_runtime`
- stateful tool loop exists
- live smoke proved packaged reasoning runtime can be used from a LangGraph agent
- retrieval and web search were also smoke tested through the same loop

## 7. Operational Service Surfaces

These are the main deployed/shared service categories currently in scope for the wider platform.

- image generation service
- coreference / identity service
- TTS service
- reasoning service
- retrieval service
- web search service
- persistence service
- unified persistence/storage service
- compute/deployment orchestration service

Not all of them are fully separated yet, but this is the intended platform map.

## 8. Current Progress Summary

### 8.1 Completed or Substantially Completed

#### Frontend cleanup

- dashboard frontend split-component branch was reviewed and merged on GitHub
- local dashboard frontend was cleaned up to remove transitional wrappers and stale surfaces
- Narraverse frontend surface was removed locally
- obsolete `apps/cli` surface was removed locally

#### Runtime extraction

- reasoning runtime extracted as reusable package
- retrieval runtime extracted as reusable package
- web search runtime extracted as reusable package
- persistence runtime expanded to cover structured, vector, and object storage
- agent runtime extracted as reusable package

#### LangGraph foundation

- LangGraph added to the project
- reusable LangGraph runtime implemented
- runtime-native LangGraph tool surfaces added
- tests added for runtime integration
- live smoke tests completed for reasoning, retrieval, and web search

#### Reasoning cleanup

- native Codex provider removed from packaged reasoning runtime
- compatibility string handling kept only where needed in SAGA-side adapter behavior
- general compute pool bug fixed and verified with live inference

#### Frontend de-legacy work

- duplicate compatibility barrel imports removed in `dashboard_pro`
- documentation updated for new frontend structure
- frontend tests and build passed

### 8.2 In Progress

- systematic legacy cleanup in SAGA slices now covered by extracted runtimes
- reduction of old direct provider access paths
- migration from mixed local service glue toward runtime-first usage

## 9. Remaining Major Work

### 9.1 Persistence and Storage

Still needed:

- migrate active callers fully onto the unified persistence runtime
- retire the old split artifact-storage surface after cutover
- add additional providers beyond Supabase if needed

### 9.2 Compute / Deployment Runtime

Still needed:

- abstract Modal-specific deployment and invocation logic into a reusable runtime/service
- centralize account rotation, deployment checks, deploy-if-missing behavior, and service invocation
- remove remaining direct project-specific Modal glue from legacy paths

### 9.3 Image Runtime

Still needed:

- finalize clean production path for image generation
- fully separate workflow execution concerns from dashboard/system glue
- keep the new direct/runtime-based design and remove covered legacy execution paths

### 9.4 Coreference / Identity Runtime

Still needed:

- formalize identity/coref as a reusable runtime/service boundary
- remove legacy fallback logic once the clean runtime path is active

### 9.5 Agent Migration

Still needed:

- rebuild real production agents on top of LangGraph
- ensure they use runtime-native tools only
- remove legacy agent-specific helper paths once covered

### 9.6 Domain/Application Cleanup

Still needed:

- separate reusable capability code from SAGA-specific orchestration more consistently
- reduce mixed-concern services that combine domain logic with infrastructure logic
- delete duplicate old implementations after cutover

### 9.7 Database Migration

Still needed:

- plan Supabase/Postgres schema migration carefully
- preserve existing provider configs and access tokens during migration
- move config access into clean runtime-driven flows

## 10. Definition of Legacy Code

For this migration, code is considered legacy if it does any of the following:

- duplicates functionality already covered by a new runtime/service
- mixes provider logic with domain logic
- mixes storage/persistence concerns with orchestration logic
- exposes multiple active paths for the same responsibility
- exists mainly to preserve old coupling
- bypasses the new runtime contracts

Legacy code should not be preserved automatically. It should either:

- be migrated into the new architecture, or
- be deleted

## 11. Immediate Priorities

The highest-value next steps are:

1. finish persistence/storage abstraction cleanly
2. complete cutover onto the unified Supabase-backed persistence/storage runtime
3. formalize compute/deployment runtime for Modal and shared compute routing
4. continue deleting legacy slices already covered by extracted runtimes
5. migrate real agents onto LangGraph using runtime-native tools only
6. complete image/coref runtime cleanup where old and new paths still overlap

## 12. Success Criteria

The migration is successful when:

- each shared capability has one clear supported implementation
- agents use platform runtimes rather than local glue
- provider logic is isolated behind reusable service boundaries
- dashboard/API surfaces are thin
- structured data is no longer tied to SQLite assumptions
- provider-backed object storage and vector storage are available through the same runtime surface
- legacy duplicate paths are removed
- the remaining codebase is easier to reason about, test, scale, and deploy

## 13. Working Principle

Whenever there is ambiguity, follow this rule:

**prefer the architecture that increases decoupling, removes duplication, and makes the capability reusable outside SAGA**
