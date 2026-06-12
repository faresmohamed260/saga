# S.A.G.A. Architecture

## High-Level Flow

```text
Books
  -> Chapter extraction
  -> Scene extraction
  -> Local evidence extraction
  -> Structured scene analysis
  -> Visual/entity world-state extraction
  -> Provider-backed identity reconciliation
  -> Deterministic contract rebuild
  -> Retrieval / dashboard inspection / prompt-pack generation
```

## Current Production Path

The current production path is centered on:

- [services/encoder_persistence_service.py](/B:/Documents/PyCharm/graduationProject/services/encoder_persistence_service.py)
- [saga_tools.py](/B:/Documents/PyCharm/graduationProject/saga_tools.py)
- [core/pipeline_contract.py](/B:/Documents/PyCharm/graduationProject/core/pipeline_contract.py)

Important current production characteristics:

- `booknlp_clean` is the only supported production identity provider
- scene failure handling is explicit and contract-aware
- same-provider rotation is supported for long canonical runs
- visual-world-state extraction happens during analysis, not only after export

## Component Map

## Ingestion

- [services/series_processor.py](/B:/Documents/PyCharm/graduationProject/services/series_processor.py)
- [services/epub_processor.py](/B:/Documents/PyCharm/graduationProject/services/epub_processor.py)
- [services/pdf_processor.py](/B:/Documents/PyCharm/graduationProject/services/pdf_processor.py)

Responsibility:

- normalize one or more books into chapter rows
- preserve book ordering and series context

## Scene And Evidence Layer

- [analysis/scene_extractor.py](/B:/Documents/PyCharm/graduationProject/analysis/scene_extractor.py)
- [analysis/local_entity_extractor.py](/B:/Documents/PyCharm/graduationProject/analysis/local_entity_extractor.py)
- [analysis/evidence_filter.py](/B:/Documents/PyCharm/graduationProject/analysis/evidence_filter.py)
- [analysis/scene_analysis_orchestrator.py](/B:/Documents/PyCharm/graduationProject/analysis/scene_analysis_orchestrator.py)
- [analysis/scene_analyzer.py](/B:/Documents/PyCharm/graduationProject/analysis/scene_analyzer.py)
- [analysis/scene_contract_reconciler.py](/B:/Documents/PyCharm/graduationProject/analysis/scene_contract_reconciler.py)

Responsibility:

- split chapters into planned scenes
- collect local evidence before LLM refinement
- run structured analysis for events, entities, state changes, and relationships
- normalize scene output into contract-safe schema

## Visual World-State Layer

- [analysis/visual_state_analyzer.py](/B:/Documents/PyCharm/graduationProject/analysis/visual_state_analyzer.py)
- [analysis/entity_world_state_analyzer.py](/B:/Documents/PyCharm/graduationProject/analysis/entity_world_state_analyzer.py)
- [query/visual_world_state_service.py](/B:/Documents/PyCharm/graduationProject/query/visual_world_state_service.py)
- [query/comfyui_prompt_pack_service.py](/B:/Documents/PyCharm/graduationProject/query/comfyui_prompt_pack_service.py)

Responsibility:

- extract character appearance, condition, outfit, and body-language evidence
- extract object, creature, and location visual/state evidence
- rebuild target-aware visual world state for review and prompt generation

## Identity Layer

- [redesign_lab/identity/booknlp_identity_adapter.py](/B:/Documents/PyCharm/graduationProject/redesign_lab/identity/booknlp_identity_adapter.py)
- [redesign_lab/identity/identity_provider.py](/B:/Documents/PyCharm/graduationProject/redesign_lab/identity/identity_provider.py)
- [redesign_lab/identity/series_identity_provider.py](/B:/Documents/PyCharm/graduationProject/redesign_lab/identity/series_identity_provider.py)
- [entities/identity_llm_postprocessor.py](/B:/Documents/PyCharm/graduationProject/entities/identity_llm_postprocessor.py)

Responsibility:

- load BookNLP-clean per-book identity payloads
- expose provider-backed `characters`, `alias_index`, `narrator`, and `reference_entities`
- merge or map series-level identity where needed
- keep provider-backed stable rosters from being overwritten by scene-local identity noise

## Contract And Builder Layer

- [core/pipeline_contract.py](/B:/Documents/PyCharm/graduationProject/core/pipeline_contract.py)
- [core/stable_character_state.py](/B:/Documents/PyCharm/graduationProject/core/stable_character_state.py)
- [core/builders](/B:/Documents/PyCharm/graduationProject/core/builders)
- [timeline/timeline_service.py](/B:/Documents/PyCharm/graduationProject/timeline/timeline_service.py)

Responsibility:

- rebuild resolved scene analyses
- build entity registry
- build state result
- build canon snapshots
- build timeline and event ledger
- build character timelines and profiles
- build stable character states

## Retrieval And Query Layer

- [query/narrative_context_service.py](/B:/Documents/PyCharm/graduationProject/query/narrative_context_service.py)
- [query/neo4j_narrative_context_service.py](/B:/Documents/PyCharm/graduationProject/query/neo4j_narrative_context_service.py)
- [query/target_character_state_service.py](/B:/Documents/PyCharm/graduationProject/query/target_character_state_service.py)
- [rag/story_index_service.py](/B:/Documents/PyCharm/graduationProject/rag/story_index_service.py)

Responsibility:

- build grounded retrieval packets from contract artifacts
- support point-in-time or target-aware state reconstruction
- provide structured context for later decoder and visual tooling

## Provider And Runtime Infrastructure

- [infrastructure/llm_client.py](/B:/Documents/PyCharm/graduationProject/infrastructure/llm_client.py)
- [infrastructure/ollama_account_rotator.py](/B:/Documents/PyCharm/graduationProject/infrastructure/ollama_account_rotator.py)
- [infrastructure/general_compute_account_rotator.py](/B:/Documents/PyCharm/graduationProject/infrastructure/general_compute_account_rotator.py)
- [infrastructure/codex_session_store.py](/B:/Documents/PyCharm/graduationProject/infrastructure/codex_session_store.py)
- [infrastructure/openai_account_store.py](/B:/Documents/PyCharm/graduationProject/infrastructure/openai_account_store.py)

Responsibility:

- multi-provider request routing
- retry and timeout logic
- same-provider account rotation
- Hermes-backed Codex session support

## Dashboard Surfaces

- [dashboard_app](/B:/Documents/PyCharm/graduationProject/dashboard_app)
- [dashboard_runtime/app.py](/B:/Documents/PyCharm/graduationProject/dashboard_runtime/app.py)
- [dashboard_api/app.py](/B:/Documents/PyCharm/graduationProject/dashboard_api/app.py)
- [story_dashboard.py](/B:/Documents/PyCharm/graduationProject/story_dashboard.py)

Responsibility:

- local operator UI
- contract browsing and validation
- visual-world-state review
- provider/config inspection
- encode command composition and run inspection

Note:

- the legacy Streamlit dashboard still exists in the repo
- the newer local React dashboard is the more current operator surface

## Design Notes

- local evidence is treated as evidence, not truth
- provider-backed identity is authoritative for canonical stable characters
- scene analyses may be retried, but provider/model drift should remain explicit
- visual-state extraction is part of analysis quality, not only a post-processing concern
- downstream artifact builders are deterministic once scene output is fixed

## Main Current Weakness

The main known artifact weakness is not the identity provider path anymore. It is downstream depth in `stable_character_states`, which is still narrower than the richer character profile and visual-state outputs.
