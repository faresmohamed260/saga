# S.A.G.A. v2 Architecture

## Purpose

S.A.G.A. v2 is a web-first rebuild of the same storytelling-intelligence product goals. This document defines the top-level ownership boundaries. Textual analysis now has a dedicated current contract in `ANALYSIS_ARCHITECTURE_2026.md`.

## Top-Level Shape

```text
                           +----------------------+
                           |       Browser        |
                           +----------+-----------+
                                      |
                                      v
+------------------------------------------------------------------+
|                     apps/web — Next.js                           |
|                                                                  |
|  product UI -> route handlers/server actions -> domain services  |
|                                     |                            |
|                         +-----------+-----------+                |
|                         |                       |                |
|                         v                       v                |
|                 Supabase boundary       Storage boundary         |
+-------------------------+-----------------------+----------------+
                          |                       |
                          v                       v
               Postgres/Auth/Realtime      Backblaze B2
                          ^                       ^
                          |                       |
                          +--------+--------------+
                                   |
                                   v
                         local analysis worker
                    deterministic + local NLP/models
```

Media/image generation is a separate workload family and may use approved GPU/cloud providers such as Modal. Textual book analysis must not depend on Modal under decisions D-026 through D-030.

## Deployment Ownership

### GitHub

Owns source of truth, pull requests/reviews, deterministic CI, bounded bootstrap/maintenance workflows, benchmark definitions and durable architecture/phase evidence.

### Vercel

Owns the web deployment of `apps/web`: Next.js rendering, request-bounded route handlers/server actions, public frontend assets and web environment configuration.

Vercel is not the execution host for full-book NLP/model workloads.

### Supabase

Owns structured application state including authentication/user identity, projects/workspaces, source metadata, normalized source structure, later analysis/canon entities, job/run records, artifact metadata, authorization/RLS and useful realtime status updates.

Supabase Postgres is the durable analysis job/control plane. Worker availability must not determine whether requested work is durably represented.

Supabase Storage is not the default large-object store for v2.

### Backblaze B2

Owns large binary/object payloads: uploaded sources, non-relational analysis artifacts, generated image/audio media, exports and temporary processing payloads.

B2 access stays behind the S.A.G.A.-owned `ObjectStorage` interface.

Dedicated storage metadata:

- bucket: `saga-v2-faresmohamed260-1207062480`
- bucket id: `b2af6d676af585d3aa0e0912`
- region: `us-east-005`
- S3 endpoint: `https://s3.us-east-005.backblazeb2.com`
- visibility: private

### Local Analysis Host

The default textual-analysis target is a S.A.G.A.-controlled local machine/worker with outbound-only network access.

It owns long-running book analysis execution but not application truth:

- claims durable Supabase jobs through existing lease semantics;
- reads source objects through scoped B2 credentials;
- runs deterministic normalization/orchestration and local literary NLP;
- invokes loopback/private local model services when escalation is justified;
- writes structured evidence/results and immutable run provenance back to Supabase.

It does **not** require a public inbound home-server port. If offline, durable queued work remains in Supabase until a worker can claim it.

The current TypeScript `services/analysis-worker` remains the preferred control-plane/orchestration owner. Python-specific NLP should be isolated behind a narrow local subprocess or loopback-service contract rather than moved into Next.js.

See `ANALYSIS_ARCHITECTURE_2026.md`.

### Modal / GPU Media Hosting

Modal may be used for image/media-generation workloads when appropriate and separately qualified.

Modal is explicitly **not** part of the required textual book-analysis path. The experimental Phase-2 xCoRe/worker Modal proof is research/deployment evidence only and must not become the permanent text-analysis architecture.

### Cloudflare

May own DNS, CDN/proxy behavior, security/rate-limit rules and custom-domain routing. Cloudflare R2 is deliberately not the v2 S.A.G.A. object store.

## Web Application Structure

```text
apps/web/
  src/
    app/                 # Next.js routes/layouts/API
    components/          # reusable product/design-system components
    features/            # feature-oriented UI + application logic
    lib/                 # framework-neutral helpers/config
    server/
      supabase/           # Supabase infrastructure boundary
      storage/            # ObjectStorage contract + B2 implementation
      data/               # repositories/data access
      jobs/               # application job lifecycle
  tests/unit/
```

Rules:

- `app/` composes routes and transport concerns;
- `features/` owns product behavior by user concept;
- `server/` owns privileged/server-only integration code;
- vendor clients stay inside their owning server infrastructure module;
- reusable UI primitives stay separate from feature-specific composition.

## Storage Contract

