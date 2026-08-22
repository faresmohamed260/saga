# SAGA Studio product plan

## Product direction

SAGA Studio is a customizable personal AI media-generation workspace inspired by the interaction model of Kling and Grok Imagine, while keeping the generation backend modular around ComfyUI workflows and Modal workers.

The application should support first-class text-to-image, image editing, image-to-video, and text-to-video generation, followed by custom workflow-driven tools.

## Architecture

- **Vercel / Studio UI** — frontend and lightweight API orchestration.
- **Modal + ComfyUI** — GPU inference and workflow execution.
- **Cloudflare R2** — durable binary media storage for originals, thumbnails/posters, and videos.
- **Supabase Postgres** — generation/job metadata, prompts, model/workflow information, favorites and collections.
- **GitHub** — application, workflow and infrastructure source of truth.

R2 owns media bytes. Supabase owns searchable application state. The database stores R2 keys/API media URLs rather than image/video blobs.

Gallery surfaces must prefer thumbnails/posters and avoid loading full-resolution originals until the user opens, downloads, edits, reuses, or plays an asset.

Generation execution is routed through Studio server APIs. The browser should select a workflow and submit inputs, while provider URLs and provider-specific transport stay on the server side.

## Build phases

### Phase 1 — Persistent media library (complete for the current single-user bootstrap)

- Persist a database record for every generated asset.
- Store prompt, model, workflow/mode, resolution, seed, timestamps and R2 key.
- Generate a lightweight image thumbnail for gallery/history use and persist its key/URL/dimensions separately from the original.
- Add a history API with newest-first pagination.
- Replace demo-only History behavior with persisted generation history.
- Add image/video/model filters.
- Persist favorites and collections.
- Add delete, download, reuse and edit actions.

### Phase 2 — Generation jobs (current)

Represent generation lifecycle explicitly:

`queued -> running -> completed | failed`

This becomes the common contract for fast image jobs and long-running video jobs. Record failures without losing the original prompt/settings.

Current Phase 2 implementation:

- `/api/jobs` creates queued jobs, validates lifecycle transitions, fetches one job, and lists lifecycle jobs by status.
- Shared `_generation-jobs.js` helpers own job creation, reads, listing, provider job identifiers and status transitions so execution routes and the Jobs API use the same lifecycle logic.
- FLUX.2 Klein image edits create the job before execution, move it to `running`, and attach the persisted output to the same generation UUID on completion.
- Failed requests keep prompt/model/seed/workflow/error metadata for inspection.
- `/api/history` intentionally returns completed generations only so queued/running/failed jobs do not appear as broken library cards.
- Supabase generation rows include `started_at`, `provider`, and `provider_job_id` in addition to `created_at` / `completed_at`.
- The production lifecycle smoke test verified `queued -> running -> completed`, timestamps, job reads, deletion, and cleanup without leaving disposable rows behind.
- Studio has a URL-backed Jobs page with Active / Queued / Running / Failed / Completed / Recent filters. The page polls every three seconds while open and shows prompt, model, provider, seed, resolution, timestamps, and failure details.
- `_workflows.js` is the first server workflow registry. The initial entry is `flux2-klein-image-edit`, which declares kind, mode, model, provider, defaults, output type and input limits.
- `_providers.js` is the provider adapter layer. The FLUX.2 Klein adapter owns the Modal gateway URL, multipart provider submit/poll requests, validation and provider error normalization.
- Modal exposes async submit/poll endpoints backed by `Function.spawn()` / `FunctionCall`, so cold GPU starts no longer require one Vercel request to remain open for several minutes.
- `/api/generate` is the shared server orchestration endpoint for registry-driven generation. It creates the job, moves it to `running`, submits the provider job, stores the provider job id, and returns `202` quickly.
- `/api/generate/result` polls the provider using short requests. Successful image results are now persisted server-side to R2, a WebP thumbnail is generated, and the same Supabase generation row is finalized as `completed` before persisted URLs are returned.
- Orchestrator-owned media keys are deterministic from the generation UUID, making repeated completion polls idempotent and preventing orphan duplicates from concurrent/retried result requests.
- `/api/generate/edit` remains a temporary compatibility route used by the current edit composer. The browser compatibility bridge consumes orchestrator-persisted media and suppresses the old second `/api/media` upload.
- Production Vite configuration points `VITE_FLUX2_KLEIN_API_URL` at `/api/generate`, so the existing client path resolves to `/api/generate/edit` without exposing or depending on the Modal gateway URL in the production browser bundle.
- The async provider smoke test verified fast `202` submission, repeated `202` polling during a cold start, eventual provider completion, R2 original + thumbnail persistence, final completed job state, and disposable cleanup without a five-minute Vercel function timeout.

Next within Phase 2:

- Remove the temporary compatibility fetch shim and have the React composer call `/api/generate` + `/api/generate/result` directly.
- Move source/reference uploads to a direct-to-R2 or equivalent upload path before long video workflows, avoiding large browser -> Vercel request bodies.
- Add safe retry/cancel semantics once provider execution can be controlled server-side.
- Add recovery rules for jobs stranded in `queued` or `running` by browser/network interruption.

### Phase 3 — Model and workflow registry

Modes:

- Text to Image
- Image Edit
- Image to Video
- Text to Video
- Custom workflows

Each registered workflow declares its capabilities and parameter schema so the UI is not hard-coded to one model.

### Phase 4 — Reference system

