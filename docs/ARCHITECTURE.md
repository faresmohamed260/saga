# S.A.G.A. Architecture

## High-Level Flow

```text
Books
  -> Chapter extraction
  -> Scene extraction
  -> Local evidence extraction
  -> Structured or tool-based scene analysis + identity analysis
  -> Deterministic downstream services
  -> Search / export / dashboard review
```

## Components

### Ingestion

- [services/series_processor.py](/B:/Documents/PyCharm/graduationProject/services/series_processor.py)
- [services/epub_processor.py](/B:/Documents/PyCharm/graduationProject/services/epub_processor.py)
- [services/pdf_processor.py](/B:/Documents/PyCharm/graduationProject/services/pdf_processor.py)

Responsibility:
- normalize one or more books into chapter rows

### Scene Layer

- [analysis/scene_extractor.py](/B:/Documents/PyCharm/graduationProject/analysis/scene_extractor.py)
- [analysis/local_entity_extractor.py](/B:/Documents/PyCharm/graduationProject/analysis/local_entity_extractor.py)
- [analysis/evidence_filter.py](/B:/Documents/PyCharm/graduationProject/analysis/evidence_filter.py)
- [analysis/scene_analysis_orchestrator.py](/B:/Documents/PyCharm/graduationProject/analysis/scene_analysis_orchestrator.py)
- [analysis/scene_analyzer.py](/B:/Documents/PyCharm/graduationProject/analysis/scene_analyzer.py)
- [analysis/identity_analyzer.py](/B:/Documents/PyCharm/graduationProject/analysis/identity_analyzer.py)
- [analysis/tool_runtime.py](/B:/Documents/PyCharm/graduationProject/analysis/tool_runtime.py)

Responsibility:
- split chapters into scenes
- extract local candidate evidence
- filter/scoring candidate evidence before LLM refinement
- route into structured, tool, or compare analysis modes
- extract identity/canonical/mention information in parallel

### Entity And State Layer

- [entities/character_profile_service.py](/B:/Documents/PyCharm/graduationProject/entities/character_profile_service.py)
- [entities/entity_registry_service.py](/B:/Documents/PyCharm/graduationProject/entities/entity_registry_service.py)
- [state/state_transition_service.py](/B:/Documents/PyCharm/graduationProject/state/state_transition_service.py)
- [state/canon_state_service.py](/B:/Documents/PyCharm/graduationProject/state/canon_state_service.py)

Responsibility:
- build formal character profiles
- build tracked entities
- apply state changes in reading order
- reconstruct canon state at a chosen point

### Timeline Layer

- [timeline/timeline_service.py](/B:/Documents/PyCharm/graduationProject/timeline/timeline_service.py)
- [timeline/character_timeline_service.py](/B:/Documents/PyCharm/graduationProject/timeline/character_timeline_service.py)
- [timeline/character_normalizer.py](/B:/Documents/PyCharm/graduationProject/timeline/character_normalizer.py)
- [timeline/causal_graph_service.py](/B:/Documents/PyCharm/graduationProject/timeline/causal_graph_service.py)
- [timeline/event_ledger_service.py](/B:/Documents/PyCharm/graduationProject/timeline/event_ledger_service.py)

Responsibility:
- build ordered story events
- build a durable event ledger artifact
- group events by character
- normalize character labels
- infer batched causal links and graph metrics

### Retrieval And Query Layer

- [rag/story_index_service.py](/B:/Documents/PyCharm/graduationProject/rag/story_index_service.py)
- [rag/scene_index_service.py](/B:/Documents/PyCharm/graduationProject/rag/scene_index_service.py)
- [query/story_query_service.py](/B:/Documents/PyCharm/graduationProject/query/story_query_service.py)

Responsibility:
- index outputs for search
- retrieve grounded evidence from structured outputs

### Infrastructure

- [infrastructure/llm_client.py](/B:/Documents/PyCharm/graduationProject/infrastructure/llm_client.py)

Responsibility:
- multi-provider JSON-first generation
- timeout/retry behavior
- Ollama and hosted model routing

### Dashboard

- [story_dashboard.py](/B:/Documents/PyCharm/graduationProject/story_dashboard.py)

Responsibility:
- product UI
- live execution orchestration
- export contract generation
- search and visualization

## Design Notes

- Raw extraction and resolved/grouped outputs are kept separate.
- Local evidence is treated as evidence, not truth.
- Scene analysis and identity analysis run side by side.
- Tool mode does not trust raw LLM schema output; code assembles the final record from validated tool calls.
- Compare mode exists to validate the redesigned path before replacing the baseline path.
- Downstream grouping is deterministic.
- Causal graph generation is batched to reduce prompt size and timeout risk.

## Long-Term Target

The current architecture is an intermediate state on the way to the fuller target system described in:

- [docs/TARGET_SYSTEM.md](/B:/Documents/PyCharm/graduationProject/docs/TARGET_SYSTEM.md)

That target system is centered on:
- event ledger outputs
- character, relationship, and entity profiles
- point-in-time canon snapshots
- causal dependencies
- divergence planning
- grounded rewrite outline generation
