# S.A.G.A. v2 Phase 2 — Story Intake & Character Identity Foundation

Status: **ACTIVE CONTRACT — implementation may begin only after this contract is merged to `main`.**

This phase is the first deliberate reconnection of S.A.G.A. storytelling intelligence behind the web/auth/data boundaries proven in Phase 1.

It does **not** recreate the old v1 runtime. Historical v1 ingestion, identity-resolution, evaluation, and canon-extraction material is evidence and requirements input only. All active ownership, persistence, runtime, provider, and application contracts in this document are v2-owned.

## 1. Phase objective

Deliver one complete private product loop:

```text
admitted member
  -> creates a S.A.G.A. project
  -> adds a supported prose source
  -> source is stored and fingerprinted
  -> a durable analysis job is queued
  -> a separate analysis runtime ingests the source
  -> S.A.G.A. resolves a conservative character identity index
  -> the member sees characters, aliases, mention evidence, and analysis state
```

The phase succeeds when S.A.G.A. is no longer only an authenticated shell: it can accept a real story source and return the first evidence-backed storytelling intelligence artifact through v2-owned contracts.

## 2. Why character identity is the first intelligence capability

Historical S.A.G.A. work makes character identity an upstream dependency for canon extraction, character/world modeling, quote attribution, retrieval, narrative generation, and grounded media generation. Restoring downstream features before stable identity would force each later subsystem to invent its own entity keys and duplicate ambiguity handling.

The historical identity work also exposed a clear failure mode: permissive mention admission can create false character canonicals from capitalization artifacts, function words, malformed noun fragments, places, objects, roles, or weak pronoun evidence. The v2 design therefore treats **precision-first character admission** as a product invariant rather than a cleanup pass.

Phase 2 deliberately restores:

- source ingestion and structural normalization;
- durable analysis execution;
- character mention evidence;
- conservative canonical character identities;
- aliases and attachment evidence;
- deterministic provenance and rerun behavior;
- user-visible inspection of the result.

It deliberately does not restore the entire old analysis/canon/agent stack.

## 3. User value

At the end of Phase 2, a member can use S.A.G.A. to answer:

- Which story/project does this source belong to?
- Has the source been ingested and analyzed?
- Which characters has S.A.G.A. identified?
- Which aliases or surface forms refer to each character?
- Where in the source did S.A.G.A. find the evidence?
- Which mentions were attached conservatively versus left unresolved?
- Which resolver/runtime version produced this result?

The interface must expose evidence and state clearly enough that later canon extraction can depend on the identity artifact without hiding uncertainty.

## 4. Product surfaces

Phase 2 activates existing Phase-1 placeholders rather than creating a parallel application.

### `/projects`

Required behavior:

- list projects owned by the signed-in member;
- create a project;
- open a project workspace;
- show high-level source/analysis state.

### `/projects/[projectId]`

Required project workspace sections for this phase:

- overview;
- sources;
- analysis status;
- characters.

A separate deeply nested route structure is optional; the required contract is the user-visible capability, not a specific component tree.

### `/library`

Required behavior:

- list source documents owned by the signed-in member;
- show associated project, format, ingestion state, and latest analysis state;
- provide the source-add/upload entry point or link into the project source flow.

### Character result surface

For each resolved character, expose at minimum:

- stable S.A.G.A. character ID;
- canonical display name;
- aliases/surface forms;
- evidence count;
- representative source mentions with chapter/scene or structural location when available;
- confidence/evidence tier expressed as a product concept, not fake probability precision;
- resolver/run provenance.

Unresolved or quarantined mentions must not be silently promoted into the main character list.

## 5. Initial source scope

Phase 2 supports **UTF-8 plain text (`.txt`) and EPUB (`.epub`)** as the first ingestion formats.

Rationale:

- both can be parsed deterministically without OCR;
- EPUB provides realistic book structure while remaining machine-readable;
- plain text provides a minimal deterministic fixture and debugging path;
- PDF/DOCX/OCR introduce extraction-quality and layout concerns that would obscure the first intelligence/runtime contract.

The ingestion layer must identify format from validated content/metadata rather than trusting a browser filename alone.

Unsupported formats must fail explicitly without creating a false successful analysis state.

## 6. Data ownership and relational contract

All Phase-2 product data is private and member-owned unless a later phase deliberately introduces sharing/collaboration.

The exact SQL names may evolve during implementation, but the following ownership concepts are mandatory.

### Project

Owns one storytelling workspace.

Required fields/concepts:

- immutable project ID;
- `owner_user_id` mapped to the authenticated Supabase user;
- title;
- optional description/metadata kept intentionally small in this phase;
- lifecycle status;
- created/updated timestamps.

