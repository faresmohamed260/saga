# Reproducibility Manifest

This manifest records what a new GitHub/Codex session needs to validate S.A.G.A. without relying on undocumented files from the original workstation.

## Validation tiers

### Tier 1 — deterministic CI

Runs on ordinary pushes and pull requests where practical.

| Gate | Command or workflow | Secrets | External assets | Runner | Notes |
| --- | --- | --- | --- | --- | --- |
| Python dependency graph | `uv sync --frozen --extra dev` | none | none | GitHub-hosted Ubuntu | Requires committed `uv.lock`. |
| Alembic one-head check | `uv run alembic heads` | none for CI Postgres | none | GitHub-hosted Ubuntu + service Postgres | `backend-ci.yml` uses a local CI Postgres service. |
| Secret scan | `uv run python -m scripts.check_source_secrets` | none | none | GitHub-hosted Ubuntu | Must run before publishing images. |
| Architecture boundary | `uv run pytest -q tests/test_architecture_boundaries.py` | none | none | GitHub-hosted Ubuntu | Confirms active code does not import historical backup. |
| Backend tests | `uv run pytest -q` | none for non-live tests | committed fixtures only | GitHub-hosted Ubuntu | Live-provider tests must remain env-gated. |
| Production compose config | `SAGA_ENV_FILE=.env.example SAGA_RELEASE_ID=release-ci-validation docker compose -f deploy/production/compose.yaml config --quiet` | none | none | GitHub-hosted Ubuntu | Static topology validation. |
| Container build | `deploy/production/Dockerfile.runtime`, `deploy/production/Dockerfile.frontend` | none | none | GitHub-hosted Ubuntu | Push disabled except publishing workflow. |
| Dashboard Pro | `cd apps/dashboard_pro && npm ci && npm test -- --run && npm run build` | none | none | GitHub-hosted Ubuntu | Root README still references this as the operator UI gate. |

### Tier 2 — bounded integration CI

Runs only when repository or environment secrets are configured.

| Gate | Command or workflow | Required secrets | External assets | Runner | Notes |
| --- | --- | --- | --- | --- | --- |
| Real Supabase runtime | `uv run pytest -q tests/test_real_supabase_runtime.py` or `python -m scripts.validate_real_supabase_runtime` | Supabase database URL or component DB env, Supabase API URL, service-role key | temporary runtime objects only | GitHub-hosted or self-hosted with network access | Must create and clean test records/objects. |
| Real runtime stack | `uv run pytest -q tests/test_real_runtime_stack.py` or `python -m scripts.validate_real_runtime_stack` | Supabase plus configured provider secrets | temporary runtime report objects | GitHub-hosted or self-hosted | Exercises reasoning/retrieval/web-search persistence path. |
| Protected asset acquisition | workflow step to download from authorized object storage and verify SHA-256 | storage read credentials | commercial EPUBs listed in `PROTECTED_TEST_ASSETS.md` | GitHub-hosted or self-hosted | Must not expose files as artifacts or logs. |

### Tier 3 — expensive/live-provider qualification

Manual or explicitly gated only.

| Gate | Command or workflow | Required secrets | External assets/models | Runner | Notes |
| --- | --- | --- | --- | --- | --- |
| Production qualification | `python -m scripts.run_production_qualification` | Supabase, Modal, reasoning providers, TTS/transcription providers, object storage access | protected EPUB input | Prefer self-hosted or cost-controlled runner | Must bind evidence to exact commit and clean source. |
| Modal worker inventory/provision | `.github/workflows/modal-worker-*.yml` | `SAGA_MODAL_TOKENS_JSON`, `HF_TOKEN`, `CIVITAI_API_TOKEN` where applicable | provider-hosted models only | GitHub-hosted trigger dispatching Modal | Expensive; keep dispatch/manual or branch-scoped. |
| Visual generation live checks | visual generation scripts / Modal ComfyUI workflows | Supabase, persisted `modal_comfyui`, Mistral vision secrets | generated images in object storage | Cost-controlled | Do not run automatically on every PR. |
| Audiobook live checks | audiobook scripts / Modal Kokoro + Mistral Voxtral | Supabase, persisted `modal_kokoro_tts`, `MISTRAL_API_KEY` | audio outputs in object storage | Cost-controlled | Do not run automatically on every PR. |

## Protected test data

Protected book inputs are documented in `docs/operations/PROTECTED_TEST_ASSETS.md`. CI may use them only through an authorized storage download followed by SHA-256 verification and cleanup.

## Expected remote execution behavior

- Normal PR CI should not require local Ollama, local books, local ComfyUI, local Neo4j, or the developer workstation.
- Local Ollama account rotation is not available to GitHub-hosted runners unless explicitly replaced by an authenticated remote endpoint or self-hosted runner.
- Modal and external model-provider checks must be manual or secret-gated.
- Dirty-worktree qualification is evidence only; promotable qualification requires a committed SHA and a clean source check.

## Latest local deterministic evidence

On 2026-09-10, the clean recovery worktree `B:\Documents\PyCharm\saga-handoff` passed:

- `uv sync --frozen --extra dev`
- `uv run alembic heads` with one head: `202608090400`
- `uv run python -m scripts.check_source_secrets` with 850 files scanned and 0 findings
- `uv run pytest -q tests/test_architecture_boundaries.py` with 4 passed
- `uv run pytest -q` with 338 passed, 3 skipped, 1 Starlette/httpx deprecation warning
- `cd apps/dashboard_pro && npm ci && npm test -- --run && npm run build` with 13 tests passed and successful Vite build
- `cd apps/dashboard_pro && npm audit --omit=dev --audit-level=high` with 0 production vulnerabilities
- `docker compose -f deploy/production/compose.yaml config --quiet` with `.env.example` and `release-ci-validation`

This proves the local deterministic recovery branch state, not live provider readiness.

## Latest GitHub Actions evidence

On 2026-09-10, PR #134 at head `8685f97cec6cca81c2a19536cbe0ab6057d7323c` passed:

- Backend Architecture CI / `test`
- Backend Architecture CI / `migrations`
- Backend Architecture CI / `containers`
- Required Check Compatibility / `dashboard-pro`
- Vercel status context

GitHub emitted Node.js 20 deprecation annotations for `actions/checkout@v4` and `astral-sh/setup-uv@v6` being forced onto Node.js 24. The annotations did not fail the run, but the workflow dependencies should be reviewed during routine CI maintenance.
