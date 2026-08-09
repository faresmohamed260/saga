**Analysis Foundation Runtime**

Active production slice for book ingestion, scene segmentation, and Modal-backed identity resolution.

**Active surfaces**

- Package runtime: `packages/analysis_foundation`
- LangGraph surface: `packages/agent_runtime/analysis_foundation.py`
- Bootstrap script: `scripts/bootstrap_analysis_foundation_runtime.py`
- Runner script: `scripts/run_analysis_foundation.py`

**Required env**

- `SAGA_RUNTIME_DB_URL`
- `SAGA_RUNTIME_DB_MODE=supabase_postgres`
- `SAGA_SUPABASE_API_URL`
- `SAGA_SUPABASE_SERVICE_ROLE_KEY`

Optional:

- `SAGA_SUPABASE_URL`
- `SAGA_RUNTIME_LOCAL_STORAGE_ROOT`
- `SAGA_ANALYSIS_IDENTITY_PROVIDER`
- `SAGA_ANALYSIS_IDENTITY_TIMEOUT_SECONDS`

**Identity provider prerequisites**

- Provider config must exist in active persistence under `modal_xcore_litbank`
- App name must point to the active Modal coref runtime, currently `saga-coref-runtime`
- Modal account tokens remain stored in provider config persistence, not in the runner
- Runtime state and provider config use the same persistence env contract

**Bootstrap**

Use this to seed or refresh the active provider config summary without touching legacy code:

```powershell
venv\Scripts\python.exe scripts\bootstrap_analysis_foundation_runtime.py `
  --provider-name modal_xcore_litbank `
  --app-name saga-coref-runtime
```

Optional flags:

- `--accounts-json`
- `--api-url`
- `--health-url`
- `--ui-url`
- `--hf-token`
- `--request-timeout-seconds`

**Run**

```powershell
venv\Scripts\python.exe scripts\run_analysis_foundation.py `
  --series-id real-holly-black-lost-sisters `
  --thread-id lost-sisters-live `
  --source "D:\Books\Ebooks\Holly Black\The Lost Sisters\The Lost Sisters.epub" `
  --output-json "tmp_live_analysis_foundation\lost_sisters.json"
```

The runner:

- executes the LangGraph-native analysis runtime
- persists source, books, chapters, scenes, identity bundle, and runtime report
- emits a quality audit and timing metadata

**Current hardening behavior**

- EPUB ingestion prefers metadata title and TOC titles when available
- front matter and promo appendix pages are filtered out
- chapter extraction is deterministic
- stage timings are recorded in `run_metadata`
- identity must resolve through `modal_xcore_litbank`
- identity clusters are reviewed through `packages.identity_runtime.review_identity_clusters()`
- reviewed identity output persists:
  - `identity_kept_cluster_count`
  - `identity_dropped_cluster_count`
  - `identity_accepted_alias_count`
  - `identity_rejected_alias_count`
- full identity review diagnostics persist in `identity_bundle.metadata.identity_review`
- runtime reports are stored under `runtime-reports`

**Identity grounding review**

The upstream identity contamination filter lives in `packages/identity_runtime`, not in downstream consumers.

The review pass:

- rejects cross-character alias bleed such as one canonical name being claimed as another cluster alias
- rejects narrator/pronoun pollution like `I`, `you`, `my`, and related unstable surface forms
- rejects generic-role aliases and cluster names such as `my sister`, `the prince`, `the children`
- rejects malformed span captures that do not look like stable names
- retains grounded named aliases such as `Cardan` for `Prince Cardan`

Diagnostic codes currently surfaced:

- `ambiguous_alias_rejected`
- `cross_character_alias_rejected`
- `generic_or_non_character_cluster`
- `generic_role_alias_rejected`
- `malformed_alias_rejected`
- `missing_display_name`

**Validation expectations**

- verify `identity_provider_name == modal_xcore_litbank`
- verify `identity_model_name` is populated from live Modal response
- verify `title_quality`, `chapter_quality`, `scene_quality`, and `identity_quality`
- verify `identity_quality.review_diagnostic_codes`
- verify `identity_quality.review_rejected_alias_count`
- verify persisted records exist for:
  - source documents
  - books
  - chapters
  - scenes
  - identity bundle
  - runtime report

**Latest real validation snapshot**

- Book: `D:\Books\Ebooks\Holly Black\The Lost Sisters\The Lost Sisters.epub`
- Series: `real-holly-black-lost-sisters-v9`
- Identity provider: `modal_xcore_litbank`
- Model: `sapienzanlp/xcore-litbank`
- Stage timings:
  - ingestion: `0.7535s`
  - scene segmentation: `0.3320s`
  - identity: `12.7130s`
- Review totals:
  - kept clusters: `29`
  - dropped clusters: `42`
  - rejected aliases: `86`

Observed cleanup on the live bundle:

- `Jude`: aliases `[]`, pronouns `[]`
- `Heather`: aliases `[]`, pronouns `[]`
- `Vivi`: aliases `[]`, pronouns `[]`
- `Prince Cardan`: aliases `["Cardan"]`
- final kept identity set reduced to `18` character records after downstream merge
- removed prior contamination patterns seen in earlier Holly Black runs such as:
  - `Prince Cardan -> Locke`
  - `Vivi -> Taryn`
  - `Mr. Fox -> Locke`
  - narrator-style aliases like `my sister`, `your sister`, `this Heather`
  - obvious non-character clusters like `Faerie`, `Revelers in rags`, `The fiddler`

**Known remaining risk**

- Identity quality still depends on upstream xcore cluster quality, so difficult books can still produce noisy raw clusters before review.
- The active review pass now strips the main contamination patterns upstream, but downstream semantic quality can still vary based on reasoning-model extraction quality even when identity bundles are clean.
- Current downstream validation still shows some narrator-level semantic confusion in canon/modeling outputs, but that is now separate from identity-cluster contamination and should be addressed in downstream reasoning slices rather than pushed back into identity.