### Source document

Represents one immutable uploaded/source payload associated with one project.

Required fields/concepts:

- immutable source ID;
- project ID and owner boundary;
- original filename/display label;
- validated format;
- byte size;
- SHA-256 content digest;
- object-storage key;
- ingestion state;
- created timestamp.

Replacing content creates a new source identity rather than mutating bytes underneath an existing source record.

### Normalized structure

The analysis runtime may persist chapter/section/scene structure as relational rows or another queryable normalized representation, but it must preserve:

- source ordering;
- stable structural IDs within a run;
- normalized text boundaries/offsets;
- source provenance;
- enough location information to render mention evidence.

Scene segmentation is allowed to start conservatively. A weak scene splitter must not be treated as semantically authoritative merely because the historical v1 runtime had one.

### Analysis job

Durable mutable control-plane record representing requested work.

Required concepts:

- job ID;
- project/source owner scope;
- job kind;
- status: queued/running/succeeded/failed/cancelled;
- requested-by user;
- input fingerprint;
- attempt/lease metadata sufficient for safe worker claiming;
- created/started/completed timestamps;
- bounded user-safe failure summary.

### Analysis run

Immutable provenance/result boundary for one actual execution.

Required concepts:

- run ID;
- job/source/project references;
- normalized input/content fingerprint;
- engine/resolver version;
- provider/model identifiers when a provider participates;
- deterministic configuration fingerprint;
- output/result fingerprint;
- started/completed timestamps;
- terminal result state.

Mutable queue state and immutable analysis provenance must not be conflated.

### Character identity

One canonical character result within an analysis run/project source context.

Required concepts:

- stable result ID;
- canonical display name;
- evidence/admission tier;
- evidence counts/summary;
- provenance to the producing run.

### Character alias

Required concepts:

- canonical character reference;
- observed surface form;
- normalized form used for comparison;
- evidence/provenance.

### Character mention

Required concepts:

- source/run reference;
- exact observed surface text;
- source offsets or equivalent stable structural locator;
- mention category such as proper-name, nominal, or pronoun;
- linked character when attachment is accepted;
- attachment/admission evidence and deterministic decision reason;
- unresolved/quarantined state when no safe attachment exists.

A mention that cannot be attached safely remains unresolved. The database must not require every proposed mention to resolve to a canonical character.

## 7. Authorization and RLS

Phase 1 access rules remain upstream of every Phase-2 route/action.

Mandatory rules:

- only admitted, active members can access product data;
- users can read/write only their own projects, sources, jobs, and results in this phase;
- browser code never receives Supabase service-role or object-storage secret credentials;
- privileged worker writes occur through a bounded server/runtime credential boundary;
- row-level security protects member-owned tables even when application code makes a mistake;
- a suspended account loses application access through the existing fresh account-access boundary;
- later sharing/collaboration must be a new explicit authorization contract, not an accidental relaxation of owner RLS.

## 8. Object-storage contract

Backblaze B2 remains the v2 binary/object store behind the existing provider-neutral `ObjectStorage` boundary.

Phase-2 storage ownership:

- original `.txt`/`.epub` bytes -> B2;
- large derived artifacts, if needed -> B2 under an explicitly versioned derived-artifact namespace;
- queryable product metadata, normalized structure required by the UI, job state, and character evidence -> Supabase Postgres.

Object keys must be generated server-side from S.A.G.A.-owned IDs and must not trust user filenames as authorization boundaries.

Suggested logical namespace (not a compatibility promise):

```text
sources/{ownerUserId}/{projectId}/{sourceId}/{contentSha256}/original
```

The existing master/bootstrap B2 credentials remain operator-only. Before a real hosted upload flow is enabled, create a bucket-scoped runtime application key with only the permissions required by the active source flow.

That scoped key is an explicit external credential gate; it is **not** permission to change Vercel deployment state.

## 9. Web request vs analysis runtime boundary

Full-book parsing/NLP must not execute inside a normal Next.js request or Server Action.

### Web application owns

- authentication/account-access checks;
- project/source metadata actions;
- issuing bounded object upload/read URLs through the server storage boundary;
- validating upload completion/metadata before enqueue;
- enqueueing durable analysis jobs;
- reading job/result state;
- rendering project/library/character evidence.

### Analysis worker owns

- claiming a queued job atomically;
- obtaining the specific source object it is authorized to process;
- deterministic decoding/normalization;
- chapter/section extraction;
- mention/evidence provider execution;
- character identity resolution;
- writing normalized results and immutable run provenance;
- heartbeat/lease renewal where needed;
- terminal success/failure transition.

