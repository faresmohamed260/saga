# Local-to-GitHub Handoff Inventory

Audit date: 2026-09-10

This inventory records local S.A.G.A. material found outside the current GitHub `main` baseline. It is a migration guide, not an instruction to upload everything.

## Baseline

- Repository: `faresmohamed260/saga`
- Remote `main` audited HEAD: `1d1fa6e9bb86feede9c9f5b89eec828eb15a2050`
- Local checkout audited branch: `codex/transaction-pool-rc36`
- Local checkout audited HEAD: `0294bb260d426e81048dd982dae85e64db3f9318`
- Handoff branch: `recovery/local-to-github-handoff`
- Handoff branch seed: `origin/main` plus PR #133 governance commit `5756e1c66df43594b2c6673a88fb6a330dcc13a1`

## Git divergence

The local branch is not a fast-forward candidate for current `main`.

- `origin/main...HEAD`: 1000 remote-side commits and 43 local-side commits.
- Local branch `codex/transaction-pool-rc36` tracks `origin/codex/transaction-pool-rc36` and is currently at the same commit.
- The local working tree also has uncommitted modified files and untracked files.

Recovery rule: do not force-push or replay the local branch wholesale. Port only durable, reviewed material forward onto current `main`.

## Uncommitted local work

Modified tracked files in the local checkout:

- `README.md`
- `integrations/comfyui/client.py`
- `integrations/comfyui/modal_app.py`
- `integrations/comfyui/pool_manager.py`
- `integrations/comfyui/workspace_client.py`
- `pyproject.toml`

Untracked project-sized surface:

- `apps/studio/`
- `apps/studio_api/`
- `docs/studio/`
- `integrations/comfyui/manifests/`
- `integrations/comfyui/workflows/reference_exports/`
- `migrations/versions/202608210100_studio_schema.py`
- `packages/generation_core/`
- `scripts/start_studio.ps1`
- Studio/generation tests including `tests/test_generation_core_registry.py`, `tests/test_model_downloads.py`, `tests/test_provider_credentials.py`, `tests/test_studio_api.py`, and `tests/test_studio_generation_executor.py`

Classification: unresolved / likely separately owned Studio-generation work. Current S.A.G.A. recovery must not migrate this into S.A.G.A. core by default, especially after the RenderLab split. Preserve as local evidence until a separate surface-ownership decision is made.

## Local commits worth reviewing

The 43 local-side commits contain potentially durable S.A.G.A. core work in these categories:

- source code: reasoning runtime routing/queueing/qualification, production orchestration, usage accounting, visual quality policy, identity review, canon extraction, character/world modeling, deployment runtime;
- tests: local reasoning qualification, routing, visual policy, identity canonicalization, narrative grounding/addressee evaluation, production qualification script updates;
- scripts: local reasoning corpus/gold/scorecard/qualification builders;
- migrations: usage project attribution migration `202608120100_usage_project_attribution.py`;
- documentation: local reasoning qualification/completion audit, vertical-slice qualification, RC38 canon bounded qualification, visual/deployment/runtime updates.

These commits predate substantial later remote work and should be cherry-picked or manually ported only after file-by-file comparison against current `main`.

## Local-only generated and heavyweight material

Do not commit the following classes directly:

- multi-GB SQLite databases under `analysis_outputs/`;
- runtime/database backups under `deploy/production/backups/` and `tmp/`;
- generated audiobook bundles and WAV/MP3 outputs;
- vector indices under `analysis_outputs/vector_indices/`;
- copied artifact restores under `tmp/rc*-artifact-restore/`;
- local caches, virtual environments, `node_modules`, build outputs, and Python bytecode;
- Neo4j plugin JARs and local Neo4j state;
- private/local provider account files.

If any generated evidence is needed, extract compact JSON/Markdown summaries with provenance and checksums.

## Local path dependencies found

Current repository and local material include Windows-only paths, especially:

- local book paths in `configs/acotar_books.json`;
- historical/local validation paths in runtime docs;
- Studio draft docs pointing to a local ComfyUI workspace;
- legacy backup code with local book defaults.

Current operational instructions must use repository-relative paths, environment variables, GitHub Actions workspace paths, or object-storage keys. Historical paths may remain only when explicitly labeled as historical evidence.

## Secret-bearing local files

Local files with credential fields exist and must never be committed with values:

- `deploy/neo4j/.env`: includes `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, and local port/memory settings.
- `deploy/ollama/accounts.local.json`: contains 18 account records with `email`, `password`, `api_key`, `auth_mode`, `account_id`, and active/index metadata.

The values were not copied into this repository. Required secret names and destinations are documented in `docs/operations/GITHUB_ACTIONS_SECRETS.md`.

## Protected assets and datasets

Commercial EPUBs are present or referenced locally for validation. They must not be committed to this public repository unless redistribution is explicitly permitted. Metadata and secure acquisition rules are documented in `docs/operations/PROTECTED_TEST_ASSETS.md`.

Small derived JSON fixtures under `tests/fixtures/` are source-controlled candidates only when they contain no copyrighted book text beyond fair-use test snippets and no secrets.

## Reconciliation decisions

- PR #133 governance docs were reused by cherry-pick instead of recreated.
- Studio/generation local work is inventoried but not migrated into S.A.G.A. core in this handoff commit.
- Heavy generated outputs and databases are excluded from Git migration.
- Local credential-bearing files are inventoried by variable/field name only.
- Protected book assets are represented by filename/hash/purpose/storage policy, not by file contents.

## Immediate follow-up

1. Port durable core changes from the 43 local commits only after comparing each affected file against current `main`.
2. Decide whether Studio remains in S.A.G.A., becomes historical, or is fully externalized to RenderLab.
3. Configure GitHub Actions secrets listed in `docs/operations/GITHUB_ACTIONS_SECRETS.md`.
4. Run the non-live validation gates from `docs/validation/REPRODUCIBILITY.md` on the handoff branch.