Feature/domain code depends on S.A.G.A.-owned operations rather than vendor SDKs:

```ts
interface ObjectStorage {
  createUploadUrl(input): Promise<SignedObjectUrl>
  createReadUrl(input): Promise<SignedObjectUrl>
  head(key): Promise<ObjectMetadata | null>
  delete(key): Promise<void>
}
```

Direct `S3Client` construction outside the storage infrastructure implementation is prohibited and covered by structural tests.

### Runtime B2 configuration

Normal runtime variables:

- `SAGA_B2_BUCKET`
- `SAGA_B2_ENDPOINT`
- `SAGA_B2_REGION`
- `SAGA_B2_APPLICATION_KEY_ID`
- `SAGA_B2_APPLICATION_KEY`

Bootstrap/admin secrets remain separate:

- `SAGA_B2_KEY_ID`
- `SAGA_B2_MASTER_APPLICATION_KEY`

The master credential is never consumed by ordinary web/local-analysis runtime code. Runtime credentials are scoped non-master application keys appropriate to the component's object operations.

## Initial Object-Key Convention

```text
sources/{projectId}/{sourceId}/original/{filename}
artifacts/analysis/{projectId}/{sourceId}/{artifactId}
generated/images/{projectId}/{generationId}/{artifactId}
generated/audio/{projectId}/{generationId}/{artifactId}
exports/{projectId}/{exportId}/{filename}
temporary/{scope}/{id}
_system/{operation}/{id}
```

Application-generated IDs, not human titles, own object namespace/isolation boundaries where practical.

## Web Request vs Long-Running Work

Use request-bounded server work for authentication/session handling, CRUD, signed object URL creation, project/source metadata operations, job creation/status reads and bounded control-plane operations.

Do not run full-book parsing, literary NLP or local/generative model jobs synchronously in a Vercel request.

Long-running textual analysis follows:

```text
user action
 -> application validates request
 -> durable Supabase job record
 -> local worker claims job
 -> deterministic/local analysis cascade operates on source/evidence
 -> structured results + provenance committed
 -> job status/events update
 -> UI observes progress/results
```

## Textual Analysis Cost / Evidence Boundary

The required textual pipeline follows decisions D-026 through D-030:

1. deterministic structure/rules;
2. lightweight local NLP;
3. specialized local models only when ambiguity remains;
4. small local generative reasoning only over bounded evidence packets that require judgment.

Provider/model output is never direct product truth. Deterministic S.A.G.A. code owns canonical IDs, acceptance/merge policy, provenance, persistence, state transitions and validation.

Provider adoption must include whole-book wall-clock/RAM/VRAM/model-size/license measurements in addition to quality metrics.

No paid AI API, hosted GPU subscription or per-token extraction service is a required dependency for book analysis unless the owner explicitly changes this decision later.

## Product Information Architecture

The UI is designed around user concepts rather than pipeline stages:

- Library / Sources
- Projects / Stories
- Chapters / Scenes
- Characters / Relationships
- Locations / World
- Timeline / Events
- Canon / Evidence
- Story Planning / Generation
- Media
- Jobs / Activity
- Settings

These are product areas, not a commitment to one table or route per item.

## v1 Reuse Boundary

Useful v1 knowledge includes source parsing lessons, chapter/scene concepts, identity-resolution research/evaluation, canon/evidence concepts, event/timeline/world modeling, narrative planning/generation concepts, visual/audio workflows, provenance/evaluation lessons and measured failure/latency data.

Do not preserve v1 implementation layers, LangGraph topology, agent counts or provider routing solely for compatibility. Reimplement useful behavior behind v2 application/evidence contracts.

## Security / Cost Principles

- no provider secrets in client bundles;
- server-only privileged credentials;
- RLS for user-owned Supabase data;
- signed/short-lived object access where appropriate;
- master B2 credential restricted to bounded bootstrap/admin operations;
- scoped non-master B2 credentials for runtime components;
- free/non-live CI by default;
- textual analysis remains functional with paid inference disabled;
- local worker/model services are not publicly exposed by default;
- hobby/demo resource limits are architecture inputs, not afterthoughts;
- media GPU/provider spend remains a separate explicit concern.

## Deliberately Undecided

The following remain measurement-driven/open:

- exact BookNLP/GLiNER/coreference provider combination after Phase-3 benchmarks;
- subprocess vs loopback HTTP implementation for the local Python NLP boundary;
- exact Qwen/local model size and quantization for bounded semantic adjudication;
- whether embeddings/vector indexing materially improve any measured candidate-retrieval task;
- final image/audio model/provider stack;
- final direct-upload strategy details as storage workflows expand.