### Queue/control-plane direction

For Phase 2, Supabase Postgres is the durable control plane. Job claiming must be atomic and lease-based so two workers cannot safely own the same attempt at the same time.

A dedicated Redis/service queue is out of scope unless implementation evidence proves Postgres insufficient for this phase.

The worker **hosting provider is intentionally not selected by this contract**. The runtime contract must be portable enough to run in CI/disposable validation and later on an approved worker host without coupling the web product to that host.

## 10. Deterministic ingestion contract

For the same source bytes and ingestion version/configuration, normalization must produce the same structural output fingerprint.

Required properties:

- compute SHA-256 over source bytes;
- reject unsupported/invalid encodings or malformed EPUBs explicitly;
- preserve source order;
- normalize whitespace/markup through a versioned algorithm;
- preserve enough source mapping for evidence display;
- never rewrite or mutate the original B2 object as part of analysis;
- produce a deterministic normalized-content fingerprint.

Historical v1 chapter/scene concepts may inform the implementation but do not dictate the v2 serialized schema.

## 11. Character identity policy

The central Phase-2 invariant is:

> **Attachment evidence may connect mentions to a character, but weak evidence may not mint a new character canonical.**

### Admission tiers

The resolver must distinguish at least:

1. **canonical seed evidence** — strong enough to create a character identity;
2. **attachment evidence** — can attach a mention to an existing identity but cannot create one by itself;
3. **quarantined/unresolved evidence** — retained for inspection/evaluation but not allowed to affect canonical identity state.

### Precision-first mention proposal

Do not recreate a capitalization/regex-first mention harvester.

Mention proposal/typing should be grounded in syntax and/or a trained span/entity provider. Candidate spans must have explicit boundaries and type/person-likeness evidence.

Phase-2 design rules:

- proper PERSON-like/name evidence can seed a canonical when the admission policy accepts it;
- nominal/descriptive mentions can attach when evidence is sufficient but are not automatically canonicals;
- pronouns cannot create canonical identities by themselves;
- sentence-initial capitalization alone is never character evidence;
- non-person typed spans such as locations/facilities/organizations/objects cannot be promoted into character canonicals merely through lexical similarity;
- malformed/truncated candidate spans must be rejected or quarantined rather than cleaned into an identity after admission;
- name/alias clustering is a first-class resolver step;
- ambiguous attachments remain unresolved instead of forcing the nearest/global candidate;
- later reveal/backfill may merge/attach evidence only through an explicit deterministic stabilization step;
- original source text remains immutable; interpretation lives in the resolved/evidence layer.

### Dialogue evidence

Quotation/speaker evidence is allowed as a high-value attachment/person-likeness channel, but full quotation attribution is not a Phase-2 exit requirement unless needed by the selected resolver implementation.

## 12. Provider/model boundary

Character identity policy belongs to S.A.G.A.; a third-party model/provider supplies evidence, not product truth.

The worker must expose an internal provider-neutral boundary roughly equivalent to:

```text
normalized source
  -> mention/span evidence
  -> optional coreference/link evidence
  -> deterministic S.A.G.A. admission/attachment/stabilization policy
  -> character identities + aliases + mentions + unresolved evidence
```

Rules:

- no provider SDK or model-specific record shape leaks into browser/application tables;
- provider/model name + revision participate in run provenance;
- provider output is normalized before the resolver consumes it;
- provider changes must be benchmarkable against the same fixture/evaluation harness;
- a coreference model may attach pronouns/nominals but cannot bypass S.A.G.A. canonical-admission policy;
- no generative LLM is required for the Phase-2 identity path.

### Candidate evidence providers

Historical S.A.G.A. work and current literature-focused research justify evaluating fiction-oriented/non-generative options rather than selecting a general chat model. Initial candidates include:

- a syntax + typed-span baseline;
- LitBank-oriented Maverick variants;
- xCoRe/LitBank variants;
- another maintained long-document/coreference implementation only if it can satisfy the same normalized provider contract.

This contract does **not** declare a winner. Provider selection is an implementation benchmark decision and must not change the deterministic product policy above.

## 13. Determinism, idempotency, and provenance

For a fixed:

- source content digest;
- ingestion version;
- provider/model revision and deterministic provider settings;
- S.A.G.A. resolver version/configuration;

two successful reruns must produce the same normalized result fingerprint after excluding non-semantic fields such as database UUIDs and wall-clock timestamps.

Required behavior:

- duplicate enqueue requests must not create uncontrolled concurrent duplicate work;
- retries are explicit attempts under durable job state;
- a failed run never becomes the latest successful result;
- a new engine/provider version produces a new run rather than mutating prior provenance;
- current UI results point to an explicit successful run;
- old runs may be retained for comparison until a later retention policy is defined.

## 14. Deterministic tests and evaluation

Phase 2 requires more than unit tests for route rendering.

### Database contract tests

Must prove:

- owner-only project/source/job/result access;
- cross-user reads/writes denied;
- worker/service operations are bounded to the intended database functions/tables;
- atomic job claim/lease behavior;
- retry/terminal-state invariants;
- cascade/restrict behavior does not orphan evidence silently.

### Ingestion golden fixtures

Small committed `.txt` and synthetic/minimal `.epub` fixtures must assert exact normalized structure and fingerprints.

### Character identity adversarial fixtures

Committed deterministic fixtures must cover historical failure classes, including:

- `You`, `What`, `This` or equivalent function/discourse tokens not becoming canonicals;
- sentence-initial capitalization not seeding a character;
- broken spans such as trailing prepositions/conjunctions not becoming identities;
- location/facility/object names not promoted to characters from lexical form alone;
- pronouns not minting characters;
- aliases merging only with accepted evidence;
- ambiguous pronouns remaining unresolved when evidence is insufficient;
- late strong-name evidence allowing deterministic stabilization/backfill without rewriting source text;
- repeated runs producing the same semantic output fingerprint.

### Provider contract fixtures

Provider-dependent tests must be separable from product-policy tests. Recorded/synthetic normalized provider evidence should allow CI to test the resolver without downloading a heavyweight model.

### Literary benchmark harness

Maintain an offline/non-blocking evaluation harness for literature-specific data such as LitBank and later book-scale datasets. It should report mention quality, false canonical creation, fragmentation/merge behavior, and coreference/identity metrics where gold data permits.

Do not make CI download large benchmark/model artifacts on every change. A small deterministic fixture suite is the required merge gate; heavyweight evaluation can run manually or in a dedicated workflow.

No arbitrary new numerical quality target is invented in this contract. Establish a v2 baseline first, then record improvement gates from measured evidence.

## 15. Web/UI tests

Required automated coverage includes:

- active member can create/list/open own project;
- another member cannot open the project by guessing its ID;
- source-add flow validates supported types and represents upload/ingestion state clearly;
- queued/running/failed/succeeded job states render without fake completion;
- character result view renders aliases and mention evidence from deterministic fixtures;
- unresolved/quarantined evidence is visually distinct from canonicals when exposed;
- suspended member remains blocked by the existing account-access boundary;
- responsive/accessibility conventions from the Narrative Desk remain intact.

## 16. Hosted validation gate

Phase 2 is not complete from local/CI fixtures alone. Final hosted validation must prove a real end-to-end source lifecycle against dedicated S.A.G.A. infrastructure.

Required hosted proof:

```text
active member
  -> creates project
  -> uploads supported source
  -> original object exists in the dedicated B2 bucket
  -> source metadata/content digest match
  -> job is durably queued
  -> deployed worker claims it
  -> job reaches succeeded
  -> immutable analysis run exists
  -> character index/evidence renders in the private app
  -> identical rerun yields the same semantic result fingerprint
```

Security proof must additionally show:

- a second admitted member cannot read the first member's project/source/results;
- object access cannot be obtained by guessing another member's object key;
- suspending the owner blocks private application access through the already-proven account gate;
- disposable hosted project/source/job/result/object records used for proof are cleaned up afterward.

Hosted evidence must record:

- web commit/SHA;
- worker commit/SHA or build identity;
- migration lineage;
- engine/provider revision;
- exact workflow/run IDs used for proof.

## 17. Deployment rule

The repository-wide manual Vercel deployment policy remains unchanged.

Implementing, merging, finishing, or validating code in GitHub does **not** authorize a Vercel deployment.

Before any Vercel Preview or Production deployment:

1. explain why hosted Vercel deployment is required;
2. state Preview or Production;
3. state the exact commit/SHA to deploy;
4. obtain fresh explicit owner approval for that deployment.

Worker hosting/deployment authorization must likewise be explicit once a provider is selected and real cost/credentials are involved.

Phase 2 may proceed through schema, contracts, deterministic fixtures, CI, and non-deployed implementation before those hosted gates.

## 18. Implementation slices

The default execution sequence is:

### Phase 2A — Product/data foundation

- project schema + RLS;
- source metadata schema + RLS;
- analysis job/run schema;
- character/alias/mention result schema;
- atomic job claim/retry functions;
- database contract tests;
- activate basic `/projects` and `/library` data surfaces with deterministic fixtures/mocks where storage is not yet live.

