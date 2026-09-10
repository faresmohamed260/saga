# GitHub Actions Secrets Manifest

This file documents required secret/variable names and destinations. It must never contain secret values.

## Repository secrets

| Secret | Owning service | Used by | Required for normal CI | Scope / permissions | Migration status |
| --- | --- | --- | --- | --- | --- |
| `SAGA_MODAL_TOKENS_JSON` | Modal | Modal worker inventory, provision, maintenance, Flux/Qwen/LTX deploy and live smoke workflows | No | JSON roster of Modal accounts; least privilege per Modal account | Present as repository secret on 2026-09-10. The clean-source qualification path prefers the active persisted provider rows instead of enabling env fallback. |
| `HF_TOKEN` | Hugging Face | Modal worker provision/maintenance, model prefetch/deploy workflows | No | Read access to required gated/private model files only | Present as repository secret on 2026-09-10. |
| `CIVITAI_API_TOKEN` | Civitai | Modal worker provision/maintenance and model prefetch workflows | No | Read/download access to selected model files only | Present as repository secret on 2026-09-10. |
| `SAGA_SUPABASE_DB_URL` | Supabase Postgres | real Supabase validation, clean-source production qualification, release/backup checks | No | Application database user or pooler URL appropriate to the workflow | Required for integration/live gates unless complete component DB configuration is supplied. |
| `SAGA_SUPABASE_DB_HOST` | Supabase Postgres | component-based DB configuration / qualification | No | Explicit remote database/pooler hostname | Required when qualification uses component DB configuration; it must not be omitted and allowed to fall back to localhost. |
| `SAGA_SUPABASE_DB_PORT` | Supabase Postgres | component-based DB configuration / qualification | No | Port only; not sensitive alone | Optional; runtime default applies when the remote host/user/password contract is otherwise complete. |
| `SAGA_SUPABASE_DB_NAME` | Supabase Postgres | component-based DB configuration / qualification | No | Database name only | Optional; runtime default applies when appropriate. |
| `SAGA_SUPABASE_DB_USER` | Supabase Postgres | component-based DB configuration / qualification | No | Least-privilege application DB user | Required with host/password unless a pooler tenant identifier constructs the username. |
| `SAGA_SUPABASE_DB_PASSWORD` | Supabase Postgres | component-based DB configuration / qualification | No | Password for DB user | Required with component DB configuration. |
| `SAGA_SUPABASE_POOLER_TENANT_ID` | Supabase Postgres | component-based pooler DB configuration / qualification | No | Project/tenant identifier used to construct pooler username | Optional alternative to an explicit component DB user. |
| `SAGA_SUPABASE_API_URL` or `SUPABASE_URL` | Supabase Storage/API | object storage, runtime validation, clean-source qualification | No | Project API URL | `SUPABASE_URL` present as repository secret on 2026-09-10; S.A.G.A.-prefixed alias not observed. |
| `SAGA_SUPABASE_SERVICE_ROLE_KEY` or `SUPABASE_SERVICE_ROLE_KEY` | Supabase | server-side runtime storage/database operations and clean-source qualification | No | Service-role key; server/Actions only; never expose to browser | `SUPABASE_SERVICE_ROLE_KEY` present as repository secret on 2026-09-10; S.A.G.A.-prefixed alias not observed. |
| `MISTRAL_API_KEY` | Mistral | visual semantic QA, narrative/reasoning providers, Voxtral transcription, clean-source qualification when Mistral is not persisted | No | Provider key with model access needed for selected live gates | Not observed in repository secrets on 2026-09-10. Qualification accepts active persisted Mistral config as an alternative. |
| `OLLAMA_API_KEY` | Ollama cloud | optional clean-source qualification/runtime authentication fallback | No | API key for an authenticated Ollama cloud endpoint | Optional. `.github/workflows/production-qualification.yml` maps this secret when present; active persisted Ollama accounts with usable API keys remain the preferred path. |
| `GEMINI_API_KEY` | Google Gemini | reasoning fallback/live provider checks where configured | No | Provider key with selected model access | Not observed in repository secrets on 2026-09-10. Optional unless a workflow enables Gemini. |
| `OPENROUTER_API_KEY` | OpenRouter | general compute/reasoning fallback if configured | No | Provider key with selected model access | Not observed in repository secrets on 2026-09-10. Optional unless configured. |
| `GROQ_API_KEY` | Groq | general compute/reasoning fallback if configured | No | Provider key with selected model access | Not observed in repository secrets on 2026-09-10. Optional unless configured. |
| `OLLAMA_BASE_URL` | Ollama/self-hosted inference | live local/remote Ollama checks only | No | URL to authenticated remote or self-hosted runner endpoint if used | Optional for separately documented self-hosted/live checks. A GitHub-hosted clean qualification must not assume workstation-local Ollama. |
| `R2_ACCOUNT_ID` | Cloudflare R2 | protected-asset verification and clean-source production qualification | No | Account identifier only | Present as repository secret on 2026-09-10. |
| `R2_BUCKET_NAME` | Cloudflare R2 | protected-asset verification and clean-source production qualification | No | Bucket identifier only | Present as repository secret on 2026-09-10. |
| `R2_ACCESS_KEY_ID` | Cloudflare R2 | protected-asset verification and clean-source production qualification | No | Object Read / List scope for the private protected-asset bucket/prefix | Present as repository secret on 2026-09-10. |
| `R2_SECRET_ACCESS_KEY` | Cloudflare R2 | protected-asset verification and clean-source production qualification | No | Secret half of R2 access key; keep server/Actions-only | Present as repository secret on 2026-09-10. |
| `SAGA_PROTECTED_ASSET_STORAGE_*` | Protected object storage | future provider-neutral protected EPUB acquisition if adopted | No | Read-only credentials for private asset bucket/prefix | S.A.G.A.-prefixed generic names not observed on 2026-09-10. Current workflows use the explicit R2 names above. |
| `SATURN_TOKEN` | Saturn/integration-specific | unclear from current recovery audit | No | Unknown; inspect owning workflow before use | Present as repository secret on 2026-09-10; ownership requires follow-up audit. |

