# SAGA Studio UI/UX Polish Checklist

This file is the **canonical source of truth** for the professional polish pass on PR #121 (`studio/video-gallery-ux`). Do not maintain a competing checklist in chat, the PR body, or another document. Every iteration must update this file before reporting back to the user.

Process and handoff instructions live in [`docs/studio-ui-polish-iteration-brief.md`](./studio-ui-polish-iteration-brief.md).

Status legend: `[ ]` pending · `[~]` in progress · `[x]` complete · `[-]` intentionally rejected/deferred by user.

## Current iteration

**P1 core UX and architecture — complete**

- Status: `[x]` Items **01–20** complete.
- Modal ecosystem worker-fleet migration and real worker-state feedback are implemented and validated.
- Next planned polish scope begins at **Item 21** in P2.

## P0 — correctness, interaction safety, accessibility

- [x] **01. Exact requested video duration after LTX 8n+1 padding.** Preserve model-required 8n+1 generation frames while clamping delivered video frames and trimming audio to the requested duration; validate 24/25/30 FPS with ffprobe. **Iteration 1 complete.**
- [x] **02. Reduce per-card immediate actions, especially on mobile.** Desktop exposes Favorite, Download, Open, and More; secondary actions live in More. Mobile exposes Favorite, Open, and More, with Download in More. Delete is separated. **Iteration 2 complete.**
- [x] **03. Refactor MediaCard interaction semantics/accessibility.** Media frames are structural containers; each card has one native primary button for open/select, selection uses `aria-pressed`, the visible checkbox is decorative, focus order starts with the primary action, and nested button-like semantics are removed. **Iteration 3 complete.**
- [x] **04. Complete keyboard behavior for custom pickers.** Enter/Space open, Arrow navigation, Home/End, Enter/Space select, Escape close, focus return, clear `:focus-visible` states. **Iteration 4 complete.**

## P1 — core UX and architecture

