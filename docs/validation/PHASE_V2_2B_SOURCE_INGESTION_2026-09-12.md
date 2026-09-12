# S.A.G.A. v2 Phase 2B Source Storage & Deterministic Ingestion Validation — 2026-09-12

## Scope

This record closes the **deterministic repository/CI portion** of Phase 2B from `docs/phases/PHASE_V2_2_STORY_INTAKE_CHARACTER_IDENTITY.md`.

It proves the v2-owned source-storage boundary, upload-completion contract, deterministic TXT/EPUB normalization, durable ingestion-worker control plane, normalized-structure persistence, product upload surface, and exact-head validation.

It does **not** claim that Phase-2 migrations have been applied to hosted Supabase, that the web/worker has a live bucket-scoped B2 runtime credential, that B2 browser-upload CORS has been configured, that a worker host has been selected/deployed, or that a Vercel deployment has occurred.

## Merged Baseline

- implementation PR: **#179**
- exact implementation head: `20a0e222aac42208b45a4faac3814208afd50762`
- merge commit: `fad0b8e5a3cc5c0e819d86fb41f50fe587574aab`
- Phase-2 tracking issue: **#176**

Phase 2A remains the predecessor baseline:

- implementation PR: **#177**
- Phase-2A merge: `7a053697e874d8fb6e0b03571b7cf0f2e885dd61`
- Phase-2A closure merge: `4b405ecacdb10e2a15b702210c2cdfef4daa2a9b`

## Implemented / Proven

### Owner-scoped source intake

- authenticated active members create source upload intents only inside projects they own;
- supported intake formats are `.txt` and `.epub`;
- the source identity is immutable and includes project/owner scope, expected byte size, SHA-256 digest, format, media type and object key;
- object keys are generated from S.A.G.A.-owned IDs and fingerprints rather than trusting filenames as authorization boundaries;
- browser code receives only a short-lived signed upload URL plus the exact required headers, never B2 credentials;
- the browser computes the declared SHA-256 before requesting the upload intent;
- original bytes upload directly to the private object store instead of transiting through a full-book Next.js request.

### Trusted upload completion

- signed upload metadata carries the declared source ID and SHA-256;
- completion independently reads B2 object metadata through `ObjectStorage.head()`;
- trusted server finalization receives observed byte size, content type and signed object metadata rather than browser assertions;
- mismatched observed metadata fails the source closed and does not enqueue ingestion;
- verified completion transitions the source to uploaded and atomically enqueues `source_ingestion` work;
- private original-source download/read access is issued only after current-account and owner-scoped database verification.

The browser-declared digest is intentionally not treated as final proof of content bytes. The worker re-hashes the actual downloaded source object before normalization can succeed.

### Durable ingestion worker boundary

A new v2-owned worker exists at `services/analysis-worker/`. It does not reactivate or import the historical Python/runtime architecture.

The worker:

- claims only `source_ingestion` jobs through a kind-scoped atomic lease function;
- cannot accidentally consume future `character_identity` jobs through the normal ingestion claim path;
- resolves the exact source record associated with the claimed job;
- marks source processing and renews the durable lease;
- downloads the immutable source object through its own B2 runtime boundary;
- verifies the object content type and actual byte SHA-256;
- runs deterministic normalization outside normal Next.js requests;
- persists immutable normalized results and analysis-run provenance transactionally;
- distinguishes deterministic terminal normalization failures from transient infrastructure/runtime errors;
- requeues bounded transient failures through the existing durable retry semantics.

Worker hosting remains provider-neutral. No permanent worker host is selected by this slice.

### Deterministic TXT normalization

The v2 normalizer:

- accepts strict UTF-8 bytes;
- rejects invalid UTF-8 explicitly;
- canonicalizes line endings and whitespace deterministically;
- recognizes conservative chapter headings without claiming semantic scene authority;
- preserves source order;
- emits stable structural keys/locators;
- records Unicode code-point offsets in the normalized document;
- produces deterministic normalized-content and output fingerprints;
- rejects a source when the actual byte digest differs from the immutable source fingerprint.

### Deterministic EPUB normalization

The EPUB path:

- validates the EPUB archive/mimetype/container/package structure;
- reads content in package spine order;
- validates manifest/spine references;
- supports XHTML/HTML spine documents used by the phase contract;
- rejects unsafe archive paths;
- places deterministic entry-count, per-entry and total-expanded-size bounds around decompression;
- ignores script/style/SVG/math content for prose extraction;
- converts block structure into deterministic normalized prose;
- removes formatting indentation introduced by pretty-printed XHTML while retaining textual content;
- emits stable `epub:` source locators;
- preserves spine/source order and exact normalized offsets/fingerprints;
- fails explicitly on malformed/missing EPUB package metadata.

### Normalized relational result boundary

Phase 2B adds immutable normalized-source and normalized-section results tied to the exact analysis run, project, source and owner scope.

The schema enforces:

- forced RLS;
- authenticated owner-only reads;
- no authenticated browser writes to normalized results;
- append-only service-role privileges for normalized result tables;
- stable section ordinal/key/location/offset contracts;
- transactional ingestion success that creates the immutable run and normalized structure before settling the job/source as successful;
- explicit ingestion failure provenance for terminal normalization errors.

