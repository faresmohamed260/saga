# S.A.G.A. v2 Architecture

## Purpose

S.A.G.A. v2 is a web-first rebuild of the same storytelling-intelligence product goals. This document defines the initial ownership boundaries. It intentionally does not freeze the future agentic AI implementation before the web application's contracts exist.

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

                                      later
                                        |
                                        v
                              Job / Agent runtime
                          reasoning + tools + workers
                                        |
                                        v
                        structured writes + artifacts
```

## Deployment Ownership

### GitHub

Owns:

- source of truth;
- pull requests/reviews;
- deterministic CI;
- bounded bootstrap/maintenance workflows;
- durable architecture/phase evidence.

### Vercel

Owns the web deployment of `apps/web`:

- Next.js rendering;
- route handlers/server actions suitable for request-bounded work;
- public frontend assets;
- environment configuration for the web application.

Vercel must not be treated as the eventual execution host for arbitrarily long agent/model workloads. Long-running work will use a later job/worker architecture.

### Supabase

Owns structured application state:

- authentication/user identity;
- projects/workspaces;
- source metadata;
- chapters/scenes and later analysis entities;
- job/run records and status;
- canon/character/location/event/application records;
- artifact metadata/references;
- authorization/RLS policy;
- realtime status updates where useful.

Supabase Storage is not the default large-object store for v2.

### Backblaze B2

Owns large binary/object payloads:

- uploaded source books/files;
- analysis artifacts that do not belong as relational rows;
- generated images/audio;
- exports;
- temporary processing payloads.

B2 access is behind a S.A.G.A. storage interface.

### Cloudflare

May own:

- DNS;
- CDN/proxy behavior;
- security/rate-limit rules;
- custom domain routing.

Cloudflare R2 is deliberately not the v2 S.A.G.A. object store.

## Web Application Structure

Initial target:

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
      data/               # later repositories/data access
      jobs/               # later application job lifecycle
  tests/unit/
```

Rules:

- `app/` composes routes and transport concerns;
- `features/` owns product behavior by user concept;
- `server/` owns privileged/server-only integration code;
- vendor clients stay inside their owning server infrastructure module;
- reusable UI primitives stay separate from feature-specific composition.

## Storage Contract

Feature/domain code should depend on operations shaped approximately like:

```ts
interface ObjectStorage {
  createUploadUrl(input): Promise<SignedUpload>
  createReadUrl(input): Promise<SignedRead>
  head(key): Promise<ObjectMetadata | null>
  delete(key): Promise<void>
}
```

The exact contract may evolve with upload requirements, but direct `S3Client` construction outside the storage implementation is prohibited.

### Runtime B2 configuration

Long-term web runtime variables:

- `SAGA_B2_BUCKET`
- `SAGA_B2_ENDPOINT`
- `SAGA_B2_APPLICATION_KEY_ID`
- `SAGA_B2_APPLICATION_KEY`

These are intentionally different from bootstrap master-key names.

Bootstrap/admin secrets:

- `SAGA_B2_KEY_ID`
- `SAGA_B2_MASTER_APPLICATION_KEY`

The master key is not S3-compatible and is never used by the normal Next.js B2 S3 client.

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

Do not use book titles/user strings as the primary isolation boundary. Application-generated IDs should own object namespaces.

## Initial Backend Boundary

The first backend is the server side of the Next.js application plus Supabase.

Use request-bounded server work for:

- authentication/session handling;
- CRUD;
- signed upload/download URL creation;
- project/source metadata operations;
- job creation/status reads;
- bounded orchestration/control-plane operations.

Do not run long book-analysis/model jobs synchronously in a Vercel request.

## Future Job/Agent Boundary

When the AI phase begins, the web application should submit durable jobs rather than invoking a hidden monolithic pipeline.

Conceptual flow:

```text
user action
 -> application validates request
 -> durable job record
 -> worker/orchestrator claims job
 -> agents/tools operate on source/canon/application state
 -> structured results + artifact references committed
 -> job status/events update
 -> UI observes progress/results
```

The specific queue, worker host, framework, and model providers remain open decisions until the web/data contracts exist.

## Product Information Architecture

The UI should be designed around user concepts rather than old pipeline stage numbers:

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

Useful v1 knowledge includes:

- source parsing lessons;
- chapter/scene concepts;
- identity-resolution research/evaluation;
- canon/evidence concepts;
- event/timeline/world modeling;
- narrative planning/generation concepts;
- visual/audio workflows;
- provenance/evaluation lessons.

Do not preserve v1 implementation layers solely for compatibility. Reimplement useful behavior behind the v2 application's contracts.

## Security / Cost Principles

- no provider secrets in client bundles;
- server-only service credentials;
- RLS for user-owned Supabase data;
- signed/short-lived object access where appropriate;
- master B2 credential restricted to bootstrap operations;
- free/non-live CI by default;
- paid model work later requires explicit bounded execution/cost policy;
- hobby/demo resource limits are architecture inputs, not afterthoughts.

## What Is Deliberately Undecided

Phase 0 does not lock:

- agent framework;
- long-running worker/queue provider;
- LLM/model provider set;
- vector/retrieval implementation;
- GPU execution provider;
- final visual/audio model stack;
- final database schema for analysis/canon;
- final direct-upload strategy.

Those decisions should be made from the needs of the validated web product rather than inherited from v1.