# SAGA Studio UI/UX Polish Iteration Brief

## Purpose

This document is the durable handoff and operating brief for the professional UI/UX and implementation polish pass on PR #121 (`studio/video-gallery-ux`). It is intentionally stored in GitHub so a future ChatGPT session can continue without reconstructing the process from chat history.

The **canonical checklist** is stored separately at [`docs/studio-ui-polish-checklist.md`](./studio-ui-polish-checklist.md). That checklist is the single source of truth for item status and iteration state. Every iteration must update it before reporting back to the user. Do not maintain a competing checklist in chat or another file.

## Current handoff state

- PR: #121 — `Video output controls and Gallery UX`
- Branch: `studio/video-gallery-ux`
- PR state: draft, open, unmerged, undeployed.
- Completed checklist items: **01–07**.
- Next item: **08 — unify Image and Video aspect selection into one reusable `AspectPicker`**.
- Do not begin Item 08 until the user says **continue**.
- Development/review previews must remain GitHub-based; do not depend on Vercel previews during iteration.
- Latest completed item is Iteration 7. Refinement run `32673600494` passed source validation, the poster/deferred-preview contract, build, and the full visual suite; artifact `9502051993` was professionally reviewed. The REDGraft Modal smoke remains externally blocked because the configured Modal workspace is disabled.

## Non-negotiable process

1. Work only on the existing feature branch `studio/video-gallery-ux` / PR #121 unless the user explicitly changes the plan.
2. Keep PR #121 **draft, unmerged, and undeployed** until the user explicitly approves merge/deployment.
3. Use the remote GitHub workflow for implementation and review. Do not depend on Vercel previews during iteration.
4. Work in numbered iterations. Prefer one checklist item at a time; combine items only when they are technically inseparable.
5. For each iteration:
   - read the canonical checklist first;
   - pick the highest-priority unchecked item;
   - mark it `[~]` in the repo checklist;
   - implement it;
   - add/update deterministic tests where practical;
   - run GitHub CI and the GitHub Studio Visual Preview workflow;
   - inspect the generated screenshots/artifacts, not just workflow status;
   - act as a professional web developer/product UX reviewer and critique the result;
   - if the visual/professional review finds an issue in the current item, improve it and repeat the review before closing the iteration;
   - record any newly discovered out-of-scope issue as a new checklist item;
   - update the canonical checklist and this brief on GitHub;
   - **stop after the iteration** and report to the user what changed, what the professional review found, the updated checklist, CI status, and visual evidence. Wait for the user to say continue or stop.
6. Every iteration must provide visual feedback. If the iteration is backend-only, still inspect and provide a current visual-regression screenshot to prove no UI regression, and explicitly state that no deliberate visual change was expected.
7. Do not call an iteration complete merely because tests pass. The visual artifact must be inspected by the professional reviewer.
8. Continue the implementation → visual review → professional critique → improvement cycle inside the current checklist item until that item has no remaining actionable comments; then close the iteration and wait for the user.
9. Favor reusable components, explicit state/data flow, accessibility, performance, and maintainability over one-off CSS/DOM patches.
10. Do not silently weaken tests to make them pass. If a visual or correctness test exposes a real problem, fix the product.
11. Before starting a new session or iteration, read this brief and the canonical checklist from the branch so the process cannot drift.

## Definition of done for the whole pass

The pass is finished only when all accepted checklist items are complete, current GitHub checks are green or any external infrastructure blocker is explicitly documented, visual-regression screenshots are reviewed at the agreed breakpoints, the professional review produces no further actionable comments, and the user approves ending the iteration cycle.

## Professional-review baseline

The implementation is now a coherent product direction rather than a broken prototype. Completed work has materially improved video correctness, Gallery action density/touch safety, card accessibility semantics, picker keyboard behavior, and video-poster loading. Remaining high-value work includes shared Image/Video aspect-picker architecture, consistent resolution terminology, stronger Generate/audio affordances, richer real lifecycle feedback, bulk-management improvements, Create composition refactoring, Gallery naming/internal cleanup, App.jsx responsibility reduction, card metadata simplification, search/sort, design-token consolidation, broader accessibility, and true screenshot-baseline regression testing.

## Iteration log

### Iteration 1 — exact video delivery duration

**Status:** complete.

**Implementation:** preserved LTX-required 8n+1 internal frames while enforcing an exact user-facing delivery contract. The first ffmpeg `-t` approach was rejected after the live 25 FPS generated-audio smoke delivered 5.160000 seconds for a requested 5 seconds. The final approach explicitly clamps delivered video frames (`duration_seconds × frame_rate`) and trims/resets audio timestamps.

