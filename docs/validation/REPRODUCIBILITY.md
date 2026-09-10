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
| Qualification readiness unit tests | `uv run pytest -q tests/test_production_qualification_readiness.py tests/test_production_qualification_readiness_workflow.py` | none | none | GitHub-hosted Ubuntu | Covers production persistence aliases/host safety, source freshness, provider/pricing readiness, and locks the standalone workflow to manual/read-only/non-paid behavior. |
| Production compose config | `SAGA_ENV_FILE=.env.example SAGA_RELEASE_ID=release-ci-validation docker compose -f deploy/production/compose.yaml config --quiet` | none | none | GitHub-hosted Ubuntu | Static topology validation. |
| Container build | `deploy/production/Dockerfile.runtime`, `deploy/production/Dockerfile.frontend` | none | none | GitHub-hosted Ubuntu | Push disabled except publishing workflow. |
| Dashboard Pro | `cd apps/dashboard_pro && npm ci && npm test -- --run && npm run build` | none | none | GitHub-hosted Ubuntu | Operator UI compatibility gate. |

### Tier 2 — bounded integration/readiness

Runs only when the required environment configuration exists. These checks may read remote production/integration state but must not invoke paid generation providers unless a separate owning workflow explicitly says otherwise.

| Gate | Command or workflow | Required secrets / variables | External assets | Runner | Notes |
| --- | --- | --- | --- | --- | --- |
| Production qualification readiness | `.github/workflows/production-qualification-readiness.yml` -> `python -m scripts.check_production_qualification_readiness --asset-id <manifest-id>` | S.A.G.A. production Supabase DB/API/service-role configuration; persisted provider configuration; optional `OLLAMA_API_KEY`/`MISTRAL_API_KEY`; `vars.SAGA_PROVIDER_COST_RATES_JSON` | committed protected-asset manifest metadata only | GitHub-hosted Ubuntu | Manual-only and `main`-only. Reads production persistence/configuration and checks source freshness/provider/pricing readiness. It does **not** contact R2, download protected bytes, run the nine-stage qualifier, or call reasoning/visual/audio providers. A not-ready result remains a failed Actions run. |
| Real Supabase runtime | `uv run pytest -q tests/test_real_supabase_runtime.py` or `python -m scripts.validate_real_supabase_runtime` | Supabase database URL or component DB env, Supabase API URL, service-role key | temporary runtime objects only | GitHub-hosted or self-hosted with network access | Must create and clean test records/objects. |
| Real runtime stack | `uv run pytest -q tests/test_real_runtime_stack.py` or `python -m scripts.validate_real_runtime_stack` | Supabase plus configured provider secrets | temporary runtime report objects | GitHub-hosted or self-hosted | Exercises reasoning/retrieval/web-search persistence path; use only under its owning integration contract. |
| Protected asset acquisition | `.github/workflows/protected-asset-verification.yml` + `scripts/check_protected_asset_storage.py` | `R2_ACCOUNT_ID`, `R2_BUCKET_NAME`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | commercial EPUBs listed in `PROTECTED_TEST_ASSETS.md` | GitHub-hosted Ubuntu | Manual-only. Supports `default`/`eu`/`us`/`fedramp` R2 endpoints and distinguishes access, object-presence, and download failures before hashing. |
| Protected asset hash verification | `scripts/verify_protected_assets.py` within the protected-asset workflow | same R2 secrets | selected downloaded object | GitHub-hosted Ubuntu | Compares SHA-256 to the committed manifest and deletes temporary bytes afterward. |

### Tier 3 — expensive/live-provider qualification

Manual or explicitly gated only.

| Gate | Command or workflow | Required secrets / variables | External assets/models | Runner | Notes |
| --- | --- | --- | --- | --- | --- |
| Clean-source production qualification | `.github/workflows/production-qualification.yml` -> `python -m scripts.run_production_qualification` | production Supabase DB/API/service-role configuration; persisted `modal_xcore_litbank`, `modal_comfyui`, `modal_kokoro_tts`; usable persisted Ollama API key or `OLLAMA_API_KEY`; Mistral persisted or `MISTRAL_API_KEY`; R2 protected-asset secrets; `vars.SAGA_PROVIDER_COST_RATES_JSON` | one explicitly selected protected EPUB that is unseen in production persistence plus live provider models | GitHub-hosted Ubuntu with explicit live-cost confirmation | Manual-only and `main`-only; binds release id to exact `GITHUB_SHA`, repeats readiness before protected download/live provider work, and removes protected/temp bytes afterward. |
| Modal worker inventory/provision | `.github/workflows/modal-worker-*.yml` | `SAGA_MODAL_TOKENS_JSON`, `HF_TOKEN`, `CIVITAI_API_TOKEN` where applicable | provider-hosted models only | GitHub-hosted trigger dispatching Modal | Expensive; keep dispatch/manual or explicitly gated. |
| Visual generation live checks | visual generation scripts / Modal ComfyUI workflows | Supabase, persisted `modal_comfyui`, Mistral vision secrets | generated images in object storage | Cost-controlled | Do not run automatically on every PR. |
| Audiobook live checks | audiobook scripts / Modal Kokoro + Mistral Voxtral | Supabase, persisted `modal_kokoro_tts`, `MISTRAL_API_KEY` or persisted Mistral | audio outputs in object storage | Cost-controlled | Do not run automatically on every PR. |