- [x] **05. Replace fallback video-as-thumbnail behavior with stored poster thumbnails.** Completed videos expose a server-side poster; Studio converts it to the standard 512px WebP thumbnail, persists it in R2/Supabase, and Gallery displays the stored poster first with `preload="none"`. **Iteration 5 complete.**
- [x] **06. Lazy-load Gallery hover video previews.** Poster-backed Gallery videos defer MP4 `src` until an in-view desktop fine-pointer hover or keyboard-focus preview is eligible; leaving intent pauses/detaches the source, reduced-motion and touch stay poster-only, and legacy thumbnail-less rows attach their metadata fallback only while visible. **Iteration 6 complete.**
- [x] **07. Merge Auto + aspect ratio into one clear Aspect control.** Video exposes one Aspect picker that combines Auto/manual mode, effective ratio, and reference provenance while preserving keyboard behavior. **Iteration 7 complete.**
- [x] **08. Unify Image and Video aspect selection into one reusable `AspectPicker`.** Image, Edit, and Video use one shared `AspectPicker` and canonical preset list, with shared ratio preview, layout, keyboard behavior, responsive anchored positioning, and optional Auto/reference provenance. **Iteration 8 complete.**
- [x] **09. Standardize resolution terminology and expose actual delivery dimensions.** Video uses explicit `480p`/`720p`/`1080p`/`2K` terminology with aspect-aware delivery dimensions; Image uses explicit pixel terminology and computed output dimensions. Unsupported Video 4K is no longer advertised. **Iteration 9 complete.**
- [x] **10. Strengthen the Generate primary action.** Desktop Image/Video now expose a clear labeled `Generate` CTA and Edit exposes `Edit`, while mobile retains the compact circular arrow action and mode-specific accessible names. **Iteration 10 complete.**
- [x] **11. Make Audio state explicit and non-color-dependent.** Video keeps the compact speaker button while showing explicit `Audio On`/`Audio Off` text on desktop and `On`/`Off` on mobile, preserves `aria-pressed`, and exposes concise explanatory hover/focus copy. **Iteration 11 complete.**
- [x] **12. Improve generation lifecycle feedback.** Real worker-backed stages, View Job, provider-aware Cancel, cancelled terminal feedback, and explicit guidance that edits during a running job apply to the next generation are implemented and validated. **Iteration 12 complete.**
- [x] **13. Add bulk Add to Collection.** Gallery Manage mode exposes Add to Collection, applies the selected collection to all persisted selected generations, clears selection after success, and keeps the sticky manager usable on mobile. Validated by Studio CI 32745883603 and Studio Visual Preview 32745883633; backend/inventory/live-smoke gates also passed.
- [x] **14. Make bulk selection wording precise.** Gallery Manage mode now says `Select visible`, matching its actual behavior of selecting only the currently loaded media rather than implying all matching paginated results. Validated by Studio CI 32746565855, Studio Visual Preview 32746565875, Backend Architecture CI 32746565882, Modal Worker Inventory 32746565838, Worker Fleet Live Smoke 32746565893, and Required Check Compatibility 32746565840. **Iteration 14 complete.**
- [x] **15. Improve mobile Manage mode.** Mobile Manage mode now uses a fixed bottom selection action bar with 44px touch targets and safe-area/viewport containment while `Done` remains in the top filter row. Final artifact `9528073923` from Studio Visual Preview `32748539009` was manually inspected: the 390px Manage state is contained, readable, and does not add top-of-page clutter; the normal mobile Gallery state remains unchanged. Validated by Studio CI `32748539003`, Studio Visual Preview `32748539009`, Backend Architecture CI `32748539005`, Modal Worker Inventory `32748538955`, Worker Fleet Live Smoke `32748538997`, and Required Check Compatibility `32748538971`. **Iteration 15 complete.**
- [x] **16. Harden bulk destructive failure handling.** Bulk delete records per-item outcomes, removes successful deletions immediately, reports partial failure counts/details, and leaves only failed items selected for retry. Final artifact `9528245515` from Studio Visual Preview `32748912117` was manually inspected at desktop and 390px mobile Manage states: selection/action affordances remain readable and contained with no regression. Validated by Studio CI `32748912013`, Studio Visual Preview `32748912117`, Backend Architecture CI `32748912075`, Modal Worker Inventory `32748912052`, Worker Fleet Live Smoke `32748912086`, and Required Check Compatibility `32748912095`. **Iteration 16 complete.**
- [x] **17. Replace repeated multi-file downloads with a scalable ZIP/download-batch flow.** Gallery bulk Download now makes one POST to `/api/download-batch`, which builds a single ZIP from persisted R2 originals (up to 100 items / 1 GB) and triggers one browser download instead of many independent downloads. Final artifact `9528710037` from Studio Visual Preview `32750178415` was manually inspected at desktop and 390px mobile Manage states: the Download ZIP action is readable and contained with no layout regression. Validated by Studio CI `32750178504`, Studio Visual Preview `32750178415`, Backend Architecture CI `32750178571`, Modal Worker Inventory `32750178430`, Worker Fleet Live Smoke `32750178518`, and Required Check Compatibility `32750178524`. **Iteration 17 complete.**
- [x] **18. Replace CreateWorkspace portal/querySelector integration with explicit component slots/composition.** Legacy composer exposes explicit `videoToolbarSlot` and `composerStatusSlot` React slots; the feature wrapper passes VideoOutputControls and VideoGenerationProgress directly, with `createPortal` and CSS-class `document.querySelector` host discovery removed. Validation also hardened duration-control accessibility/test targeting after slot insertion changed sibling order. Final artifact `9529378543` from Studio Visual Preview `32751942189` was manually inspected across desktop video controls, 390px mobile controls, and generation-progress states: controls remain contained, ordered, readable, and progress placement is preserved with no visual regression. Validated by Studio CI `32751942243`, Studio Visual Preview `32751942189`, Backend Architecture CI `32751942113`, Modal Worker Inventory `32751942205`, Worker Fleet Live Smoke `32751942214`, and Required Check Compatibility `32751942236`. **Iteration 18 complete.**
- [x] **19. Rename History internals to Gallery.** `GalleryView`, `galleryItems`, `loadGallery`, `gallery-*` CSS hooks, and `gallery-controls.css` now match the product terminology. The existing `/api/history` endpoint and legacy `#/history` route alias are intentionally retained as compatibility surfaces to avoid unnecessary migration risk. Final artifact `9529741150` from Studio Visual Preview `32752854888` was manually inspected at desktop, 390px mobile, and mobile Manage states: Gallery layout, filters, cards, and the bottom manager remain visually unchanged and contained. Validated by Studio CI `32752855009`, Studio Visual Preview `32752854888`, Backend Architecture CI `32752854626`, Modal Worker Inventory `32752854616`, Worker Fleet Live Smoke `32752854778`, and Required Check Compatibility `32752854618`. **Iteration 19 complete.**
- [x] **20. Split App.jsx responsibilities.** Generation lifecycle now lives in `useGenerationController`; Gallery/Favorites/Collections state/loading in `useLibraryController`; Gallery selection in `useGallerySelection`; item, bulk, and collection mutations in `useMediaActions`; browser API operations are consolidated in `api/studioApi.js`. Worker/lifecycle contract tests were updated to follow the new ownership rather than requiring implementation inside `App.jsx`. Final artifact `9530241337` from Studio Visual Preview `32754253022` was manually inspected across desktop Gallery, 390px mobile Manage, and active generation-progress states with no visual regression. Validated by Studio CI `32754253028`, Studio Visual Preview `32754253022`, Backend Architecture CI `32754253027`, Modal Worker Inventory `32754253032`, Worker Fleet Live Smoke `32754253050`, and Required Check Compatibility `32754253049`. **Iteration 20 complete; P1 complete.**

