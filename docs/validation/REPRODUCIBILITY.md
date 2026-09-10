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
| Qualification readiness unit tests | `uv run pytest -q tests/test_production_qualification_readiness.py` | none | none | GitHub-hosted Ubuntu | Covers persistence aliases, provider readiness, and provider-wide pricing fallback requirements without contacting live providers. |
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

| Gate | Command or workflow | Required secrets / variables | External assets/models | Runner | Notes |
| --- | --- | --- | --- | --- | --- |
| Clean-source production qualification | `.github/workflows/production-qualification.yml` -> `python -m scripts.run_production_qualification` | production Supabase DB/API/service-role configuration; persisted `modal_xcore_litbank`, `modal_comfyui`, `modal_kokoro_tts`; persisted Ollama; Mistral persisted or `MISTRAL_API_KEY`; R2 protected-asset secrets; `vars.SAGA_PROVIDER_COST_RATES_JSON` | one protected EPUB selected by manifest id plus live provider models | GitHub-hosted Ubuntu with explicit live-cost confirmation | Manual-only; binds release id to exact `GITHUB_SHA`, validates readiness before protected-book processing, and removes protected/temp bytes afterward. |
| Qualification readiness | `python -m scripts.check_production_qualification_readiness` | same Supabase/provider config plus `SAGA_PROVIDER_COST_RATES_JSON` | none beyond persisted configuration | GitHub-hosted or controlled operator environment | Non-destructive schema/provider/pricing readiness check. Requires provider-wide fallback rates for `ollama`, `mistral`, and `modal`. |
| Modal worker inventory/provision | `.github/workflows/modal-worker-*.yml` | `SAGA_MODAL_TOKENS_JSON`, `HF_TOKEN`, `CIVITAI_API_TOKEN` where applicable | provider-hosted models only | GitHub-hosted trigger dispatching Modal | Expensive; keep dispatch/manual or explicitly gated. |
| Visual generation live checks | visual generation scripts / Modal ComfyUI workflows | Supabase, persisted `modal_comfyui`, Mistral vision secrets | generated images in object storage | Cost-controlled | Do not run automatically on every PR. |
| Audiobook live checks | audiobook scripts / Modal Kokoro + Mistral Voxtral | Supabase, persisted `modal_kokoro_tts`, `MISTRAL_API_KEY` or persisted Mistral | audio outputs in object storage | Cost-controlled | Do not run automatically on every PR. |

## Protected test data

Protected book inputs are documented in `docs/operations/PROTECTED_TEST_ASSETS.md`. CI may use them only through an authorized private storage download followed by SHA-256 verification and cleanup.

The protected storage diagnostic helper intentionally does not print credentials, account ids, bucket names, object listings, or protected bytes. A live run should produce one bounded category:

- `access_failed` — account/bucket/jurisdiction/token scope or Object Read access is wrong;
- `object_missing` — private listing succeeded, but the exact manifest object key does not exist;
- `download_failed` — the object is visible but cannot be downloaded;
- success — bytes were downloaded, after which the independent hash verifier must still pass.

Issue #142 tracks the current protected-book private-storage prerequisite.

## Qualification pricing contract

Production qualification is stricter than “the providers returned output.” The qualification evaluator requires recorded usage charges to be priced and reconciled.

`SAGA_PROVIDER_COST_RATES_JSON` is a non-secret runtime configuration value. For the current nine-stage qualification path it must contain valid versioned **provider-wide fallback** `CostRate` entries for:

- `ollama` — gpt-oss/retrieval metering;
- `mistral` — reasoning, visual semantic QA, and Voxtral transcription metering;
- `modal` — Modal endpoint work such as identity, image generation, and TTS.

More-specific account/model rates may coexist and override the fallbacks. Do not invent rates solely to make the evaluator green; rates must correspond to the intended accounting policy/provider pricing.

## Expected remote execution behavior

- Normal PR CI should not require local Ollama, local books, local ComfyUI, local Neo4j, or the developer workstation.
- Local Ollama account rotation is not available to GitHub-hosted runners unless explicitly replaced by authenticated persisted provider configuration or a self-hosted runner.
- Modal and external model-provider checks must be manual or secret-gated.
- Live FLUX runtime/gateway deployment is manual-only and must not fire on ordinary `main` pushes.
- Dirty-worktree qualification is evidence only; promotable qualification requires a committed SHA and a clean source check.
- Protected asset verification is manual-only and checks private storage visibility/object presence/download/hash, not production qualification by itself.
- Clean-source production qualification is manual-only, requires `confirm_live_cost=true`, and never uploads the protected EPUB as an artifact.

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

PR #141 at head `2bc87f62deb3e7a17d02ee41f30083ca6db292a3` passed:

- Backend Architecture CI / active backend tests;
- migration upgrade, rollback, re-upgrade, and isolated restore;
- production Compose validation;
- runtime image build;
- frontend image build;
- Required Check Compatibility / Dashboard Pro.

PR #141 merged as `b416eaf0f0b2431845e8b26a4a51d315881bcfa0`, adding protected-R2 diagnostic classification and updating Phase-0 evidence.

The historical protected-asset run `34432226628` predates that diagnostic helper and failed with an opaque `HeadObject` 403. Use the revised manual workflow before attributing that failure to permissions alone.
