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
- FLUX.2 Klein image edits create the job before calling Modal, move it to `running`, and attach the persisted output to the same generation UUID on completion.
- Failed requests move the existing job to `failed` and keep prompt/model/seed/workflow/error metadata for inspection.
- `/api/media` finalizes an existing job instead of inserting a second generation row when a valid job UUID is supplied. A terminal or stale job cannot silently create a duplicate completed generation.
- `/api/history` intentionally returns completed generations only so queued/running/failed jobs do not appear as broken library cards.
- Supabase generation rows include `started_at` and `provider` fields in addition to `created_at` / `completed_at`.
- The production lifecycle smoke test verified `queued -> running -> completed`, timestamps, job reads, deletion, and cleanup without leaving disposable rows behind.
- Studio has a URL-backed Jobs page with Active / Queued / Running / Failed / Completed / Recent filters. The page polls every three seconds while open and shows prompt, model, provider, seed, resolution, timestamps, and failure details.

Next within Phase 2:

- Move provider execution behind a common server-side workflow adapter so image and video jobs share one execution contract.
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

A generation record contains a UUID, status, media kind, mode, model, prompt, optional negative prompt, original R2 key/application media URL, thumbnail R2 key/application URL, original and thumbnail dimensions, MIME type, resolution, duration for video, seed, workflow identifier, provider, favorite state, error information, extensible JSON metadata, and lifecycle timestamps.

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
9. Active Jobs/Queue UI with lifecycle polling and filters. **Implemented.**
10. Move execution behind the shared server-side provider/workflow adapter. **Next.**
11. Add the first video workflow on top of the shared job contract.