**Validated results:** 24 FPS muted T2V = 5.000000 s; 25 FPS generated-audio T2V = 5.000000 s with H.264 + AAC; 30 FPS gateway I2V = 5.000000 s. Studio CI, Studio Visual Preview, Backend Architecture CI, Required Check Compatibility, Modal smoke, and live R2/Supabase persistence all passed on the validated product head. Visual inspection found no UI regression.

**Professional review:** duration correctness resolved; no new visual issues introduced.

### Iteration 2 — Gallery action density and mobile touch safety

**Status:** complete.

**Implementation:** reduced desktop per-card immediate actions from seven to four: Favorite, Download, Open, and More. Reuse, Edit, Add/Remove collection, and Delete moved into the More menu. Mobile shows only Favorite, Open, and More as immediate actions; Download moves into More. Mobile action targets are at least 44px and visible without hover. Delete is separated as destructive in overflow.

**Professional review cycle:** the first visual review found that the initial mobile More implementation was clipped by the card/overlay containing block. That implementation was rejected. The containing-block issue was fixed, a second GitHub visual-preview run was inspected, and all overflow actions rendered correctly.

**Validation:** Studio CI, Studio Visual Preview, Backend Architecture CI, and Required Check Compatibility passed on final Iteration 2 product head `2cd1a0de5ac3c55b2f9af9eca905e1cafc081c9e`.

### Iteration 3 — MediaCard interaction semantics/accessibility

**Status:** complete.

**Implementation:** removed fake button semantics from the structural media frame; added one native full-preview primary button as the first focusable control; Manage selection uses `aria-pressed`; the visible checkbox is decorative/non-interactive; nested button semantics were removed; keyboard focus has a clear 2px indicator; focus reveals secondary card actions.

**Professional review cycle:** the first visual assertion checked an action-overlay transition too early. The product behavior was retained and the test was corrected to observe the completed 160ms transition instead of weakening the UI. Final keyboard-focus, desktop Manage, and mobile Manage screenshots were inspected with no remaining Item 03 comments.

**Validation:** Studio CI, Studio Visual Preview, Backend Architecture CI, and Required Check Compatibility passed on product head `1503d40a1421a81e4c7b169edbfda0affc6e42d9`.

### Iteration 4 — custom-picker keyboard behavior

**Status:** complete.

**Implementation:** added Enter/Space and Arrow opening, roving Arrow focus, Home/End, Enter/Space selection, Escape dismissal, focus restoration, nested Advanced-picker Escape protection, and strong `:focus-visible` states across shared Create pickers and dedicated Video aspect/FPS controls.

**Professional review cycle:** multiple remote runs exposed asynchronous focus races and a nested Escape problem. Those were fixed rather than hidden by timing changes. Dedicated visual evidence (`02b-image-picker-keyboard-focus.png`, `03b-advanced-picker-keyboard-focus.png`, `05f-video-picker-keyboard-focus.png`) was inspected and accepted.

**Validation:** final dedicated GitHub validation run `32669033886` passed build + full visual suite. Product implementation commit `9a09522d1c7dac4eed1fd4d6f4d5f4db78582a0f`. Later PR checks were green except the unrelated REDGraft smoke, which became externally blocked when the configured Modal workspace was disabled.

### Iteration 5 — stored video poster thumbnails

**Status:** complete.

**Implementation:** completed videos now have a stored poster path. The Modal gateway installs ffmpeg and exposes `GET /jobs/{call_id}/poster`, extracting a JPEG frame from the completed MP4. Studio provider polling retrieves video plus poster; poster failure is non-fatal to a valid video. `persistVideoJobResult` converts the poster to the same 512px WebP thumbnail format used by images, stores it in R2, and persists thumbnail URL/key/dimensions and metadata in Supabase. Gallery uses the stored poster and `preload="none"` for poster-backed videos; legacy rows without thumbnails keep the old metadata/seek fallback. True deferred `src` attachment remains Item 06.

**Deterministic coverage:** added `npm run test:poster` and wired it into Studio CI. The contract verifies a 1920×1080 JPEG becomes a 512×288 WebP, provider video/poster retrieval, runtime/gateway contract markers, result plumbing, persistence fields, and Gallery poster-first preload behavior. Gallery visual tests also assert poster URLs and `preload="none"`, and capture `10c-gallery-video-posters.png`.

**Professional review cycle:** the first implementation changed `LTX25Worker.generate()` from raw MP4 bytes to a `{video, poster}` object. This was rejected as an unnecessary compatibility break. The refinement restored the worker's existing `-> bytes` contract and moved poster extraction to the gateway, which keeps existing direct-worker callers intact while avoiding ffmpeg work in Studio/Vercel. The refined deterministic test, build, and full visual suite passed.

