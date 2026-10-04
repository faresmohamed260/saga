<h1 align="center">S.A.G.A.</h1>

<p align="center">
  <strong>Story Analysis, Generation, and Archives</strong><br />
  Evidence-linked narrative intelligence for books and series.
</p>

<p align="center">
  <a href="PROJECT.md">Current status</a>
  · <a href="docs/README.md">Documentation</a>
  · <a href="docs/v2/ANALYSIS_ARCHITECTURE_2026.md">Analysis architecture</a>
  · <a href="CONTRIBUTING.md">Contributing</a>
</p>

<p align="center">
  <a href="https://github.com/faresmohamed260/saga/actions/workflows/backend-ci.yml"><img alt="Backend Architecture CI" src="https://github.com/faresmohamed260/saga/actions/workflows/backend-ci.yml/badge.svg?branch=main" /></a>
  <a href="https://github.com/faresmohamed260/saga/actions/workflows/dashboard-pro-ci.yml"><img alt="Dashboard Pro CI" src="https://github.com/faresmohamed260/saga/actions/workflows/dashboard-pro-ci.yml/badge.svg?branch=main" /></a>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/License-MIT-8A2BE2" />
</p>

> **Project state:** S.A.G.A. has a production-domain, invite-only closed-beta surface, but the current v2 product is still in progress and is **not operational end to end**. Required application APIs and additional qualification testing remain incomplete. Phase 1 is complete, the Phase 2 repository foundation is complete, and Phase 3 local-first narrative analysis is active. Historical v1 runtime material is retained as evidence and reference, not treated as current v2 implementation.

## The problem

Books are not flat text. A useful narrative system must understand who a character is across aliases and mentions, who spoke each line, what happened, where and when it happened, how relationships and states changed, and which source passage supports every claim.

S.A.G.A. reverse-engineers novels and series into an evidence-linked narrative model for analysis, retrieval, timelines, visualization, and later canon-aware generation.

## Product goal

~~~mermaid
flowchart LR
    A["TXT / EPUB source"] --> B["Structure + mentions"]
    B --> C["Characters + dialogue"]
    C --> D["Scenes + atomic events"]
    D --> E["Relationships + state"]
    E --> F["Timeline + causality"]
    F --> G["Retrieval · visualization · generation"]
~~~

Every derived claim should preserve source evidence, provenance, uncertainty, and the distinction between a candidate observation and accepted canon.

## Current v2 capabilities

### Application foundation

- Web-first closed-demo product with invite-only access.
- Supabase-owned identity and S.A.G.A.-owned product admission.
- Private source ingestion, normalized text/section persistence, and owner-scoped access.
- Durable jobs, leases, immutable runs, provenance, and evidence review surfaces.
- Provider-neutral storage and analysis boundaries.
- Backblaze B2 for private binary/source objects and Supabase/Postgres for structured state.

### Local-first analysis foundation

- Deterministic TXT/EPUB ingestion with normalized Unicode offsets and fingerprints.
- Precision-first character identity policy with unresolved/quarantined evidence preserved.
- Public LitBank evaluation harnesses and reproducible component fingerprints.
- Deterministic quote detection currently leading the measured public comparison at **0.8563 F1**.
- BookNLP event-trigger challenger measured at **0.7791 F1**, without premature production adoption.
- Strict event participant, semantic qualifier, relationship-observation, narrative-order, temporal-cue, and life-state-candidate contracts.
- Persistent local BookNLP stdio transport measured faster than one-shot execution with exact semantic equality.
- Model-light CI plus dedicated whole-book/local qualification paths.

Measured challengers are not silently promoted to defaults. See [PROJECT.md](PROJECT.md) and the [component scorecard](docs/validation/PHASE_V2_3_COMPONENT_SCORECARD.md) for current evidence and decisions.

## Analysis strategy

S.A.G.A. uses a cost-aware evidence cascade:

1. **Deterministic structure and rules**
2. **Lightweight local literary NLP**
3. **Specialized local models for unresolved ambiguity**
4. **Small local generative reasoning over bounded evidence packets**

