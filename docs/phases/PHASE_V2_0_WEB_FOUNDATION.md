# S.A.G.A. v2 Phase 0 — Web Foundation & Storage Bootstrap

**Status:** ACTIVE — IMPLEMENTED; FINAL CI/PR MERGE REMAINS

**Tracking:** #148

## Goal

Establish a clean, web-first S.A.G.A. v2 foundation that can be developed and deployed independently of the legacy v1 runtime.

This phase is complete when the repository has a validated Next.js application/backend shell, explicit Supabase/storage boundaries, dedicated B2 storage validated through GitHub Actions, and durable governance that makes v1 historical rather than accidentally active.

## Owner Direction

The rebuild preserves S.A.G.A.'s goals/features but intentionally changes architecture.

Development order:

1. main site frontend and backend;
2. application data/auth/storage/job foundation;
3. new agentic AI subsystem;
4. progressive restoration of analysis, canon, generation, visual/audio, and export capabilities.

## Verified Starting Point

Pre-v2 boundary:

- repository: `faresmohamed260/saga`
- `main`: `b689e17bf2b70ea6c2ade0c3795bb85bb048d57b`
- branch: `v2/phase-0-web-foundation`

The v1 recovery/control-plane work is historical evidence. Its remaining qualification work was intentionally abandoned by the owner in favor of this rebuild. Issues #142 and #147 are closed `not_planned`.

## Implemented Phase Work

### Repository/governance reset

Implemented:

- v2 is the active architecture in `PROJECT.md`, `AGENTS.md`, `docs/README.md`, and `docs/DECISIONS.md`;
- pre-v2 runtime/code/docs are classified historical/reference;
- the clean v1 boundary remains available in Git history without becoming a compatibility constraint.

### Web application foundation

`apps/web/` now contains:

- Next.js 16 + React 19 + TypeScript;
- Tailwind CSS and Motion-ready visual foundation;
- initial polished S.A.G.A. product shell;
- `/api/health` integration-status route;
- Supabase SSR server/configuration boundary;
- provider-neutral `ObjectStorage` interface;
- Backblaze B2 S3 runtime adapter that accepts only scoped runtime credentials;
- structural tests preventing bootstrap master credentials and vendor SDK leakage into feature code.

### v2 web CI

`.github/workflows/v2-web-ci.yml` validates:

- dependency install;
- lint;
- typecheck;
- unit/structural tests;
- production Next.js build.

Initial run `34537327565` passed before the final workflow-boundary tests were added. Exact-final-head CI is still required before merge.

### Backblaze B2 bootstrap — VALIDATED

Repository bootstrap secrets:

- `SAGA_B2_KEY_ID`
- `SAGA_B2_MASTER_APPLICATION_KEY`

The first bootstrap run `34537390902` failed at authorization because the manually entered key-id value included surrounding line-break/whitespace formatting. No bucket or object work occurred in that failed run.

The workflow was hardened to normalize surrounding whitespace without printing credentials. Run **`34537566675`** then passed completely:

- B2 account authorization: success;
- dedicated private bucket create/reuse: success;
- smoke object upload: success;
- download: success;
- byte-for-byte `cmp`: success;
- smoke object deletion: success.

Safe validated metadata is committed in `config/v2-storage.json`:

- bucket: `saga-v2-faresmohamed260-1207062480`
- bucket id: `b2af6d676af585d3aa0e0912`
- region: `us-east-005`
- S3 endpoint: `https://s3.us-east-005.backblazeb2.com`
- visibility: private

The temporary branch push trigger used to perform the bootstrap has been removed. `.github/workflows/v2-b2-bootstrap.yml` is now **manual-only**. Structural tests enforce that it has no `push` or `pull_request` trigger and does not publish artifacts.

The master key remains bootstrap-only and is not consumed by `apps/web`. Normal runtime B2 S3 access still requires a later bucket-scoped non-master application key.

## Explicitly Out of Scope

- new agent/LLM orchestration;
- identity/coreference implementation;
- canon extraction;
- generation planning/narrative generation;
- visual/audio model execution;
- importing the old nine-stage orchestration;
- v1 production qualification;
- repairing v1 R2;
- creating or mutating RenderLab/Fares Uniform cloud resources;
- final Supabase schema beyond the minimum boundary needed to scaffold the app;
- final Vercel/Cloudflare domain rollout if the project is not yet connected.

## v2 Architecture Invariants

1. The browser/product is designed around user concepts, not internal AI stages.
2. Supabase owns structured application/domain records.
3. B2 owns large source/media/export objects.
4. Feature/domain code does not instantiate vendor storage SDKs directly.
5. Long-running AI work will later be a job/worker subsystem behind the web application, not a Vercel request pretending to be a worker.
6. v2 must not import legacy Python/runtime code.
7. RenderLab technology patterns may be referenced; RenderLab state/resources remain separate.
8. Secret values never enter repository files, workflow artifacts, issue text, or logs.
9. B2 master credentials are for bounded bootstrap/admin operations only; the web runtime uses a scoped application key.

## Target Initial Product Areas

Phase 0 only establishes the shell, but Phase 1 information architecture should anticipate:

- Home / dashboard
- Library / sources
- Projects / story workspaces
- Chapters / scenes
- Characters / relationships
- Locations / world
- Timeline / events
- Canon / evidence
- Story planning / generation
- Media
- Jobs / activity
- Settings

These labels describe product concepts, not final schema or route commitments.

## Storage Namespace

```text
sources/
artifacts/analysis/
generated/images/
generated/audio/
exports/
temporary/
_system/
```

Object keys should be scoped by application-generated project/source IDs rather than human titles where practical.

## Validation

### Web deterministic gate

From `apps/web`:

```text
npm install --no-audit --no-fund
npm run lint
npm run typecheck
npm run test:unit
npm run build
```

### Storage bootstrap gate — PASSED

Evidence: GitHub Actions run `34537566675`.

The gate proved credential authorization, private bucket availability, smoke upload/download/content comparison/delete, and safe metadata extraction without exposing credentials.

## Remaining Exit Work

Phase 0 now needs only repository-finalization evidence:

1. run v2 CI on the exact final branch head, including workflow-boundary tests;
2. inspect branch diff for secret leakage and accidental v1 coupling;
3. open a focused PR against current `main` and require the applicable repository checks;
4. merge the exact green head;
5. record the merged v2 baseline in `PROJECT.md` if needed;
6. close #148 and start Phase 1.

A scoped B2 runtime key is intentionally a Phase-1 prerequisite for real source upload/read functionality rather than a blocker for the Phase-0 application/storage architecture.

## Phase 1 Direction

After Phase 0, fully specify **Phase 1 — Main Site Frontend & Backend** from the validated v2 foundation.

Do not fully design the agentic AI phase until the application/domain/job contracts are established.