## Protected test data

Protected book inputs are documented in `docs/operations/PROTECTED_TEST_ASSETS.md`. CI may use them only through an authorized private storage download followed by SHA-256 verification and cleanup.

The protected storage diagnostic helper intentionally does not print credentials, account ids, bucket names, object listings, or protected bytes. A live storage check produces one bounded category:

- `access_failed` — account/bucket/jurisdiction/token scope or Object Read/List access is wrong;
- `object_missing` — private listing succeeded, but the exact manifest object key does not exist;
- `download_failed` — the object is visible but cannot be downloaded;
- success — bytes were downloaded, after which the independent hash verifier must still pass.

Issue #142 tracks the private-source prerequisite. Storage success alone is insufficient for clean-source qualification: the selected manifest asset must also be absent from the production library by filename/SHA. If every listed source is stale in production, add metadata for another authorized unseen protected source and store the bytes only privately.

The standalone **Production Qualification Readiness** workflow checks that production freshness condition using manifest metadata and production persistence only. It intentionally has no R2 credentials or protected-download path.

## Qualification pricing contract

Production qualification is stricter than “the providers returned output.” The qualification evaluator requires recorded usage charges to be priced and reconciled.

`SAGA_PROVIDER_COST_RATES_JSON` is a non-secret runtime configuration value. For the current nine-stage qualification path it must contain valid versioned **provider-wide fallback** `CostRate` entries for:

- `ollama` — gpt-oss/retrieval metering;
- `mistral` — reasoning, visual semantic QA, and Voxtral transcription metering;
- `modal` — Modal endpoint work such as identity, image generation, and TTS.

More-specific account/model rates may coexist and override the fallbacks. Do not invent rates solely to make the evaluator green; rates must correspond to the intended accounting policy/provider pricing.

The standalone readiness workflow validates the structure/coverage of those configured rates but never invokes the providers whose future usage would be priced.

## Expected remote execution behavior

- Normal PR CI should not require local Ollama, local books, local ComfyUI, local Neo4j, or the developer workstation.
- A GitHub-hosted qualification/readiness check must not silently fall back to `127.0.0.1` for production Supabase or Ollama.
- A persisted Ollama provider row without a usable API key is not qualification-ready.
- `production-qualification-readiness.yml` is manual-only, `main`-only, reads production persistence/configuration, and must remain free of R2 acquisition and paid provider execution.
- `protected-asset-verification.yml` is manual-only and checks private storage visibility/object presence/download/hash, not production source freshness.
- `production-qualification.yml` is manual-only, `main`-only, requires `confirm_live_cost=true`, and never uploads the protected EPUB as an artifact.
- Live FLUX runtime/gateway deployment is manual-only and must not fire on ordinary `main` pushes.
- Dirty-worktree qualification is evidence only; promotable qualification requires a committed SHA, clean tracked source, a `main` dispatch, and a source that is fresh in production persistence.

## Latest deterministic / hosted evidence

On 2026-09-10, repository recovery and the subsequent control-plane work passed the current deterministic/backend/migration/container compatibility gates.

PR #145 final head `8b00e732bfeda213b77dc77a44ebc60fabc46a8e` passed Backend Architecture CI and Required Check Compatibility before merging as `67e852116af2efea9484daa6ddb343397c5322a9`.

PR #146 final head `0297b5abd9785b35cbe7e3c842ee40489c97f792` passed Required Check Compatibility run `34515749221` and Backend Architecture CI run `34515749174` before merging as `b689e17bf2b70ea6c2ade0c3795bb85bb048d57b`.

The dated external-readiness evidence is in `docs/validation/PHASE_0_EXTERNAL_READINESS_2026-09-10.md`. It establishes that the actual S.A.G.A. production DB path and qualification pricing are not currently configured in GitHub Actions, and that the configured generic R2 namespace cannot list a bucket on any supported jurisdiction endpoint.

The historical protected-asset run `34432226628` predates the bounded diagnostic helper and failed with an opaque `HeadObject` 403; do not use it to infer an object-missing condition.