`GITHUB_TOKEN` is provided by GitHub Actions and is used by publish/provenance workflows with workflow-declared permissions.

## Repository / Actions variables

These values are configuration, not credentials. They should not contain secrets.

| Variable | Used by | Requirement | Notes |
| --- | --- | --- | --- |
| `SAGA_PROVIDER_COST_RATES_JSON` | `.github/workflows/production-qualification.yml`, usage governance / production qualification | Required for clean-source qualification | JSON array of active `CostRate` objects. Current qualification readiness requires valid versioned provider-wide fallback rates for `ollama`, `mistral`, and `modal`; more-specific account/model entries may override those fallbacks. Do not fabricate prices simply to satisfy the gate. |

The checked-in production example intentionally leaves `SAGA_PROVIDER_COST_RATES_JSON=[]` as a placeholder. An empty array is **not** qualification-ready because the evaluator rejects unpriced charges.

## Persisted provider configuration required by qualification

Not every live credential belongs in GitHub Actions secrets. The current runtime contract stores provider accounts/configuration in S.A.G.A. persistence and the clean-source qualification preflight checks those rows before downloading a protected book or calling live providers.

Required persisted Modal providers for the current nine-stage path:

- `modal_xcore_litbank` — identity/coreference;
- `modal_comfyui` — stage-7 image generation;
- `modal_kokoro_tts` — stage-8 speech synthesis.

The current default reasoning path also requires at least one **usable Ollama API key**. Prefer the persisted Ollama account configuration; `OLLAMA_API_KEY` is an explicit workflow fallback when configured as a repository/environment secret. Merely having an `ollama` provider row does not make a GitHub-hosted runner qualification-ready; without a usable key the runtime can fall back toward its local Ollama URL. Mistral may be persisted or supplied via `MISTRAL_API_KEY`.

The qualification readiness gate also checks the selected manifest asset against production persistence by filename/SHA before protected-storage download. This is not a secret requirement, but it prevents reusing a book already processed by the production library as if it were an unseen qualification source.

Do not copy provider payloads, persisted book rows, tokens, or cost-rate values into documentation or workflow logs.

## Local secrets found during recovery

- `deploy/neo4j/.env` existed in the former local recovery environment and included `NEO4J_PASSWORD`. Neo4j is not currently a documented production dependency for the active S.A.G.A. runtime.
- `deploy/ollama/accounts.local.json` existed locally and contained account `email`, `password`, and `api_key` fields for local Ollama/account-rotation experiments.

These local values were not copied into this document or committed. If any are still required, migrate them through the active persisted provider contract or an explicitly documented GitHub secret/environment path first.

## Rotation notes

- Rotate any secret pasted into chat or used from an old local file before relying on it for production.
- Keep Supabase service-role credentials server-side only.
- Prefer short-lived or environment-scoped provider keys for expensive live-provider workflows.
- Remove secrets from GitHub when the owning workflow is removed or moved to a different repository.
- Do not enable `SAGA_MODAL_ALLOW_ENV_FALLBACK` merely to bypass missing persisted qualification provider configuration; repair the active provider state instead.
- Do not make a GitHub-hosted qualification depend on developer-workstation localhost services unless a self-hosted runner contract is explicitly adopted and documented.
