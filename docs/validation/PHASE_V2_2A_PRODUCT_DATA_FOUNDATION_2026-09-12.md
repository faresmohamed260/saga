# S.A.G.A. v2 Phase 2A Product/Data Foundation Validation — 2026-09-12

## Scope

This record covers the deterministic repository qualification of **Phase 2A — Product/data foundation** under the active Phase-2 contract:

- `docs/phases/PHASE_V2_2_STORY_INTAKE_CHARACTER_IDENTITY.md`

It proves the private project/source/job/run/character data boundary, database authorization/runtime contracts, and the first real Projects/Library application surfaces.

It does **not** claim real hosted source upload/download, scoped B2 runtime credentials, source normalization, a deployed analysis worker, character-resolution quality, or any new Vercel deployment.

## Merged Baseline

- implementation PR: **#177**
- exact implementation head: `51147ddf5855a43c3b50770502f2cf9f8fdf1f54`
- merge commit: `7a053697e874d8fb6e0b03571b7cf0f2e885dd61`
- tracking issue: **#176**

## Implemented / Proven

### Member-owned product data

- `saga_projects` establishes the private story-workspace ownership boundary;
- `saga_sources` establishes immutable source metadata ownership and future object-key/fingerprint state;
- project/source rows carry explicit owner scope;
- authenticated member access is constrained by forced RLS and the existing active-account boundary;
- cross-user product reads/writes are denied by the disposable-Postgres contract;
- suspended users lose project/source/result visibility through the same account-access boundary used by the rest of the private app.

### Durable analysis control plane

- `saga_analysis_jobs` stores mutable queued/running/terminal control-plane state;
- analysis enqueue is authenticated and idempotent for active duplicate work;
- worker claim uses atomic `FOR UPDATE SKIP LOCKED` lease semantics;
- lease tokens prevent a stale worker attempt from finishing a newer attempt;
- bounded retry state is explicit;
- browser roles cannot claim/renew/finish worker leases;
- service-role worker authority is limited to the intended functions/tables.

### Immutable run and identity-result foundation

- `saga_analysis_runs` is append-only from the worker boundary;
- analysis runs are relationally constrained to the same job/project/source/owner scope;
- character, alias, and mention evidence tables exist behind owner RLS;
- result tables are append-only from the worker boundary rather than mutable browser state;
- unresolved/quarantined mention state is representable without requiring every mention to resolve to a canonical character;
- weak/ambiguous mention policy remains a Phase-2 product invariant rather than being hidden inside provider output.

### Product surfaces

- `/projects` now creates and lists real member-owned projects;
- `/projects/[projectId]` exposes project Overview, Sources, Analysis, and Characters sections;
- `/library` lists real private source records and ingestion state;
- Home copy reflects the new project boundary accurately;
- upload controls remain deliberately absent until Phase 2B rather than exposing a fake or partially authorized source-upload path.

### Visual-review harness

The rendered-review fixture was extended with runner-only deterministic story data so activated product pages can be reviewed without weakening production authorization or requiring hosted Supabase/B2 access.

The fixture validates:

- Home, Library, Projects, project-workspace, and Admin desktop rendering;
- real fixture source/project data visibility;
- project workspace Sources/Analysis/Characters sections;
- narrow Projects without horizontal overflow;
- visible Project creation controls at approximately 44 px minimum touch height;
- narrow Admin overflow/touch targets;
- mobile navigation current-route state;
- opaque portaled navigation;
- Escape close + focus restoration;
- reduced-motion transition neutralization.

Framework-generated hidden Server Action inputs are excluded from touch-target measurement because they are not interactive controls.

## Exact-Head Validation

All required checks succeeded on exact implementation head `51147ddf5855a43c3b50770502f2cf9f8fdf1f54` before merge:

- `SAGA v2 Web CI` run **34654618229** — success
  - lint — success
  - typecheck — success
  - unit/structural tests — success
  - production Next.js build — success
  - disposable-Postgres migration application — success
  - account/admin database contracts — success
  - Phase-2A story-intelligence database contract — success
- `Required Check Compatibility` run **34654618239** — success
- `Backend Architecture CI` run **34654618234** — success
  - active backend tests — success
  - migration upgrade/rollback/re-upgrade — success
  - backup/restore proof — success
  - runtime image build — success
  - frontend image build — success
- `SAGA v2 Visual Review` run **34654618236** — success

## Rendered Evidence

- artifact ID: **10284398956**
- artifact name: `saga-v2-phase-2a-visual-review`
- exact artifact head: `51147ddf5855a43c3b50770502f2cf9f8fdf1f54`
- SHA-256 digest: `9a0b5646dfa830850c6f89ea442038c6ec57819c24ec85f20fcbef6dbd47ab89`

## Hosted / External State Not Claimed

Phase 2A did not require or perform a Vercel deployment.

The following remain deliberately unproven:

1. real hosted source-object upload/download through B2;
2. bucket-scoped runtime B2 application credentials;
3. upload completion metadata/fingerprint verification against real B2;
4. `.txt` / `.epub` normalization against real stored objects;
5. a deployed separate analysis worker;
6. hosted worker lease/retry lifecycle;
7. hosted character identity results;
8. cross-user hosted Phase-2 isolation proof;
9. deterministic hosted rerun proof.

The dedicated B2 bucket already exists, but bootstrap/master credentials remain operator-only. Phase 2B may implement and test the bounded storage/ingestion contracts without hosted credentials; enabling real hosted object I/O remains an explicit external credential/infrastructure gate.

## Phase State After This Evidence

- Phase 1 — complete
- Phase 2 contract — active
- Phase 2A Product/data foundation — **complete**
- Phase 2B Source storage + deterministic ingestion — **next**
- Phase 2C Character identity engine — pending
- Phase 2D Qualification — pending

The next repository work is Phase 2B from merged `main`: bounded source-object lifecycle, upload completion/fingerprint verification, deterministic UTF-8 text and EPUB normalization, golden fixtures, and normalized structure persistence.

Do not deploy to Vercel merely because Phase 2A is merged or because Phase 2B implementation is ready.