### Phase 2B — Source storage and deterministic ingestion

- bounded B2 upload/read integration using the existing storage abstraction;
- upload completion verification and content fingerprinting;
- `.txt`/`.epub` decoder/normalizer;
- normalized structure persistence;
- ingestion golden fixtures.

A bucket-scoped runtime B2 application key becomes required for the real hosted source flow in this slice.

### Phase 2C — Character identity engine

- provider-neutral evidence contract;
- precision-first mention proposal/typing;
- deterministic canonical seeding/name clustering;
- attachment/quarantine policy;
- optional coreference evidence provider evaluation;
- adversarial/golden identity fixtures;
- character result persistence and product UI.

### Phase 2D — End-to-end qualification

- retry/idempotency/concurrency hardening;
- literary benchmark baseline report;
- rendered accessibility/responsive validation;
- hosted B2 + worker + private-app lifecycle proof after explicit infrastructure/deployment authorization;
- cleanup and closure documentation.

A later slice may not silently weaken the earlier ownership/determinism contracts to make integration easier.

## 19. Explicitly out of scope

Phase 2 does **not** include:

- a general agent framework or multi-agent orchestrator;
- generative LLM chat/RAG over the book;
- full canon/fact extraction;
- relationship/world/timeline graph completion beyond what is minimally needed for character evidence;
- character dossiers or psychological inference;
- narrative continuation/generation;
- image/video/3D/audio/audiobook generation;
- collaborative/shared projects, organizations, or project-level RBAC;
- public project/source sharing;
- PDF/DOCX/OCR ingestion;
- bulk migration of v1 caches/artifacts into v2;
- v1 file/schema compatibility as a requirement;
- a generalized non-character entity knowledge graph;
- automatic custom-domain cutover;
- automatic Vercel deployment;
- choosing a permanent worker host before the runtime contract is proven;
- copying RenderLab product code/schema/routes/branding.

## 20. Historical material deliberately translated into v2

The following historical documents are requirements/evidence sources, not active runtime specifications:

- `docs/analysis_foundation_runtime.md` — source normalization/chapter/scene concepts and deterministic artifact lessons;
- `docs/identity_runtime.md` — stable identity, alias, mention evidence, resolver evaluation lessons;
- `docs/canon_extraction_runtime.md` — confirms stable identity as an upstream dependency for later evidence-backed canon;
- `docs/system_agent_roadmap.md` — broader sequencing context only; its monolithic/group runtime architecture is not adopted.

Translation rule:

| Historical concept | Phase-2 v2 ownership |
| --- | --- |
| source processor/cache | immutable Source + normalized run artifacts behind project ownership |
| pipeline/group orchestration | durable Postgres job + separate worker boundary |
| identity resolver outputs | queryable Character / Alias / Mention evidence tied to immutable analysis run |
| provider/model experiments | provider-neutral evidence adapter + recorded provenance |
| raw-text reveal rewriting | immutable source + separate resolved/evidence layer |
| permissive candidate cleanup | precision-first admission + quarantine/unresolved state |

## 21. Owner/external gates

Implementation should continue autonomously until one of these becomes real:

- a bucket-scoped B2 runtime key is required for hosted object I/O;
- a worker hosting provider/account/cost choice must be made;
- a large paid/proprietary model/provider credential is proposed;
- a Vercel deployment is needed for hosted validation;
- the custom production domain issue #165 is intentionally resumed;
- product behavior would require collaboration/sharing or another requirement outside this contract.

Do not stop ordinary repository/CI implementation merely because these future gates exist.

## 22. Phase completion criteria

Phase 2 is complete only when all of the following are true:

- this contract is implemented without an undocumented architecture substitution;
- project/source/job/run/character ownership and RLS contracts are covered by deterministic tests;
- `.txt` and `.epub` deterministic ingestion fixtures pass;
- precision-first identity adversarial fixtures pass;
- a literary evaluation baseline is recorded;
- the private UI exposes project/source analysis state and evidence-backed character results;
- exact-SHA CI is green;
- hosted B2 + worker + application lifecycle proof passes after explicit deployment/infrastructure approval;
- security isolation and rerun determinism are proven hosted;
- disposable hosted proof data is cleaned up;
- closure evidence is committed and the Phase-2 tracking issue is closed.

Only after Phase 2 is complete should S.A.G.A. select the next intelligence contract, with canon extraction as the likely downstream candidate because it can then consume stable, provenance-bearing character identities rather than reinventing them.