## P2 — product polish and scale

- [~] **21. Simplify Gallery card information hierarchy.** Implementation in validation: Gallery cards now show preview + max two-line prompt + one concise output line (`resolution · aspect · fps`), with model/seed/dimensions/created metadata moved into the media modal’s expandable Details surface.
- [ ] **22. Replace technical checkpoint/model strings with user-facing names.** Keep exact checkpoint/quantization/workflow metadata in a Details surface.
- [ ] **23. Add Gallery search and sorting.** Prompt search plus at least Newest/Oldest before adding more niche filters.
- [ ] **24. Add optional Gallery density modes.** Compact default plus Comfortable/detail-oriented density where useful.
- [ ] **25. Simplify persistent sidebar/product status information.** Clarify `More`; keep backend/provider status in Jobs/Models instead of persistent account navigation when possible.
- [ ] **26. Consolidate CSS into a small design-token system.** Standardize spacing, radii, control heights, typography, surfaces, accent/danger/success, and reduce specificity/`!important` patches.
- [ ] **27. Dedicated typography/contrast accessibility pass.** Raise overly small 9–11px text where appropriate, improve muted contrast, audit focus visibility and non-color state communication.
- [ ] **28. Convert screenshot capture into true visual regression.** Approved screenshot baselines/diffs with sensible tolerances rather than capture-only assertions.
- [ ] **29. Expand responsive visual coverage.** At minimum 320, 390, 768, 1024, 1440, and 1920 widths, focusing especially on the 768–1100 transition range.
- [ ] **30. Expand deterministic video delivery-contract tests.** Cover all supported aspects/resolutions/FPS, odd reference ratios, even delivery dimensions, 64-aligned internal dimensions, exact aspect tolerance, exact duration, and canonical 1080p landscape/portrait dimensions without requiring GPU generation.

## Completed iteration log

### Iteration 1 — exact video delivery duration

- [x] Preserved internal LTX 8n+1 frames while clamping delivered video to `duration × fps` frames and trimming/resetting generated audio.
- [x] Live delivery validation: 24 FPS muted T2V = 5.000000 s; 25 FPS audio T2V = 5.000000 s; 30 FPS gateway I2V = 5.000000 s.
- [x] Professional review found no UI regression.

### Iteration 2 — Gallery action density and mobile touch safety

- [x] Reduced desktop immediate card actions to Favorite, Download, Open, More; moved secondary/destructive actions into overflow.
- [x] Mobile uses three immediate controls with >=44px touch targets.
- [x] First visual review caught a clipped mobile More surface; containing-block behavior was fixed and revalidated.
- [x] Final reviewed product head: `2cd1a0de5ac3c55b2f9af9eca905e1cafc081c9e`.

### Iteration 3 — MediaCard interaction semantics and accessibility

- [x] Replaced fake frame-button semantics with one native full-frame primary action and decorative selection indicator.
- [x] Added visible 2px focus treatment and deterministic keyboard/ARIA coverage on desktop and mobile.
- [x] Final reviewed product head: `1503d40a1421a81e4c7b169edbfda0affc6e42d9`.

### Iteration 4 — custom-picker keyboard behavior

- [x] Added keyboard opening, roving navigation, Home/End, selection, Escape dismissal, focus return, nested Advanced Escape protection, and 2px focus-visible treatment across custom pickers.
- [x] Fixed asynchronous focus races rather than weakening tests.
- [x] Dedicated successful validation run `32669033886`; product implementation commit `9a09522d1c7dac4eed1fd4d6f4d5f4db78582a0f`.

