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
| Protected storage diagnostic unit tests | `uv run pytest -q tests/test_protected_asset_storage.py` | none | none | GitHub-hosted Ubuntu | Covers endpoint selection, manifest selection, exact-key visibility, and bounded acquisition classification without contacting R2. |
| Production compose config | `SAGA_ENV_FILE=.env.example SAGA_RELEASE_ID=release-ci-validation docker compose -f deploy/production/compose.yaml config --quiet` | none | none | GitHub-hosted Ubuntu | Static topology validation. |
| Container build | `deploy/production/Dockerfile.runtime`, `deploy/production/Dockerfile.frontend` | none | none | GitHub-hosted Ubuntu | Push disabled except publishing workflow. |
| Dashboard Pro | `cd apps/dashboard_pro && npm ci && npm test -- --run && npm run build` | none | none | GitHub-hosted Ubuntu | Operator UI compatibility gate. |

### Tier 2 — bounded integration CI

Runs only when repository or environment secrets are configured.

| Gate | Command or workflow | Required secrets | External assets | Runner | Notes |
| --- | --- | --- | --- | --- | --- |
| Real Supabase runtime | `uv run pytest -q tests/test_real_supabase_runtime.py` or `python -m scripts.validate_real_supabase_runtime` | Supabase database URL or component DB env, Supabase API URL, service-role key | temporary runtime objects only | GitHub-hosted or self-hosted with network access | Must create and clean test records/objects. |
| Real runtime stack | `uv run pytest -q tests/test_real_runtime_stack.py` or `python -m scripts.validate_real_runtime_stack` | Supabase plus configured provider secrets | temporary runtime report objects | GitHub-hosted or self-hosted | Exercises reasoning/retrieval/web-search persistence path. |
| Protected asset acquisition | `.github/workflows/protected-asset-verification.yml` + `scripts/check_protected_asset_storage.py` | `R2_ACCOUNT_ID`, `R2_BUCKET_NAME`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | commercial EPUBs listed in `PROTECTED_TEST_ASSETS.md` | GitHub-hosted Ubuntu | Manual-only. Supports `default`/`eu`/`us`/`fedramp` R2 endpoints and distinguishes access, object-presence, and download failures before hashing. |
| Protected asset hash verification | `scripts/verify_protected_assets.py` within the protected-asset workflow | same R2 secrets | selected downloaded object | GitHub-hosted Ubuntu | Compares SHA-256 to the committed manifest and deletes temporary bytes afterward. |

### Tier 3 — expensive/live-provider qualification

Manual or explicitly gated only.

| Gate | Command or workflow | Required secrets | External assets/models | Runner | Notes |
| --- | --- | --- | --- | --- | --- |
| Production qualification | `python -m scripts.run_production_qualification` | Supabase, Modal, reasoning providers, TTS/transcription providers, object storage access | protected EPUB input | Prefer self-hosted or cost-controlled runner | Must bind evidence to exact commit and clean source. |
| Modal worker inventory/provision | `.github/workflows/modal-worker-*.yml` | `SAGA_MODAL_TOKENS_JSON`, `HF_TOKEN`, `CIVITAI_API_TOKEN` where applicable | provider-hosted models only | GitHub-hosted trigger dispatching Modal | Expensive; keep dispatch/manual or explicitly gated. |
| Visual generation live checks | visual generation scripts / Modal ComfyUI workflows | Supabase, persisted `modal_comfyui`, Mistral vision secrets | generated images in object storage | Cost-controlled | Do not run automatically on every PR. |
| Audiobook live checks | audiobook scripts / Modal Kokoro + Mistral Voxtral | Supabase, persisted `modal_kokoro_tts`, `MISTRAL_API_KEY` | audio outputs in object storage | Cost-controlled | Do not run automatically on every PR. |

## Protected test data

Protected book inputs are documented in `docs/operations/PROTECTED_TEST_ASSETS.md`. CI may use them only through an authorized private storage download followed by SHA-256 verification and cleanup.

The protected storage diagnostic helper intentionally does not print credentials, account ids, bucket names, object listings, or protected bytes. A live run should produce one bounded category:

- `access_failed` — account/bucket/jurisdiction/token scope or Object Read access is wrong;
- `object_missing` — private listing succeeded, but the exact manifest object key does not exist;
- `download_failed` — the object is visible but cannot be downloaded;
- success — bytes were downloaded, after which the independent hash verifier must still pass.

## Expected remote execution behavior

- Normal PR CI should not require local Ollama, local books, local ComfyUI, local Neo4j, or the developer workstation.
- Local Ollama account rotation is not available to GitHub-hosted runners unless explicitly replaced by an authenticated remote endpoint or self-hosted runner.
- Modal and external model-provider checks must be manual or secret-gated.
- Live FLUX runtime/gateway deployment is manual-only and must not fire on ordinary `main` pushes.
- Dirty-worktree qualification is evidence only; promotable qualification requires a committed SHA and a clean source check.
- Protected asset verification is manual-only and checks private storage visibility/object presence/download/hash, not production qualification by itself.

## Latest deterministic recovery evidence

On 2026-09-10, the clean recovery worktree passed:

- `uv sync --frozen --extra dev`
- `uv run alembic heads` with one head: `202608090400`
- `uv run python -m scripts.check_source_secrets`
- `uv run pytest -q tests/test_architecture_boundaries.py`
- `uv run pytest -q`
- `cd apps/dashboard_pro && npm ci && npm test -- --run && npm run build`
- `cd apps/dashboard_pro && npm audit --omit=dev --audit-level=high`
- `docker compose -f deploy/production/compose.yaml config --quiet` with the documented CI environment

This proves the deterministic recovery state, not live provider readiness.

## Latest GitHub Actions evidence

Exact clean baseline `961e679cd98405822f80def395ea83a8b43231d9` (PR #140 merged on 2026-09-10) passed Backend Architecture CI with:

- active backend tests;
- migration upgrade, rollback, re-upgrade, and isolated restore;
- production Compose validation;
- runtime image build;
- frontend image build.

Required Check Compatibility also passed. The same `main` push triggered no FLUX deployment workflow, confirming the manual-only live-provider guardrail.

The first protected-asset run `34432226628` predates the diagnostic helper and failed with an opaque `HeadObject` 403. Use the revised manual workflow before attributing that failure to permissions alone.
