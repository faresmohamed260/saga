# GitHub Actions Secrets Manifest

This file documents required secret/variable names and destinations. It must never contain secret values.

Observed presence/status below is evidence from 2026-09-10 only. Presence is not proof that a credential points to the correct S.A.G.A. resource or has sufficient permissions. Detailed bounded evidence: `../validation/PHASE_0_EXTERNAL_READINESS_2026-09-10.md`.

## Repository secrets

| Secret | Owning service | Used by | Required for normal CI | Scope / permissions | Current qualification status |
| --- | --- | --- | --- | --- | --- |
| `SAGA_MODAL_TOKENS_JSON` | Modal | Modal worker inventory/provision/maintenance/live-smoke workflows | No | JSON roster of Modal accounts | Previously observed present. Clean-source qualification intentionally prefers persisted provider rows. |
| `HF_TOKEN` | Hugging Face | Modal worker/model provisioning | No | Read access to required model files | Previously observed present; not a clean-source preflight substitute for persisted provider readiness. |
| `CIVITAI_API_TOKEN` | Civitai | Modal worker/model provisioning | No | Read/download access to selected model files | Previously observed present. |
| `SAGA_SUPABASE_DB_URL` | S.A.G.A. production Postgres | clean-source qualification / real runtime validation | No | Production application/pooler database URL | **Absent in bounded Actions diagnostic on 2026-09-10.** |
| `SAGA_SUPABASE_DB_HOST` | S.A.G.A. production Postgres | component DB configuration | No | Explicit remote database/pooler hostname | **Absent in bounded Actions diagnostic.** |
| `SAGA_SUPABASE_DB_PORT` | S.A.G.A. production Postgres | component DB configuration | No | Port | No usable complete component DB contract was available. |
| `SAGA_SUPABASE_DB_NAME` | S.A.G.A. production Postgres | component DB configuration | No | Database name | No usable complete component DB contract was available. |
| `SAGA_SUPABASE_DB_USER` | S.A.G.A. production Postgres | component DB configuration | No | Least-privilege DB user | No usable complete component DB contract was available. |
| `SAGA_SUPABASE_DB_PASSWORD` | S.A.G.A. production Postgres | component DB configuration | No | DB password | No usable complete component DB contract was available. |
| `SAGA_SUPABASE_POOLER_TENANT_ID` | S.A.G.A. production Postgres | component pooler configuration | No | Project/tenant identifier | No usable complete component DB contract was available. |
| `SAGA_SUPABASE_API_URL` or `SUPABASE_URL` | Supabase API/Storage | runtime storage / qualification | No | API URL for the **same S.A.G.A. production project** | Legacy `SUPABASE_URL` was present; S.A.G.A.-prefixed alias was not observed. Presence alone is not ownership proof. |
| `SAGA_SUPABASE_SERVICE_ROLE_KEY` or `SUPABASE_SERVICE_ROLE_KEY` | Supabase | server-side runtime/qualification | No | Service-role key for the **same S.A.G.A. production project** | Legacy `SUPABASE_SERVICE_ROLE_KEY` was present; S.A.G.A.-prefixed alias was not observed. Presence alone is not ownership proof. |
| `OLLAMA_API_KEY` | Ollama cloud | optional qualification/runtime authentication fallback | No | API key for authenticated remote Ollama | **Absent** in bounded Actions diagnostic. Persisted S.A.G.A. provider configuration remains the preferred path but cannot be inspected until the real DB is connected. |
| `MISTRAL_API_KEY` | Mistral | qualification fallback for current reasoning/vision/transcription stages | No | Provider key with required model access | **Absent** in bounded Actions diagnostic. Persisted Mistral remains acceptable but currently uninspectable without the real S.A.G.A. DB. |
| `GEMINI_API_KEY` | Google Gemini | optional reasoning fallback/live checks | No | Provider key with selected model access | Optional unless configured by an owning workflow. |
| `OPENROUTER_API_KEY` | OpenRouter | optional general-compute fallback | No | Provider key | Optional unless configured. |
| `GROQ_API_KEY` | Groq | optional general-compute fallback | No | Provider key | Optional unless configured. |
| `OLLAMA_BASE_URL` | Ollama/self-hosted inference | separately documented live/self-hosted checks | No | Remote/self-hosted endpoint | A GitHub-hosted clean qualification must not assume workstation-local Ollama. |
| `R2_ACCOUNT_ID` | Cloudflare R2 | protected-asset verification / qualification acquisition | No | Account identifier for a S.A.G.A.-owned protected-assets bucket | Name/value presence observed, but **current credentials cannot list the configured bucket on any supported jurisdiction endpoint**. |
| `R2_BUCKET_NAME` | Cloudflare R2 | protected-asset verification / qualification acquisition | No | S.A.G.A.-owned private protected-assets bucket | Name/value presence observed, but target ownership/readability is not established. |
| `R2_ACCESS_KEY_ID` | Cloudflare R2 | protected-asset verification / qualification acquisition | No | List/Get on protected-assets bucket/prefix | Name/value presence observed; current bounded probe returns `access_failed` before object diagnosis. |
| `R2_SECRET_ACCESS_KEY` | Cloudflare R2 | protected-asset verification / qualification acquisition | No | Secret half of R2 credential | Name/value presence observed; current bounded probe returns `access_failed` before object diagnosis. |
| `SAGA_PROTECTED_ASSET_STORAGE_*` | future provider-neutral storage | future abstraction if adopted | No | Read-only protected asset credentials | Not the current workflow contract. |
| `SATURN_TOKEN` | Saturn/integration-specific | ownership unclear | No | Inspect owning workflow before use | Present during recovery audit; unrelated to current qualification until an owning contract says otherwise. |