### Product surface

The private project workspace now exposes the bounded source-add flow rather than a placeholder:

- supported `.txt`/`.epub` file selection;
- optional display label;
- browser hashing state;
- direct object-upload state;
- trusted server-verification state;
- queued-ingestion state;
- bounded user-safe failure messages;
- existing source list with ingestion/job status.

`/library` and `/home` copy now reflects active Phase-2B intake rather than describing upload as future work.

The source-add client is intentionally a small browser interaction island. Durable source, upload and job truth remains server/database owned.

## Deterministic Fixtures

Committed worker fixtures cover:

- UTF-8 text with CRLF, extra blank lines, accented characters and chapter headings;
- a synthetic minimal EPUB with explicit container/package/manifest/spine structure and two spine documents;
- exact normalized text;
- exact chapter/spine order;
- Unicode code-point offsets;
- stable source locators;
- deterministic reruns/fingerprints;
- invalid UTF-8;
- source-byte fingerprint mismatch;
- missing EPUB container/package metadata;
- worker successful lifecycle;
- terminal byte-integrity failure;
- transient object-store requeue behavior;
- no-work polling behavior.

Disposable-Postgres tests additionally prove owner isolation, upload metadata mismatch failure, no enqueue on mismatched upload, verified enqueue, lease use, atomic normalized persistence and cross-user normalized-result isolation.

## Exact-Head Validation

All active required checks succeeded on exact implementation head `20a0e222aac42208b45a4faac3814208afd50762` before merge:

- `SAGA v2 Web CI` run **34661457524** — success
  - lint — success
  - typecheck — success
  - web unit/structural tests — success
  - production Next.js build — success
  - disposable-Postgres migrations — success
  - Phase 1/2 database contracts — success
  - Phase-2B source-ingestion database contract — success
- `SAGA v2 Analysis Worker CI` run **34661457497** — success
  - worker dependency install — success
  - worker TypeScript typecheck — success
  - deterministic ingestion/worker fixture suite — success
- `SAGA v2 Visual Review` run **34661457496** — success
- `Backend Architecture CI` run **34661457500** — success
- `Required Check Compatibility` run **34661457516** — success

No unresolved inline PR review threads existed before merge.

## Rendered Evidence

Visual artifact from the exact implementation head:

- artifact ID: **10287611789**
- artifact name: `saga-v2-phase-2a-visual-review`
- SHA-256 digest: `ccadb4a2bd382ea7d69e34b9d72aa8f1ac0b6bbe5d5c8b2f0de8ad43daa61fb6`
- exact artifact head: `20a0e222aac42208b45a4faac3814208afd50762`

The artifact name is inherited from the shared visual-review workflow and predates this Phase-2B slice; the artifact metadata and head SHA above are authoritative for this validation record.

The production-build Chromium fixture rendered the active Home, Library, Projects, project workspace and Admin surfaces on the Phase-2B head, including the real project-workspace source-add composition. Existing narrow-layout, navigation, touch-target, focus-restoration, reduced-motion and horizontal-overflow checks remained green.

## Hosted / External State — Deliberately Unproven

The following remain outside this repository closure and must not be inferred from the green CI above:

1. application of Phase-2A/2B migrations to the dedicated hosted S.A.G.A. Supabase project;
2. a bucket-scoped non-master B2 runtime application key for the web/worker;
3. any required B2 CORS rule allowing the approved browser origin to use the signed upload flow;
4. a real browser upload to the dedicated S.A.G.A. B2 bucket;
5. a deployed long-running analysis worker;
6. a hosted source-ingestion job reaching succeeded;
7. hosted normalized-source/section rows;
8. a new Vercel deployment containing Phase 2B;
9. the full hosted source -> identity lifecycle required by Phase 2D.

The B2 bootstrap/master credential remains operator-only and is not consumed by `apps/web` or the worker.

Vercel deployment remains separately approval-gated. This merge does not authorize Preview or Production deployment.

## Phase State After This Evidence

- Phase 2A — **complete (repository/CI slice)**
- Phase 2B — **complete (repository/CI slice)**
- Phase 2C — **next: character identity engine**
- Phase 2D — **later: hardening, literary baseline and hosted end-to-end qualification**

Phase 2 overall remains active. Hosted source/worker/application proof is intentionally deferred to Phase 2D after the character identity loop exists and the required external-resource/deployment approvals become meaningful.

## Phase-2C Handoff

Begin Phase 2C from the merged Phase-2B baseline. Preserve these invariants:

- normalized source/sections are immutable evidence inputs;
- the identity worker uses durable `character_identity` jobs rather than running NLP in Next.js;
- provider/model output is normalized evidence, never product truth;
- canonical admission is precision-first;
- pronouns, malformed spans, sentence-initial capitalization and non-person evidence cannot mint character canonicals;
- attachment evidence may connect to an existing identity but may not bypass canonical admission;
- ambiguous evidence remains unresolved/quarantined;
- result persistence stays tied to an immutable analysis run and deterministic semantic fingerprint;
- no generative LLM is required;
- hosted B2/worker/Vercel proof remains separately approval-gated.
