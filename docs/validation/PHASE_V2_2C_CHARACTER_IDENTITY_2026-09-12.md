# Phase 2C Character Identity Validation — 2026-09-12

Status: **DETERMINISTIC REPOSITORY/CI SLICE COMPLETE**

This record closes Phase 2C of `docs/phases/PHASE_V2_2_STORY_INTAKE_CHARACTER_IDENTITY.md` at the repository/CI boundary. It does not claim hosted B2, hosted Phase-2 Supabase migrations, a deployed worker, a selected production evidence provider, or a Vercel deployment.

## Implementation identity

- implementation PR: #181
- exact qualified implementation head: `9643a6c997f37074b8e6827c4ad0027858040f77`
- implementation merge: `191e2e4ab4ad9d4023f198b295922b5675e8d269`
- tracking issue: #176

## Implemented contract

Phase 2C adds a v2-owned evidence-to-identity pipeline behind the Phase-2A/2B ownership and ingestion boundaries.

### Provider-neutral evidence boundary

`services/analysis-worker/src/identity/` defines normalized mention/span/coreference evidence that is independent from browser/product persistence and from any one NLP/model SDK.

The worker supports:

- deterministic recorded/synthetic evidence for CI and policy evaluation;
- a provider-neutral HTTPS adapter for a future approved evidence service;
- explicit provider name/model/revision provenance on successful identity runs.

No generative LLM dependency is required or embedded in the identity policy.

### Precision-first resolver policy

S.A.G.A., not the provider, owns canonical admission and attachment decisions.

Proven rules include:

- only strong, clean, PERSON-like proper-name evidence may seed a canonical;
- pronouns and nominals may attach to an accepted identity but may not mint one;
- sentence-initial capitalization is not sufficient evidence;
- blocked discourse/function surfaces such as `You`, `What`, and `This` do not become canonicals;
- non-person typed spans such as `Chancery Lane` do not become characters;
- generic roles such as `Healer` do not become canonicals from lexical form alone;
- malformed candidate spans such as `Isaac Hale and` are quarantined rather than cleaned into an identity;
- provider clusters may support attachment but cannot force incompatible canonical seeds such as Cardan/Locke together;
- ambiguous pronouns remain unresolved;
- a full-evidence stabilization pass can attach earlier weak mentions after later strong-name evidence without rewriting source text;
- deterministic semantic character keys, aliases, decisions, and output fingerprints exclude database UUID/timestamp noise.

### Durable job/run/result lifecycle

A successful source-ingestion transition atomically creates the downstream `character_identity` job in PostgreSQL. This avoids an application-level crash window between normalization success and identity enqueue.

Identity workers claim only `character_identity` jobs through the kind-scoped lease path. Successful commits persist, in one trusted transaction:

- immutable analysis-run provenance;
- characters;
- aliases;
- linked, unresolved, and quarantined mentions;
- resolver/provider revisions and deterministic fingerprints.

Authenticated users retain read-only owner/RLS access to result evidence. Direct browser writes to identity results remain unavailable.

### Private product evidence surface

The project workspace now exposes evidence rather than only a character count:

- latest successful identity result per source;
- canonical display name;
- admission tier;
- aliases;
- representative linked mentions;
- unresolved/quarantined evidence;
- provider/resolver provenance.

The UI does not expose provider/model controls or imply false probability precision.

## Deterministic adversarial evidence

The worker fixture suite covers historical failure classes including:

- `You`, `What`, `This` false canonicals;
- capitalization/weak-person evidence;
- non-person location evidence;
- generic role evidence;
- malformed trailing-fragment spans;
- pronoun/nominal non-seeding behavior;
- contaminated provider clusters;
- ambiguous pronouns;
- late strong-name stabilization/backfill;
- span/source mismatch quarantine;
- identical semantic rerun fingerprints.

## Database integration hardening finding

During qualification, the Phase-2C database fixture initially appeared to violate identity mention offsets.

Instrumentation showed the identity commit function was correct. The actual cause was test-suite cross-contamination introduced by the new automatic ingestion-to-identity handoff:

1. the older Phase-2B source-ingestion database test successfully normalized a 25-character fixture;
2. under the new Phase-2C trigger, that success correctly enqueued a `character_identity` job;
3. the later Phase-2C test requested its own 41-character fixture;
4. the generic kind-scoped worker claim correctly selected the older queued identity job first;
5. the Phase-2C fixture evidence therefore appeared out of range for that older 25-character source.

The final fix preserves production queue semantics and restores deterministic test isolation by cancelling only the older Phase-2B fixture's downstream queued identity job after that test completes.

A temporary production-function workaround/diagnostic migration was removed before exact-head qualification. The qualified head uses the original strict identity commit validation.

## Exact-head CI evidence

All active gates passed on exact head `9643a6c997f37074b8e6827c4ad0027858040f77`:

- SAGA v2 Web CI `34664464705` — success
- SAGA v2 Analysis Worker CI `34664464659` — success
- SAGA v2 Visual Review `34664464727` — success
- Backend Architecture CI `34664464655` — success
- Required Check Compatibility `34664464685` — success

The Web CI database contract applies the full active migration lineage to disposable PostgreSQL and verifies the Phase-2C identity lifecycle, RLS ownership, trusted worker authority, transactional persistence, and cross-user isolation.

## Rendered evidence

Visual Review artifact:

- artifact ID: `10288233985`
- name: `saga-v2-phase-2c-visual-review`
- artifact head: `9643a6c997f37074b8e6827c4ad0027858040f77`
- digest: `sha256:03fc83ee8dad10a05e7edc33db77d7295cc02f70e90e0a4fdd3cd5dfb04d7f55`

The production-build Chromium fixture asserts the Phase-2C evidence composition at desktop and narrow width, including canonical identity state, unresolved/quarantined evidence, provenance, navigation context, and horizontal-overflow/accessibility conventions.

## Explicitly unperformed

Phase 2C repository completion does **not** mean the feature is live on hosted infrastructure.

Not performed:

- no bucket-scoped B2 runtime application key created;
- no B2 browser-upload CORS/account mutation performed;
- no Phase-2 migrations applied to the dedicated hosted S.A.G.A. Supabase project;
- no permanent identity evidence provider/model selected for production;
- no worker host selected or deployed;
- no Vercel Preview or Production deployment performed;
- no custom-domain cutover performed.

These remain Phase-2D qualification gates and require the relevant explicit credentials/provider/cost/deployment authorization.

## Handoff to Phase 2D

Repository work may continue autonomously with:

- retry/idempotency/concurrency hardening;
- a literature-oriented benchmark/evaluation harness and recorded v2 baseline;
- deterministic qualification workflows and reports;
- final rendered/accessibility evidence packaging.

Stop when real hosted qualification requires one of the owner/external gates defined in the Phase-2 contract: B2 runtime credentials/CORS, hosted Supabase mutation, worker host/provider/cost approval, or Vercel deployment approval.
