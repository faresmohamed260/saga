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

Owns source of truth, pull requests/reviews, deterministic CI, bounded bootstrap/maintenance workflows, and durable architecture/phase evidence.

### Vercel

Owns the web deployment of `apps/web`: Next.js rendering, request-bounded route handlers/server actions, public frontend assets, and web environment configuration.

Vercel is not the eventual execution host for arbitrarily long agent/model workloads. Long-running work will use a later durable job/worker architecture.

### Supabase

Owns structured application state including authentication/user identity, projects/workspaces, source metadata, chapters/scenes, later analysis/canon entities, job/run records, artifact metadata, authorization/RLS, and useful realtime status updates.

Supabase Storage is not the default large-object store for v2.

### Backblaze B2

Owns large binary/object payloads: uploaded sources, non-relational analysis artifacts, generated image/audio media, exports, and temporary processing payloads.

B2 access stays behind the S.A.G.A.-owned `ObjectStorage` interface.

The dedicated private storage foundation was validated by GitHub Actions run `34537566675`. Safe authoritative storage metadata is committed at `config/v2-storage.json`:

- bucket: `saga-v2-faresmohamed260-1207062480`
- bucket id: `b2af6d676af585d3aa0e0912`
- region: `us-east-005`
- S3 endpoint: `https://s3.us-east-005.backblazeb2.com`
- visibility: private

The validation performed create/reuse, upload, download, byte comparison, and deletion of a small `_system/bootstrap/` object. No application/source data was used.

### Cloudflare

May own DNS, CDN/proxy behavior, security/rate-limit rules, and custom-domain routing. Cloudflare R2 is deliberately not the v2 S.A.G.A. object store.

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

Normal web runtime variables:

- `SAGA_B2_BUCKET`
- `SAGA_B2_ENDPOINT`
- `SAGA_B2_REGION`
- `SAGA_B2_APPLICATION_KEY_ID`
- `SAGA_B2_APPLICATION_KEY`

The non-secret bucket/endpoint/region values are already known from `config/v2-storage.json`. A later bucket-scoped application key must provide the two secret runtime credential values before real web upload/read functionality is enabled.

Bootstrap/admin secrets are deliberately separate:

- `SAGA_B2_KEY_ID`
- `SAGA_B2_MASTER_APPLICATION_KEY`

The master credential is never consumed by `apps/web`. It remains limited to the manual `.github/workflows/v2-b2-bootstrap.yml` account/bootstrap path.

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

## Initial Backend Boundary

The first backend is the server side of the Next.js application plus Supabase.

Use request-bounded server work for authentication/session handling, CRUD, signed upload/download URL creation, project/source metadata operations, job creation/status reads, and bounded control-plane operations.

Do not run long book-analysis/model jobs synchronously in a Vercel request.

The current `/api/health` route is deliberately non-invasive: it reports only whether required integration configuration is present and does not contact Supabase or B2.

## Future Job/Agent Boundary

When the AI phase begins, the web application submits durable jobs rather than invoking a hidden monolithic pipeline:

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

The UI is designed around user concepts rather than old pipeline stages:

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

Useful v1 knowledge includes source parsing lessons, chapter/scene concepts, identity-resolution research/evaluation, canon/evidence concepts, event/timeline/world modeling, narrative planning/generation concepts, visual/audio workflows, and provenance/evaluation lessons.

Do not preserve v1 implementation layers solely for compatibility. Reimplement useful behavior behind v2 application contracts.

## Security / Cost Principles

- no provider secrets in client bundles;
- server-only privileged credentials;
- RLS for user-owned Supabase data;
- signed/short-lived object access where appropriate;
- master B2 credential restricted to manual bootstrap/admin operations;
- bucket-scoped non-master B2 credentials for web runtime;
- free/non-live CI by default;
- paid model work later requires explicit bounded execution/cost policy;
- hobby/demo resource limits are architecture inputs, not afterthoughts.

## Deliberately Undecided

Phase 0 does not lock the agent framework, long-running worker/queue provider, LLM/model providers, vector/retrieval implementation, GPU execution provider, final visual/audio model stack, final analysis/canon schema, or final direct-upload strategy.

Those decisions will be made from the needs of the validated web product rather than inherited from v1.