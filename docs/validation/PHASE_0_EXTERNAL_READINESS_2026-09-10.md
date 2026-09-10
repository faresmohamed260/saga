# Phase 0 External Readiness Diagnostic — 2026-09-10

This record preserves the bounded, non-paid external-readiness evidence collected after PR #145 merged. It exists so future sessions do not repeat ambiguous provider/storage probes or mistake legacy connected infrastructure for S.A.G.A. production.

## Source baseline

- Repository: `faresmohamed260/saga`
- `main` commit under test: `67e852116af2efea9484daa6ddb343397c5322a9`
- tree: `f5cf499f280fbc2fb12c7e1a1bcafeb8577833b9`
- commit: `Add clean-source production qualification workflow (#145)`
- PR #145 final head: `8b00e732bfeda213b77dc77a44ebc60fabc46a8e`
- PR #145 exact-head Required Check Compatibility: success
- PR #145 exact-head Backend Architecture CI: success
- post-merge `main` Required Check Compatibility run `34509072301`: success
- post-merge `main` Backend Architecture CI run `34509072302`: success
- the paid/live `Clean-Source Production Qualification` workflow did **not** auto-run after merge.

## Diagnostic safety boundary

The temporary branch `phase-0/external-readiness-diagnostic` was created only to allow same-repository GitHub Actions to read repository secret/variable presence and exercise the bounded storage helper.

The diagnostic:

- did not run `scripts.run_production_qualification`;
- did not call paid reasoning, visual-generation, or audio providers;
- did not upload workflow artifacts;
- did not print secret values, bucket names, account identifiers, object listings, protected filenames beyond committed manifest metadata, or protected bytes;
- used read-only production-persistence checks when configuration was available;
- used bounded R2 List/Get/hash behavior only;
- removed temporary protected bytes;
- was removed from the temporary branch after evidence collection and must not be merged to `main`.

Diagnostic runs:

- `34514215596` — initial configuration/readiness probe;
- `34514460132` — safe bounded-result logging and R2 jurisdiction probe.

## GitHub Actions configuration presence

The diagnostic established only whether relevant values were populated; no values were printed.

| Configuration | Presence |
| --- | --- |
| `SAGA_SUPABASE_DB_URL` | absent |
| `SAGA_SUPABASE_DB_HOST` | absent |
| complete S.A.G.A. component DB configuration | absent |
| legacy `SUPABASE_URL` | present |
| legacy `SUPABASE_SERVICE_ROLE_KEY` | present |
| `OLLAMA_API_KEY` | absent |
| `MISTRAL_API_KEY` | absent |
| `SAGA_PROVIDER_COST_RATES_JSON` | absent |
| R2 account/bucket/access-key/secret variable names | present |

The production-persistence probe therefore returned:

```text
PRODUCTION_DB_RESULT status=not_configured
```

Consequences:

- source freshness cannot currently be proven from GitHub Actions;
- persisted Modal provider rows cannot be inspected through the qualification preflight;
- persisted Ollama/Mistral readiness cannot be established;
- the current clean-source qualifier cannot pass its production-persistence gate;
- the cost-accounting gate cannot pass until legitimate versioned provider rates are configured.

## Connected Supabase project is not S.A.G.A. production

The Supabase connector exposed one project named `AI Studio`. A read-only table inventory showed RenderLab/retired-Studio schema, including:

- `generation_*`;
- `media_*`;
- `renderlab_*`;
- `studio_*`.

No S.A.G.A. production-library schema was identified there. That project was left untouched and must not be used to infer S.A.G.A. source freshness or qualification readiness.

## Protected R2 result

Run `34514460132` exercised `scripts/check_protected_asset_storage.py` with the existing repository R2 configuration across every supported Cloudflare R2 jurisdiction endpoint.

| Jurisdiction | Result |
| --- | --- |
| `default` | `access_failed` |
| `eu` | `access_failed` |
| `us` | `access_failed` |
| `fedramp` | `access_failed` |

Aggregate result:

```text
R2_PROBE_RESULT status=no_accessible_jurisdiction
```

The helper fails at bounded bucket listing for every endpoint. Therefore the current evidence supports an **account/bucket/credential/token-scope access blocker**. It does **not** support an `object_missing` conclusion for any protected manifest asset. Asset-level download/hash verification was correctly skipped because no jurisdiction demonstrated bucket-list access.

## R2 configuration namespace provenance

Historical source at pre-Studio-retirement commit `1944ea3a1c7d6733236869cec2e030dad4fdd470` shows that `apps/studio/api/_r2.js` consumed the exact same environment-variable names:

- `R2_ACCOUNT_ID`;
- `R2_BUCKET_NAME`;
- `R2_ACCESS_KEY_ID`;
- `R2_SECRET_ACCESS_KEY`.

The Studio helper also defaulted its bucket name to `saga-studio-media`.

This proves the **configuration namespace was used by the retired Studio product**. GitHub does not expose repository secret values, so this does not prove that the current secret values are the historical Studio values. Presence of these names alone must therefore not be treated as evidence that they point to a S.A.G.A.-owned protected-book bucket.

## Required repair before qualification

1. Configure the actual S.A.G.A. production Postgres/Supabase path for GitHub Actions using `SAGA_SUPABASE_DB_URL` or complete explicit remote component DB configuration.
2. Preserve the required Supabase API/service-role server-side aliases for the same S.A.G.A. project.
3. Configure legitimate, versioned `SAGA_PROVIDER_COST_RATES_JSON` provider-wide fallbacks for `ollama`, `mistral`, and `modal`; do not invent pricing.
4. Ensure the real S.A.G.A. persistence contains qualification-ready `modal_xcore_litbank`, `modal_comfyui`, and `modal_kokoro_tts` credentials plus a usable Ollama key and Mistral access.
5. Reconfigure or rotate the R2 repository credentials so they explicitly target a S.A.G.A.-owned private protected-assets bucket/prefix with List/Get access.
6. Re-run `Protected Asset Verification`; require successful bucket access before classifying individual object presence.
7. Once production persistence is available, select a manifest asset that passes the filename/SHA freshness preflight. If every listed asset is already present, add metadata for another authorized unseen source and store only its bytes privately.
8. Require successful private download plus committed SHA-256 verification.
9. Only then separately authorize the paid/live `Clean-Source Production Qualification` from exact `main` with `confirm_live_cost=true`.

## Phase interpretation

Phase 0 repository recovery and the qualification control plane are implemented and CI-validated. Phase 0 is **not complete** because external production configuration and a fresh protected qualification source remain unresolved.

Issue #142 is the authoritative open blocker for the protected-source side. No paid qualification should be run until the prerequisites above are satisfied.