# Contributing

S.A.G.A. is developed contract-first and measurement-first. Keep `main` reviewable and releasable, and do not promote experimental analysis behavior into product truth without qualification evidence.

## Before substantial work

Read, in order:

1. [`AGENTS.md`](AGENTS.md)
2. [`PROJECT.md`](PROJECT.md)
3. [`docs/README.md`](docs/README.md)
4. [`docs/DECISIONS.md`](docs/DECISIONS.md)
5. the active phase contract and relevant v2 architecture/validation documents

GitHub history is authoritative for exact merge state. Do not reconstruct current status from stale chat/history notes when the repository can establish it.

## Choose the correct surface

- `apps/web` — **current v2 web product surface** and default location for new v2 frontend/product work.
- `services/analysis-worker` — current durable analysis-worker/control-plane work.
- `packages` — reusable v2/shared domain and runtime packages.
- `integrations` — bounded provider implementations behind explicit contracts.
- `apps/dashboard_api` and `apps/dashboard_pro` — retained earlier application surfaces; do not use them for new v2 frontend work unless an active issue explicitly scopes work there.
- `backup/reference` — historical/reference material; non-authoritative.

## Workflow

1. Open or assign a GitHub issue when the change is substantial or changes behavior/contracts.
2. Branch from current `main` using a descriptive prefix such as `feat/`, `fix/`, `docs/`, `test/`, or the active phase convention.
3. Open a draft pull request early for multi-step work and link the relevant issue/contract.
4. Keep scope bounded. Architectural/provider adoption changes must name their validation plan.
5. Run the relevant model-light checks locally.
6. For visible UI changes, verify the rendered result and attach screenshots to the PR when useful.
7. Wait for required CI/review before merging.
8. Update the owning documentation when verified project state changes.

## Model-light checks

### Python/backend

```bash
python -m pip install -e ".[dev]"
pytest
```

Use the more specific typecheck/test commands required by the active package or phase contract when applicable.

### Current v2 web application

Install exactly from the web lockfile and run the same gates as `v2-web-ci.yml`:

```bash
npm --prefix apps/web ci
npm --prefix apps/web run lint
npm --prefix apps/web run typecheck
npm --prefix apps/web run test:unit
npm --prefix apps/web run build
```

The web production build should not require live Supabase/B2 credentials. Integration-dependent functionality may require `apps/web/.env.local` at runtime; never commit secrets.

## Heavyweight qualification

Large local models, protected fiction corpora, and whole-book benchmarks are intentionally outside normal CI.

When a change affects model-backed analysis:

- use the dedicated qualification path named by the active contract;
- record exact versions/configuration/fingerprints where required;
- distinguish correctness metrics from coverage/failure-mode diagnostics;
- include resource measurements when provider selection depends on them;
- keep copyrighted source text and protected assets out of Git/public artifacts;
- do not treat a successful experiment as production adoption unless the owning decision/scorecard says so.

## Review policy

- `main` should stay releasable.
- Required CI should be green before merge unless a documented repository policy explicitly allows otherwise.
- Prefer focused PRs with a clear behavioral/contract boundary.
- Preserve provenance, authorization, deterministic identifiers, and failure semantics when changing provider integrations.
- New or changed claims in public docs must reflect measured repository reality.
- Do not silently broaden experimental behavior to improve headline coverage metrics.

## Documentation changes

Avoid copying volatile current-state details into multiple overview documents.

- Root `README.md` owns the stable public overview.
- `PROJECT.md` owns the current high-level handoff.
- `docs/README.md` owns documentation navigation.
- Decision/phase/validation/experiment files own their respective detailed truth.

If a PR materially changes project status, update the owning source rather than creating another competing status summary.

## Pairing and authorship

When multiple contributors author a change, use Git/GitHub co-author attribution as appropriate. Keep authorship information accurate; do not add a co-author who did not contribute to the commit.

## Ownership

Repository review ownership is defined in [`.github/CODEOWNERS`](.github/CODEOWNERS). Current v2 work should route to the owners for the active path being changed.
