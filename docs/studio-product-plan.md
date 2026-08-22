# SAGA Studio product plan

## Product direction

SAGA Studio is a customizable personal AI media-generation workspace inspired by the interaction model of Kling and Grok Imagine, while keeping the generation backend modular around ComfyUI workflows and Modal workers.

The application should support first-class text-to-image, image editing, image-to-video, and text-to-video generation, followed by custom workflow-driven tools.

## Architecture

- **Vercel / Studio UI** — frontend and lightweight API orchestration.
- **Modal + ComfyUI** — GPU inference and workflow execution.
- **Cloudflare R2** — durable binary media storage (images, thumbnails, videos).
- **Supabase Postgres** — generation/job metadata, prompts, model/workflow information, favorites and collections.
- **GitHub** — application, workflow and infrastructure source of truth.

R2 owns media bytes. Supabase owns searchable application state. The database stores R2 keys/API media URLs rather than image/video blobs.

## Build phases

### Phase 1 — Persistent media library (current)

- Persist a database record for every generated asset.
- Store prompt, model, workflow/mode, resolution, seed, timestamps and R2 key.
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

- Persist MP4/WebM assets in R2.
- Video thumbnails/posters.
- Video cards/player.
- Long-running job polling/status.
- Connect the first image-to-video workflow, then text-to-video.

## Current storage contract

A generation record contains a UUID, status, media kind, mode, model, prompt, optional negative prompt, R2 key, application media URL, MIME type, resolution/dimensions, duration for video, seed, workflow identifier, error information, extensible JSON metadata, and timestamps.

Indexes prioritize newest-first history and status/kind filtering. RLS is enabled from the beginning.

### Phase 1 implementation status

Completed:

- `studio_generations` table created in the AI Studio Supabase project.
- Newest-first, status, and media-kind indexes created.
- RLS enabled.
- Bootstrap RLS policies allow anonymous reads and narrowly scoped completed image-edit inserts while Studio uses the public Supabase key through its server API. This is a temporary hobby/demo bootstrap and should be replaced by authenticated/server-privileged access before production use.
- `/api/history` implemented with newest-first results, a bounded `limit`, and optional `kind` / exact-model filters.
- `/api/media` records a generation row after a successful R2 upload and returns `generationId` / `historyPersisted` in the upload response.
- The production path has been verified with a real generation: R2 upload/read succeeds and Supabase receives the completed generation row.
- Prompt and seed metadata are now forwarded from the FLUX.2 client to `/api/media`.
- UTF-8 model names are URL-encoded in browser headers and decoded server-side before Supabase insertion, preventing the previous replacement-character corruption while keeping R2 object metadata ASCII-safe for signature compatibility.

Remaining for Phase 1:

- Load `/api/history` into the frontend and replace demo-only History behavior with persisted R2-backed cards.
- Add gallery filters and pagination/load-more behavior.
- Add delete/favorite/collection actions after the persistent read path is stable.

## Immediate milestone

Complete the Supabase-backed history path for the existing FLUX.2 Klein image-edit workflow:

1. R2 upload succeeds. **Done.**
2. Studio writes the generation metadata record. **Done.**
3. Prompt, seed, and model metadata are stored correctly. **Fixed; verify with the next production generation.**
4. `/api/history` returns persisted records newest first. **Done.**
5. History UI renders R2-backed assets after refresh/reopen. **Next.**
6. Then migrate generation execution to the shared job lifecycle before adding video.