`GITHUB_TOKEN` is provided by GitHub Actions and is used only according to workflow-declared permissions.

## Repository / Actions variables

| Variable | Used by | Requirement | Current status |
| --- | --- | --- | --- |
| `SAGA_PROVIDER_COST_RATES_JSON` | `.github/workflows/production-qualification.yml`, usage governance | Required for clean-source qualification | **Absent in bounded Actions diagnostic on 2026-09-10.** Must contain legitimate versioned provider-wide fallback `CostRate` entries for `ollama`, `mistral`, and `modal`; do not fabricate prices. |

The checked-in production example may use an empty placeholder, but `[]` is not qualification-ready because the evaluator rejects unpriced charges.

## Current production-persistence boundary

The clean-source qualification preflight requires the actual S.A.G.A. production persistence path. On 2026-09-10 the bounded diagnostic returned:

```text
PRODUCTION_DB_RESULT status=not_configured
```

The only project visible through the connected Supabase app was inspected read-only and contained RenderLab/retired-Studio tables (`generation_*`, `media_*`, `renderlab_*`, `studio_*`). It is **not** S.A.G.A. production and must not be used for S.A.G.A. source-freshness or persisted-provider claims.

Until the real S.A.G.A. database path is configured, these required persisted qualification providers remain **unknown**, not failed:

- `modal_xcore_litbank`;
- `modal_comfyui`;
- `modal_kokoro_tts`;
- Ollama/gpt-oss accounts;
- Mistral provider configuration.

## R2 namespace ownership warning

Historical source at pre-retirement commit `1944ea3a1c7d6733236869cec2e030dad4fdd470` shows retired `apps/studio/api/_r2.js` consumed the exact names:

- `R2_ACCOUNT_ID`;
- `R2_BUCKET_NAME`;
- `R2_ACCESS_KEY_ID`;
- `R2_SECRET_ACCESS_KEY`.

That helper defaulted its bucket to `saga-studio-media`.

This proves the **environment-variable namespace was Studio-era infrastructure**. It does not prove current GitHub secret values are identical, because GitHub does not expose values. Therefore these generic `R2_*` names should be reconfigured/rotated with explicit S.A.G.A. protected-asset ownership before qualification rather than trusted based on presence alone.

Read-only diagnostic run `34514460132` returned `access_failed` for `default`, `eu`, `us`, and `fedramp`. No supported endpoint demonstrated bucket listing, so object presence/hash is not yet classifiable.

## Rotation / repair notes

- Configure `SAGA_SUPABASE_DB_URL` or a complete explicit remote S.A.G.A. component DB contract before any live qualification attempt.
- Ensure Supabase API URL/service-role aliases belong to the same S.A.G.A. production project as the DB.
- Configure legitimate versioned pricing before provider calls.
- Prefer persisted provider configuration; env fallbacks are explicit alternatives, not a reason to bypass persistence ownership.
- Reconfigure/rotate R2 credentials to a S.A.G.A.-owned protected-assets bucket/prefix with List/Get access.
- Keep Supabase service-role and provider credentials server-side only.
- Remove secrets when their owning workflow/product is retired.
- Do not enable environment fallbacks merely to bypass missing persisted qualification state.
- Do not make GitHub-hosted qualification depend on developer-workstation localhost services.