The required text-analysis path uses no paid AI subscription or API. Modal is reserved for image/media generation. Full novels and multi-book series—not short demo chunks—are the target workload.

## Architecture

~~~mermaid
flowchart TB
    WEB["Next.js web application"]
    SUPA["Supabase: Auth, Postgres, durable jobs"]
    WORKER["Local analysis worker: outbound-only"]
    NLP["Python NLP sidecars and optional local inference"]
    B2["Backblaze B2: private source and object storage"]
    MEDIA["Media generation boundary: Modal when approved"]

    WEB --> SUPA
    SUPA <--> WORKER
    WORKER --> NLP
    WORKER <--> B2
    WORKER --> MEDIA
    MEDIA --> SUPA
~~~

The browser never talks directly to a local model. Supabase owns durable queue truth, so an offline worker can reconnect and resume. Provider output remains evidence; deterministic S.A.G.A. policy owns identifiers, validation, persistence, and state transitions.

## Technology

- **Backend and analysis:** Python 3.10+, FastAPI, SQLAlchemy, Alembic, LangGraph, pytest
- **Web:** Next.js/React application under apps/web
- **Persistence:** Supabase PostgreSQL with owner/RLS boundaries
- **Object storage:** Backblaze B2 behind a provider-neutral contract
- **Retrieval and graph options:** pgvector and Neo4j where current contracts adopt them
- **NLP evaluation:** deterministic analyzers, BookNLP experiments, LitBank/public corpora, private modern-fiction qualification
- **Media:** separately governed ComfyUI/Modal generation integrations

## Development method

S.A.G.A. is contract-first, measurement-driven, and remote-first.

- The immediate phase contract is merged before substantial implementation.
- State is labeled precisely: proposed, experimental, implemented, validated, or historical.
- Algorithms and providers are adopted through quality/resource evidence, not because a demo runs.
- Normal CI stays deterministic and model-light.
- Full-book and heavyweight benchmarks run through dedicated qualification paths.
- Architecture, data ownership, storage, authorization, retry behavior, and validation are explicit for every capability.
- Documentation is updated from verified reality before a phase closes.

## Development setup

Create an isolated Python environment and install the package with development dependencies:

~~~bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
pytest
~~~

Large NLP models and full-book corpora are intentionally not part of the default CI path. Follow the active phase and experiment documents before running model-backed qualification.

## Repository map

| Path | Purpose |
| --- | --- |
| apps/web | Current web application |
| services/analysis-worker | Durable analysis orchestration and local-worker control plane |
| packages | Reusable runtime and domain packages |
| integrations | Bounded provider implementations |
| migrations / supabase | Database evolution and hosted schema assets |
| tests | Active v2 contract and behavior tests |
| docs/v2 | Current v2 architecture |
| docs/phases | Execution contracts and amendments |
| docs/experiments | Reproducible measurements and adoption evidence |
| backup/reference | Isolated historical implementation; non-authoritative |

## Documentation

Read in this order before substantial work:

1. [AI development instructions](AGENTS.md)
2. [Current project handoff](PROJECT.md)
3. [Documentation index](docs/README.md)
4. [Durable decisions](docs/DECISIONS.md)
5. [Active Phase 3 contract](docs/phases/PHASE_V2_3_LOCAL_FIRST_NARRATIVE_ANALYSIS.md)
6. [Primary evaluation corpus](docs/phases/PHASE_V2_3_PRIMARY_EVALUATION_CORPUS.md)
7. [2026 analysis architecture](docs/v2/ANALYSIS_ARCHITECTURE_2026.md)
8. [Local literary provider protocol](docs/v2/LOCAL_LITERARY_PROVIDER_PROTOCOL.md)

## Roadmap

The current priority is to complete a trustworthy local-first evidence stack for characters, dialogue, scenes, events, relationships, state, and time. Later phases can build causal/motivational graphs, arcs, summaries, canon-aware retrieval, visualization, and generation on that measured foundation.

No proposed layer is described as shipped until its v2 contract is implemented and validated.

## License

S.A.G.A. is licensed under the [MIT License](LICENSE).
