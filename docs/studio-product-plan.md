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

### Phase 1 — Persistent media library (current)

- Persist a database record for every generated asset.
- Store prompt, model, workflow/mode, resolution, seed, timestamps and R2 key.
- Generate a lightweight image thumbnail for gallery/history use and persist its key/URL/dimensions separately from the original.
- Add a history API with newest-first pagination.
- Replace demo-only History behavior with persisted generation history.
- Add image/video/model filters.
- Prepare favorites, collections, delete, download, reuse, edit and animate actions.

### Phase 2 — Generation jobs

Represent generation lifecycle explicitly:

`queued -> running -> completed | failed`

This becomes the common contract for fast image jobs and long-running video jobs. Record failures without losing the original prompt/settings.

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

## Current storage contract

A generation record contains a UUID, status, media kind, mode, model, prompt, optional negative prompt, original R2 key/application media URL, thumbnail R2 key/application URL, original and thumbnail dimensions, MIME type, resolution, duration for video, seed, workflow identifier, error information, extensible JSON metadata, and timestamps.

Current image thumbnails are generated server-side as WebP, constrained to a maximum 512 x 512 bounding box without upscaling. Original media remains unchanged in R2.

Indexes prioritize newest-first history and status/kind filtering. RLS is enabled from the beginning.

### Phase 1 implementation status

Completed:

- `studio_generations` table created in the AI Studio Supabase project.
- Newest-first, status, and media-kind indexes created.
- RLS enabled.
- Bootstrap RLS policies allow anonymous reads and narrowly scoped completed image-edit inserts while Studio uses the public Supabase key through its server API. This is a temporary hobby/demo bootstrap and should be replaced by authenticated/server-privileged access before production use.
- `/api/history` supports newest-first results, bounded page size, `offset` pagination, optional media-kind / exact-model filters, and model facets for the UI filter.
- `/api/media` records a generation row after a successful R2 upload and returns `generationId` / `historyPersisted` in the upload response.
- Prompt, seed, UTF-8 model metadata, original dimensions, thumbnail creation, thumbnail dimensions, original reads, and thumbnail reads were verified end-to-end with the automated media smoke test.
- Supabase has `thumbnail_r2_key`, `thumbnail_url`, `thumbnail_width`, and `thumbnail_height` fields.
- Image persistence creates a WebP gallery thumbnail, uploads it under `thumbnails/...`, records original/thumbnail dimensions, and returns the thumbnail URL alongside the original.
- `/api/media` serves both `generations/...` originals and `thumbnails/...` previews.
- `/api/history` returns the thumbnail fields needed by the gallery.
- The Studio History view fetches `/api/history`, renders thumbnail-backed persisted cards, refreshes on demand, survives page refresh/reopen, and falls back to the original URL for legacy image rows without thumbnails.
- Opening a History card loads the full original in an on-demand viewer instead of using the original for the grid.
- Newly generated persisted images immediately use their thumbnail URL in the Create gallery when available.
- History now has All / Images / Videos filters, a model selector, 24-item pages, and Load more pagination.
- Video history rows are poster-first when a thumbnail exists, use a lightweight placeholder when no poster exists, and open the original only in the on-demand player.

Remaining for Phase 1:

- Persist favorites and collections in Supabase rather than local React state.
- Add delete/download/reuse/edit actions with final UX and authorization rules.
- Replace bootstrap anonymous RLS with authenticated/server-privileged access before broader release.

## Immediate milestone

Complete the persistent library shell before moving generation execution onto the shared job lifecycle:

1. R2 original upload succeeds. **Done.**
2. Studio writes generation metadata. **Done.**
3. Prompt, seed, model, dimensions, thumbnail storage, and both media reads pass automated verification. **Done.**
4. History is persistent and thumbnail-first. **Done.**
5. Media-kind/model filters and Load more pagination. **Implemented; deployment verification next.**
6. Persist favorites and collections, then finish delete/download/reuse/edit actions.
7. Migrate generation execution to the shared job lifecycle before adding video workflows.
