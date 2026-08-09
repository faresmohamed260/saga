# S.A.G.A.

[![Backend Architecture CI](https://github.com/faresmohamed260/saga/actions/workflows/backend-ci.yml/badge.svg?branch=main)](https://github.com/faresmohamed260/saga/actions/workflows/backend-ci.yml)
[![Dashboard Pro CI](https://github.com/faresmohamed260/saga/actions/workflows/dashboard-pro-ci.yml/badge.svg?branch=main)](https://github.com/faresmohamed260/saga/actions/workflows/dashboard-pro-ci.yml)

S.A.G.A. analyzes source books into evidence-backed canon, generates grounded stories and visual assets, synthesizes audited audiobooks, and packages release artifacts. The active implementation is a contract-driven collection of reusable runtimes rather than a monolithic application.

## Architecture

The active source tree has four primary surfaces:

- `packages/`: independent runtime packages for agents, reasoning, retrieval, persistence, execution, identity, media generation, observability, lineage, qualification, and deployment.
- `integrations/`: provider implementations for ComfyUI, Kokoro TTS, and XCore LitBank on Modal.
- `apps/dashboard_api/`: stateless FastAPI control and query surface.
- `apps/dashboard_pro/`: React operator dashboard.

Supabase Postgres, pgvector, and object storage are persistence providers behind `packages/persistence_runtime`. LangGraph execution is owned by `packages/agent_runtime`. Provider credentials remain in persistence or deployment secret stores and are injected into runtimes; they are not committed to source control.

The historical implementation is inert reference material under `backup/reference/`. Active code is prohibited from importing it by an automated architecture-boundary test.

## Pipeline

The production orchestration path covers:

1. source ingestion and analysis foundation
2. Modal XCore LitBank identity resolution
3. canon extraction
4. character and world modeling
5. generation planning
6. narrative generation and semantic support
7. visual generation and image QA
8. audiobook synthesis and transcription QA
9. EPUB, manifest, lineage, and qualification reporting

See `docs/system_agent_roadmap.md` and `docs/production_qualification.md` for current implementation and qualification status.

## Development

Python dependencies are locked with `uv`:

```powershell
uv sync --frozen --extra dev
uv run pytest -q
```

Dashboard development:

```powershell
cd apps\dashboard_pro
npm ci
npm test -- --run
npm run build
```

Run the API after configuring the Supabase environment:

```powershell
uv run saga-runtime-api
```

## Production

Production topology and operations are defined under `deploy/production/` and documented in `docs/deployment_operations.md`. API, workers, scheduler, observability, frontend, migrations, and telemetry collector are separate processes.

```powershell
$env:SAGA_ENV_FILE = ".env"
docker compose -f deploy\production\compose.yaml config
docker compose -f deploy\production\compose.yaml up -d
```

Container bases and the OpenTelemetry collector are pinned by digest. CI publishes runtime and dashboard images from `main`, refuses existing version tags, creates provenance attestations, and stores a release manifest containing the commit and image digests. Production promotion additionally fails closed unless the deployment manifest has clean committed source provenance.

## Repository Layout

- `apps/`: API and dashboard application surfaces
- `backup/reference/`: isolated, non-importable historical implementation
- `deploy/production/`: production container topology
- `docs/`: active architecture and operations documentation
- `integrations/`: external provider implementations
- `migrations/`: Alembic-owned PostgreSQL migrations
- `packages/`: reusable runtime packages
- `scripts/`: bounded runtime and validation entrypoints
- `supabase/`: Supabase project schema assets
- `tests/`: active architecture and behavior tests

## Operational References

- `docs/deployment_operations.md`: build, rollout, rollback, backup, and recovery
- `docs/runtime_secrets.md`: provider credential ownership
- `docs/storage_architecture.md`: persistence contracts and provider boundaries
- `docs/production_orchestration_runtime.md`: end-to-end orchestration
- `docs/production_qualification.md`: accepted real-book qualification evidence
- `docs/architecture_hardening_audit.md`: architecture integrity audit
