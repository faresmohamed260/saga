# S.A.G.A. Local-to-GitHub Handoff Report — 2026-09-10

This report is the durable handoff record for the one-time local-to-GitHub recovery.

## Git

| Item | Evidence |
| --- | --- |
| Repository | `faresmohamed260/saga` |
| Original audited remote `main` SHA | `1d1fa6e9bb86feede9c9f5b89eec828eb15a2050` |
| Original audited local branch/SHA | `codex/transaction-pool-rc36` / `0294bb260d426e81048dd982dae85e64db3f9318` |
| Divergence | 1000 remote-side commits and 43 local-side commits from `origin/main...HEAD` at audit time |
| Governance/recovery PR | PR #134, merged 2026-09-10 |
| Post-PR #134 `main` SHA | `6e02c0e720d9b871c27921aa9ba010bb2921fa3b` |
| Local commit triage PR | PR #135, merged 2026-09-10 |
| Post-PR #135 `main` SHA | `8d81639c56fc3a1df27de16e8819e414fec2d0eb` |
| Duplicate governance PR | PR #133 closed as superseded by PR #134 |
| Remaining open local-history PR | PR #54 remains draft/historical evidence; do not merge as-is |

## Migrated to GitHub

- Repository-first AI/session governance.
- Current project handoff and Phase 0 recovery contract.
- Documentation index and durable decisions register.
- Local workspace inventory and reconciliation decisions.
- Commit-by-commit triage of the 43 divergent local commits.
- Reproducibility matrix covering deterministic, integration, and expensive/live gates.
- GitHub Actions secrets manifest without secret values.
- Protected asset manifest with filenames, purposes, and SHA-256 values.
- Model/provider manifest without model weights.
- Placeholder-only protected asset env names.
- Local and GitHub validation evidence for deterministic recovery gates.

## Not migrated

- Secret values from local files or chat.
- Commercial EPUB/PDF/book files.
- Multi-GB SQLite databases and backups.
- Generated audiobook/image/runtime artifacts.
- Vector index caches.
- Local virtual environments, caches, `node_modules`, and build outputs.
- Local Neo4j plugin/state.
- Untracked Studio/generation-core local subtree.
- Model checkpoints, LoRAs, GGUFs, ONNX files, or other weights.

## Secrets

Repository secret names observed on 2026-09-10:

| Secret | Destination | Migration status |
| --- | --- | --- |
| `CIVITAI_API_TOKEN` | GitHub repository secret | Present |
| `HF_TOKEN` | GitHub repository secret | Present |
| `SAGA_MODAL_TOKENS_JSON` | GitHub repository secret | Present |
| `R2_ACCOUNT_ID` | GitHub repository secret | Present |
| `R2_BUCKET_NAME` | GitHub repository secret | Present |
| `R2_ACCESS_KEY_ID` | GitHub repository secret | Present |
| `R2_SECRET_ACCESS_KEY` | GitHub repository secret | Present |
| `SUPABASE_URL` | GitHub repository secret | Present |
| `SUPABASE_SERVICE_ROLE_KEY` | GitHub repository secret | Present |
| `SATURN_TOKEN` | GitHub repository secret | Present, owner/use still requires audit |
| `MISTRAL_API_KEY` | GitHub repository/environment secret | Not observed |
| `GEMINI_API_KEY` | GitHub repository/environment secret | Not observed |
| `OPENROUTER_API_KEY` | GitHub repository/environment secret | Not observed |
| `GROQ_API_KEY` | GitHub repository/environment secret | Not observed |
| `SAGA_SUPABASE_DB_URL` or component DB secrets | GitHub repository/environment secret | Not observed |
| `SAGA_PROTECTED_ASSET_STORAGE_*` | GitHub repository/environment secret | Not observed; existing R2 secrets are now used by the manual protected-asset verification workflow |

No secret values were written to repository files.

## Protected assets