**Visual review:** desktop and mobile Gallery screenshots show stored posters fitting the existing dense card layout with no new clipping, sizing, action, or responsive regression. The known blank/dark synthetic image-card artifact is pre-existing and unrelated to poster work.

**Validation:** Required Check Compatibility, Studio CI (including the poster contract), Studio Visual Preview, and Backend Architecture CI passed on reviewed head `44e6f5df0e5e8d97a021078f0d31e21d431a8a81`. The REDGraft live Modal smoke deployed the runtime but failed at the subsequent prefetch invocation because Modal returned `ConflictError: workspace ... is disabled`; runtime/gateway rendering and live poster/R2 persistence therefore could not execute. Treat this as an external validation blocker and rerun live coverage when the workspace is enabled.

**Professional review:** Item 05 has no remaining actionable comments. The next iteration is **Item 06 — lazy-load Gallery hover video previews**, gated on explicit user approval.

### Iteration 6 — lazy/deferred Gallery video previews

**Status:** complete.

**Implementation:** poster-backed Gallery videos now render only their stored poster until an eligible preview is requested. The MP4 `src` is attached only for visible Gallery videos when desktop fine-pointer hover or keyboard focus expresses preview intent; the video is muted, inline, and looping, and is paused/detached when intent or visibility leaves. `IntersectionObserver` gates preview activity, reduced-motion users remain poster-only, and legacy rows without a stored poster only attach their metadata fallback while visible.

**Deterministic coverage:** Gallery Playwright verifies initial `src` absence, keyboard-focus attach/detach, hover activation, reduced-motion suppression, and true touch-emulated suppression (`hasTouch: true`, `isMobile: true`). `test:poster` also guards the deferred-source contract and the final input-modality implementation.

**Professional review cycle:** the first validation run exposed a stale poster-contract assertion that still expected the old preload expression; the contract was updated to match the new deferred behavior. The first professional source review then rejected a `window.innerWidth > 640` gate because narrow desktop windows are not touch devices. The final refinement uses only `(hover: hover) and (pointer: fine)` and validates a genuinely touch-emulated page. The refined visual suite passed and was inspected.

**Visual review:** static poster state, hover-preview state, reduced-motion state, and touch/mobile Gallery all preserve the established grid, action overlays, focus treatment, and mobile action geometry. No new Item 06 visual defect remains.

**Validation:** final refinement run `32671818722` passed source validation, `npm run test:poster`, Studio build, the full Playwright visual suite, and artifact upload (`9501593078`). Product refinement commit `c7ba940865eba1be07c23f2b09b6a78a051c2b92`. No Gallery page errors were recorded. Item 07 is next and remains gated on explicit user approval.

### Iteration 7 — unified Video Aspect control

**Status:** complete.

**Implementation:** replaced the separate Video Auto toggle plus ratio picker with one Aspect picker. Its trigger communicates automatic/manual mode and the effective ratio directly, including full reference provenance (`Aspect · Auto 4:3 · From reference`). The menu places Auto alongside the manual ratio choices; Auto follows the first reference when present and falls back to 16:9, while any explicit ratio switches to manual mode. Existing persistence and generation payload semantics remain unchanged.

**Deterministic coverage:** the Video-output Playwright suite now rejects any separate Auto button, requires exactly Aspect + FPS extra controls, verifies default Auto selection, keyboard navigation to manual 9:16, returning to Auto through the same menu, reference-derived 4:3 state, 16:9 fallback after reference removal, complete desktop option visibility, mobile trigger containment, and mobile menu viewport containment.

**Professional review cycle:** the first visual review accepted the combined-control direction but rejected two details: `Ref` was too abbreviated for a primary state label, and the new Auto row pushed `21:9 Cinematic` partly behind the desktop menu scroll boundary. The refinement uses the full `From reference` wording and a desktop-only Aspect-menu height that exposes all twelve choices without scrolling while preserving the viewport-safe mobile cap.

**Visual review:** the final desktop trigger/menu, reference-derived state, keyboard-focus state, and 390px mobile state were inspected. The control reads as one coherent setting, reference provenance is explicit, all desktop choices are visible, and mobile layout remains unclipped. No additional Item 07 defect remains.

**Validation:** dedicated refinement run `32673600494` passed source formatting, `npm run test:poster`, Studio build, the full `visual:preview` suite, and artifact upload (`9502051993`). Refined product head `93c4f7005ee651778775fb217892558487c1ede3`. Item 08 is next and remains gated on explicit user approval.