### Iteration 5 — stored video poster thumbnails

- [x] Modal gateway exposes a poster endpoint; Studio converts/persists the poster as a 512px WebP thumbnail in R2/Supabase and Gallery loads it first.
- [x] Preserved `LTX25Worker.generate() -> bytes`; an initial object-return compatibility break was rejected and poster extraction moved to the gateway.
- [x] Added deterministic `test:poster` coverage and Gallery poster-first visual assertions.
- [x] Final reviewed product head before docs: `44e6f5df0e5e8d97a021078f0d31e21d431a8a81`.
- [x] Modal live verification remained externally blocked because the configured workspace was disabled.

### Iteration 6 — lazy/deferred Gallery video previews

- [x] Poster-backed videos attach MP4 only for eligible in-view desktop fine-pointer hover or keyboard focus, then pause/detach when intent leaves.
- [x] Reduced-motion and true touch emulation remain poster-only; legacy thumbnail-less rows retain a visible-only fallback.
- [x] Source review rejected viewport width as a modality proxy; final implementation uses `(hover: hover) and (pointer: fine)`.
- [x] Final validation run `32671818722`, artifact `9501593078`.

### Iteration 7 — unified Video Aspect control

- [x] Removed the separate Video Auto button; one Aspect picker now owns Auto/manual selection, effective ratio, and explicit `From reference` provenance.
- [x] First visual review caught abbreviated provenance and a partially hidden 21:9 option; both were refined.
- [x] Final refinement run `32673600494`, artifact `9502051993`, product head `93c4f7005ee651778775fb217892558487c1ede3`.

### Iteration 8 — shared Image/Video AspectPicker

- [x] Added reusable `features/create/AspectPicker.jsx`; Image, Edit, and Video now share one component/preset source.
- [x] Fixed focus handoff, a 2px menu overflow, and truncated default Auto provenance found during review.
- [x] Final standard Visual Preview `32676390654`, artifact `9502799506`, reviewed product head `333e32236b116be9a48234abada56582cbfd6ff2`.
- [x] Modal prefetch remained externally blocked because the configured workspace was disabled.

### Iteration 9 — resolution terminology and delivery dimensions

- [x] Replaced Video `Full HD` wording with explicit `1080p`; enabled Video presets are `480p`, `720p`, `1080p`, and `2K`.
- [x] Added shared `ResolutionPresets.js` helpers so Create UI and deterministic contracts derive dimensions from the same preset data.
- [x] Video picker rows, preview copy, trigger title, and accessible label expose aspect-aware delivered dimensions, including `1920×1080 at 16:9`, `1080×1920 at 9:16`, and `1440×1080 at 4:3` for 1080p.
- [x] Effective shared Aspect state—including Auto/reference-derived ratios—drives the displayed Video dimensions.
- [x] Image resolution uses explicit pixel terminology and shows computed output dimensions for the active aspect.
- [x] Removed Video 4K because the production workflow/runtime enables only `480p`, `720p`, `1080p`, and `2K`; professional source review rejected advertising a disabled capability.
- [x] Added `check-resolution-contract.mjs` to the normal Studio build, guarding canonical dimensions, runtime/workflow parity, `Full HD` regression, and disabled Video 4K.
- [x] First Item 09 validation run `32678010842` exposed a stale visual-test text expectation after terminology changed. The test was corrected without weakening keyboard End/Home/focus coverage.
- [x] Dedicated refinement run `32678135023` passed the full deterministic and Playwright visual suite; artifact `9503328418` was inspected.
- [x] Validation-generated screenshots and `package-lock.json` were removed from the product branch before final standard validation.
- [x] Final standard Studio CI `32678441763`, Studio Visual Preview `32678441802`, Backend Architecture CI `32678441772`, and Required Check Compatibility `32678441777` passed on reviewed product head `26fc3501aaaef91fd2e831ec30d5bb41c2caf0da`.
- [x] Final visual artifact `9503419570` was downloaded and all 31 screenshots were inspected across Image, Video, Edit, desktop/mobile Create, and Gallery states. No Item-09-specific visual or responsive regression remained.
- [x] Accepted evidence: `02-image-resolution-picker.png`, `04-video-resolution-picker.png`, `05h-video-resolution-portrait.png`...