| Filename | SHA-256 | Storage mechanism | Workflow status |
| --- | --- | --- | --- |
| `Once Upon a Broken Heart.epub` | `89F8E1A7DD808A8D40280608F5499F520FDF16AA01206F7A5F62AFED9247B7A5` | Private authorized object storage only | Metadata migrated; manual R2 hash-verification workflow added |
| `The Lost Sisters.epub` | `38AC0F672B820EB3D9347BA4587FDE9AD1859F87C46434561D253D391F46AF90` | Private authorized object storage only | Metadata migrated; manual R2 hash-verification workflow added |
| `A Court of Thorns and Roses.epub` | `FAFCB0E4420BA70C6E1F78749882CBFF2E3B6D2207A62305F10F9996A1033BCF` | Private authorized object storage only | Metadata migrated; manual R2 hash-verification workflow added |
| `A Court of Mist and Fury.epub` | `10A2CBB71FFEA040CEA51BCC2D6D20F1602B3D3BD731F0436022F5C82A194FBB` | Private authorized object storage only | Metadata migrated; manual R2 hash-verification workflow added |
| `A Court of Wings and Ruin.epub` | `4D8D79FE1B0B3DF3F01F335BB79C78D41CBD8B1765280E820A657CBFD1FB7A0F` | Private authorized object storage only | Metadata migrated; manual R2 hash-verification workflow added |
| `A Court of Frost and Starlight.epub` | `5A02FA8D59425B265A86D022BED9025D3BA3B29E30D892D777300B7758812FB3` | Private authorized object storage only | Metadata migrated; manual R2 hash-verification workflow added |
| `A Court of Silver Flames.epub` | `D1A17DFE07AFBA50097519A3267099B75EFEFDB2056B53E2901D6935AB905E60` | Private authorized object storage only | Metadata migrated; manual R2 hash-verification workflow added |

## CI and validation

Local validation on clean recovery worktree:

- `uv sync --frozen --extra dev` — passed.
- `uv run alembic heads` — one head, `202608090400`.
- `uv run python -m scripts.check_source_secrets` — passed.
- `uv run pytest -q tests/test_architecture_boundaries.py` — passed.
- `uv run pytest -q` — passed, 338 passed / 3 skipped / 1 warning.
- Dashboard Pro install/test/build — passed, 13 tests and production Vite build.
- Dashboard production dependency audit — passed, 0 high production vulnerabilities.
- Production Compose config validation — passed.

GitHub validation:

- PR #134 final head `8685f97cec6cca81c2a19536cbe0ab6057d7323c` — Backend Architecture CI `test`, `migrations`, `containers`; Required Check Compatibility; Vercel; Vercel Preview Comments all passed.
- PR #135 head `729b8f0f8db29d081db74487f80c937e0a0f1bfe` — Backend Architecture CI `test`, `migrations`, `containers`; Required Check Compatibility; Vercel; Vercel Preview Comments all passed.

CI emitted Node.js 20 deprecation annotations for some actions forced onto Node.js 24. This is maintenance work, not a current gate failure.

## Remaining local dependencies

The repository no longer depends on undocumented local knowledge for the recovery inventory, secret names, protected asset metadata, validation tiers, or divergent local commit classification.

Remaining unresolved dependencies/blockers:

- Live-provider qualification still requires configured provider secrets and cost-controlled execution.
- Protected-asset qualification now has a manual R2 hash-verification workflow, but production qualification still requires authorized objects and the live qualification workflow to consume them.
- Some local-side code/evidence may still be valuable, but it must be ported through focused PRs from `docs/recovery/LOCAL_COMMIT_TRIAGE.md`.
- Studio product ownership is assigned to `faresmohamed260/renderlab` going forward. S.A.G.A. still needs a focused cleanup/deprecation PR before deleting or relocating existing Studio files.
- `SATURN_TOKEN` exists as a repository secret but its current owning workflow/service was not identified in this recovery pass.

## Final recovery state

GitHub is now the durable source of truth for the handoff/recovery evidence completed in this pass. Phase 0 remains active until live/provider/protected-asset qualification and any selected focused local-code ports are handled or accepted as explicit blockers.
