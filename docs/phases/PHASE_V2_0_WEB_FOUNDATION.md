# S.A.G.A. v2 Phase 0 — Web Foundation & Storage Bootstrap

**Status:** ACTIVE

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

The v1 recovery/control-plane work is complete enough to serve as historical evidence. Its remaining external qualification work was intentionally abandoned by the owner in favor of this rebuild. Issues #142 and #147 are closed `not_planned` for that reason.

## In Scope

### Repository/governance reset

- make v2 the active architecture in `PROJECT.md`, `AGENTS.md`, `docs/README.md`, and `docs/DECISIONS.md`;
- classify pre-v2 runtime/code/docs as historical/reference;
- preserve the v1 boundary in Git history rather than requiring compatibility in v2.

### Web application foundation

Create `apps/web/` with:

- Next.js 16;
- React 19;
- TypeScript;
- Tailwind CSS;
- maintained component primitives and Motion-ready styling;
- feature/server/lib organization modeled on successful Studio/RenderLab engineering conventions;
- initial product shell suitable for continued UI development;
- health/API route;
- environment helpers;
- Supabase server boundary;
- provider-neutral object-storage contract;
- B2 S3 implementation ready for a future scoped runtime key.

### CI

Add v2-specific GitHub Actions validation for:

- dependency install;
- lint;
- typecheck;
- unit/structural tests;
- production Next.js build.

CI for v2 must be distinguishable from legacy Python gates.

### Backblaze B2 bootstrap

Repository secrets already provided manually:

- `SAGA_B2_KEY_ID`
- `SAGA_B2_MASTER_APPLICATION_KEY`

The bootstrap path must:

- run through GitHub Actions;
- authenticate without printing credential values;
- create/reuse a uniquely named private S.A.G.A. bucket;
- upload, download, checksum/byte-compare, and delete a small `_system/` smoke object;
- report only safe bucket/account endpoint metadata;
- preserve no protected/source data in the bootstrap test;
- leave the long-term workflow manual-only after initial setup.

The master key is bootstrap-only and must not be used by the web runtime. Backblaze's S3-compatible API requires a non-master application key.

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

## Target Initial Product Areas

Phase 0 only establishes the shell, but the navigation/information architecture should anticipate:

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

Initial B2 namespace convention:

```text
sources/
artifacts/analysis/
generated/images/
generated/audio/
exports/
temporary/
_system/
```

Object keys must later be scoped by project/source IDs rather than human titles where practical.

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

### Storage bootstrap gate

A GitHub Actions run must prove:

- bootstrap secrets are present;
- B2 account authorization succeeds;
- dedicated private bucket exists/is created;
- small smoke object upload succeeds;
- downloaded bytes match;
- smoke object cleanup succeeds;
- safe bucket ID/name/S3 endpoint can be recorded without credential disclosure.

## Exit Criteria

Phase 0 closes when:

1. governance points new sessions to v2;
2. v1 is explicitly historical/reference;
3. `apps/web` exists and is the active product surface;
4. v2 CI passes on the exact final PR head;
5. web production build succeeds without requiring live provider credentials;
6. Supabase and storage server boundaries exist without direct vendor coupling in feature code;
7. a dedicated private B2 bucket is created/reused and passes smoke validation;
8. safe B2 bucket/endpoint metadata is committed to the v2 configuration/docs;
9. master credentials remain bootstrap-only;
10. `PROJECT.md` is updated with the exact merged v2 baseline and Phase 1 next step.

## Phase 1 Direction

After Phase 0, fully specify **Phase 1 — Main Site Frontend & Backend** from the validated v2 foundation.

Do not fully design the agentic AI phase until the application/domain/job contracts are established.