Support multiple ordered references with semantic roles such as identity, body/anatomy, clothing, pose, style and environment. Workflows decide which roles they accept.

### Phase 5 — Prompt composer

- Main and negative prompts where supported.
- Presets.
- Reuse settings from a previous generation.
- Use as reference / Edit this / Animate this actions.

### Phase 6 — Video foundation

- Persist MP4/WebM originals in R2.
- Generate static poster thumbnails for video gallery cards.
- Load posters in gallery/history rather than video payloads.
- Video cards/player.
- Long-running job polling/status.
- Connect the first image-to-video workflow, then text-to-video.
- Add Animate this once an image-to-video workflow is registered.

## Current storage contract

A generation record contains a UUID, status, media kind, mode, model, prompt, optional negative prompt, original R2 key/application media URL, thumbnail R2 key/application URL, original and thumbnail dimensions, MIME type, resolution, duration for video, seed, workflow identifier, provider, provider job identifier, favorite state, error information, extensible JSON metadata, and lifecycle timestamps.

Collections are stored separately in `studio_collections`, with generation membership in `studio_collection_items`. Deleting a collection removes membership rows but does not delete the underlying generated media.

Current image thumbnails are generated server-side as WebP, constrained to a maximum 512 x 512 bounding box without upscaling. Original media remains unchanged in R2.

Indexes prioritize newest-first history, status/kind filtering, favorites, and collection membership. RLS is enabled from the beginning.

### Phase 1 implementation status

Completed:

- `studio_generations` table created in the AI Studio Supabase project.
- Newest-first, status, media-kind, favorite, and collection membership indexes created.
- RLS enabled.
- Bootstrap RLS policies support the current single-user hobby/demo server API, including completed-generation deletion. These temporary anonymous policies must be replaced by authenticated/server-privileged access before broader release.
- Server Supabase requests prefer a service-role/secret key when configured, with the publishable key remaining as the temporary bootstrap fallback.
- `/api/history` supports newest-first results, bounded page size, `offset` pagination, optional media-kind / exact-model filters, model facets, and favorite state.
- Prompt, seed, UTF-8 model metadata, original dimensions, thumbnail creation, thumbnail dimensions, original reads, and thumbnail reads were verified end-to-end with automated smoke tests.
- Supabase has `thumbnail_r2_key`, `thumbnail_url`, `thumbnail_width`, and `thumbnail_height` fields.
- Image persistence creates a WebP gallery thumbnail, uploads it under `thumbnails/...`, records original/thumbnail dimensions, and returns the thumbnail URL alongside the original.
- `/api/media` serves both `generations/...` originals and `thumbnails/...` previews, and supports attachment download responses for originals.
- The Studio History view fetches `/api/history`, renders thumbnail-backed persisted cards, refreshes on demand, survives page refresh/reopen, and falls back to the original URL for legacy image rows without thumbnails.
- Opening a History card loads the full original in an on-demand viewer instead of using the original for the grid.
- History has All / Images / Videos filters, a model selector, 24-item pages, and Load more pagination.
- Video history rows are poster-first when a thumbnail exists, use a lightweight placeholder when no poster exists, and open the original only in the on-demand player.
- Active navigation is URL-backed, so refresh/reopen keeps the current Studio section.
- Persistent Favorites are stored on `studio_generations.is_favorite`, exposed through `/api/favorites`, and rendered by the Favorites sidebar page.
- Persistent Collections use `studio_collections` + `studio_collection_items`, with create/rename/delete, add/remove membership, collection covers, counts, and collection detail views.
- Media cards support Download original, Reuse settings, Edit this, Add/remove collection membership, and permanent Delete.
- Edit this fetches the original image on demand and loads it into the existing FLUX.2 Klein edit composer as the new source image.
- Permanent generation deletion removes the original and thumbnail from R2, then removes the generation row; favorite and collection references cascade with the database row.
- The production destructive-media smoke test creates disposable media, confirms original + thumbnail reads, confirms attachment download, permanently deletes the generation, verifies both R2 objects return 404, verifies the History row is gone, and leaves no disposable test rows behind.

Security work before broader release:

- Replace bootstrap anonymous access with Supabase Auth/JWT ownership and server-privileged authorization.
- Scope generation, favorites, collections, jobs, and destructive actions per user.

## Immediate milestone

The persistent library shell is complete and generation execution is moving onto the shared job lifecycle:

1. R2 original upload succeeds. **Done.**
2. Studio writes generation metadata. **Done.**
3. Prompt, seed, model, dimensions, thumbnail storage, and both media reads pass automated verification. **Done.**
4. History is persistent and thumbnail-first. **Done.**
5. Media-kind/model filters and Load more pagination. **Done.**
6. Persist Favorites and Collections. **Done.**
7. Download/reuse/edit/delete actions pass production verification. **Done.**
8. Shared `queued -> running -> completed | failed` job contract. **Done and production-smoke-tested for FLUX.2 image editing.**
9. Active Jobs/Queue UI with lifecycle polling and filters. **Done.**
10. Shared server-side workflow registry and provider execution adapter. **Done.**
11. Async provider submit/poll path that survives cold starts beyond Vercel's synchronous function window. **Done and smoke-tested.**
12. Server-owned provider-result persistence to R2 + Supabase. **Implemented; production deployment verification is blocked only by the current Vercel Hobby build-rate window.**
13. Remove the browser compatibility shim and call the unified orchestration API directly from the React composer. **Next.**
14. Add the first video workflow on top of the shared job contract.
