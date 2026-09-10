# GitHub Actions Secrets Manifest

This file documents required secret names and destinations. It must never contain secret values.

## Repository secrets

| Secret | Owning service | Used by | Required for normal CI | Scope / permissions | Migration status |
| --- | --- | --- | --- | --- | --- |
| `SAGA_MODAL_TOKENS_JSON` | Modal | Modal worker inventory, provision, maintenance, Flux/Qwen/LTX deploy and live smoke workflows | No | JSON roster of Modal accounts; least privilege per Modal account | Required; value must be configured in GitHub if live Modal workflows are used. |
| `HF_TOKEN` | Hugging Face | Modal worker provision/maintenance, model prefetch/deploy workflows | No | Read access to required gated/private model files only | Required for live model acquisition; not needed for deterministic CI. |
| `CIVITAI_API_TOKEN` | Civitai | Modal worker provision/maintenance and model prefetch workflows | No | Read/download access to selected model files only | Required for Civitai-backed live model acquisition. |
| `SAGA_SUPABASE_DB_URL` | Supabase Postgres | real Supabase validation, production qualification, release/backup checks | No | Application database user or pooler URL appropriate to the workflow | Required for integration/live gates. |
| `SAGA_SUPABASE_DB_HOST` | Supabase Postgres | component-based DB configuration | No | Hostname only; not sensitive alone | Optional alternative to full DB URL. |
| `SAGA_SUPABASE_DB_PORT` | Supabase Postgres | component-based DB configuration | No | Port only; not sensitive alone | Optional alternative to full DB URL. |
| `SAGA_SUPABASE_DB_NAME` | Supabase Postgres | component-based DB configuration | No | Database name only | Optional alternative to full DB URL. |
| `SAGA_SUPABASE_DB_USER` | Supabase Postgres | component-based DB configuration | No | Least-privilege application DB user | Optional alternative to full DB URL. |
| `SAGA_SUPABASE_DB_PASSWORD` | Supabase Postgres | component-based DB configuration | No | Password for DB user | Optional alternative to full DB URL. |
| `SAGA_SUPABASE_API_URL` | Supabase Storage/API | object storage and runtime validation | No | Project API URL | Required for real storage validation. |
| `SAGA_SUPABASE_SERVICE_ROLE_KEY` | Supabase | server-side runtime storage/database operations | No | Service-role key; server/Actions only; never expose to browser | Required for real storage/runtime validation. |
| `MISTRAL_API_KEY` | Mistral | visual semantic QA, narrative/reasoning providers, Voxtral transcription | No | Provider key with model access needed for selected live gates | Required for live qualification using Mistral. |
| `GEMINI_API_KEY` | Google Gemini | reasoning fallback/live provider checks where configured | No | Provider key with selected model access | Optional unless a workflow enables Gemini. |
| `OPENROUTER_API_KEY` | OpenRouter | general compute/reasoning fallback if configured | No | Provider key with selected model access | Optional unless configured. |
| `GROQ_API_KEY` | Groq | general compute/reasoning fallback if configured | No | Provider key with selected model access | Optional unless configured. |
| `OLLAMA_BASE_URL` | Ollama/self-hosted inference | live local/remote Ollama checks only | No | URL to authenticated remote or self-hosted runner endpoint if used | Optional; do not invent `OLLAMA_API_KEY` unless the endpoint requires it. |
| `SAGA_PROTECTED_ASSET_STORAGE_*` | Protected object storage | protected EPUB acquisition workflow | No | Read-only credentials for private asset bucket/prefix | Required only if GitHub Actions runs protected-asset qualification. |

`GITHUB_TOKEN` is provided by GitHub Actions and is used by publish/provenance workflows with workflow-declared permissions.

## Local secrets found during recovery

- `deploy/neo4j/.env` exists locally and includes `NEO4J_PASSWORD`. Neo4j is not currently a documented production dependency for the active S.A.G.A. runtime.
- `deploy/ollama/accounts.local.json` exists locally and contains account `email`, `password`, and `api_key` fields for local Ollama/account-rotation experiments.

These local values were not copied into this document or committed. If any are still required, migrate them through GitHub repository or environment secrets and document the exact consuming workflow first.

## Rotation notes

- Rotate any secret pasted into chat or used from an old local file before relying on it for production.
- Keep Supabase service-role credentials server-side only.
- Prefer short-lived or environment-scoped provider keys for expensive live-provider workflows.
- Remove secrets from GitHub when the owning workflow is removed or moved to a different repository.
