# SAGA Studio UI/UX Polish Checklist

This file is the **canonical source of truth** for the professional polish pass on PR #121 (`studio/video-gallery-ux`). Do not maintain a competing checklist in chat, the PR body, or another document. Every iteration must update this file before reporting back to the user.

Process and handoff instructions live in [`docs/studio-ui-polish-iteration-brief.md`](./studio-ui-polish-iteration-brief.md).

Status legend: `[ ]` pending · `[~]` in progress · `[x]` complete · `[-]` intentionally rejected/deferred by user.

## Current iteration

**Platform blocker — Modal ecosystem worker fleet**

- Status: `[~]` in progress
- Completed checklist items remain **01–11**.
- Blocker: replace the single-account Modal runtime assumption with ecosystem-affine workers, scale-to-zero compute, persistent model caches, credit/unavailable failover, clean worker provisioning, and production worker-state feedback.
- Item **12 — improve generation lifecycle feedback** remains pending and must not start until this blocker is implemented and end-to-end generation is validated.

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
- [ ] **13. Add bulk Add to Collection.** Include it in selection mode and use an appropriate collection picker.
- [ ] **14. Make bulk selection wording precise.** Use `Select visible` unless selection truly spans all matching paginated results.
- [ ] **15. Improve mobile Manage mode.** Prefer a sticky bottom selection action bar with large touch targets; keep `Done` at the top and minimize vertical clutter.
- [ ] **16. Harden bulk destructive failure handling.** Return/report per-item outcomes and keep failed items selected instead of treating partial success as all-or-nothing.
- [ ] **17. Replace repeated multi-file downloads with a scalable ZIP/download-batch flow.** Avoid browsers blocking many independent downloads.
- [ ] **18. Replace CreateWorkspace portal/querySelector integration with explicit component slots/composition.** Placement must come from React structure rather than CSS-class DOM discovery.
- [ ] **19. Rename History internals to Gallery.** `HistoryView`, `historyItems`, `loadHistory`, CSS names, etc.; API path may be migrated separately if risk is not justified.
- [ ] **20. Split App.jsx responsibilities.** Extract generation, gallery, collections, media actions, and selection hooks/services; introduce a clear API layer.

## P2 — product polish and scale

- [ ] **21. Simplify Gallery card information hierarchy.** Preview + max two-line prompt + concise metadata (`1080p · 16:9 · 24fps`). Move seed and implementation details to Details.
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
- [x] Accepted evidence: `02-image-resolution-picker.png`, `04-video-resolution-picker.png`, `05h-video-resolution-portrait.png`.
- [x] REDGraft smoke `32678441765` successfully deployed the runtime, then failed at prefetch because Modal returned `ConflictError: workspace ... is disabled`; this is the existing external infrastructure blocker, not an Item 09 regression.
- [x] Professional review result for Item 09: complete.

### Iteration 10 — strengthen the Generate primary action

- [x] Replaced the desktop icon-only submit affordance with an explicit high-contrast primary CTA: Image and Video show `Generate` plus the send arrow; Edit shows `Edit` plus the same arrow.
- [x] Desktop CTA uses a promoted 112px-minimum rounded rectangle with bold verb text, restrained elevation, hover/active feedback, and a 2px `:focus-visible` outline instead of looking like another 36px utility icon.
- [x] Preserved the existing mode-specific accessible names: `Generate image`, `Generate video`, and `Edit image`.
- [x] Kept the 390px mobile treatment compact: the verb label collapses and the action remains a 36×36 circular arrow with its accessible name intact.
- [x] Expanded `capture-ui-preview.mjs` to assert desktop CTA hierarchy/geometry, mode-specific visible verbs and accessible names, strong keyboard focus, and compact mobile behavior; added dedicated `01b-generate-primary.png` evidence.
- [x] Added `check-generate-action-contract.mjs` to the normal Studio build so the visible verb, promoted desktop geometry, focus treatment, mobile collapse, and Playwright contract cannot silently regress.
- [x] Initial successful GitHub product/visual refinement run `32713936104` passed build and the complete Playwright suite, uploaded artifact `9515188794`, and committed reviewed product implementation `eaec5e4528885b6012f1a43d5e9eb6b2c6d0192d` while restoring temporary workflow machinery.
- [x] Professional visual review accepted Image `Generate`, Video `Generate`, Edit `Edit`, and compact mobile arrow treatments: the CTA is clearly primary without overpowering the composer, stays aligned with dense Video controls, and introduces no clipping or responsive regression.
- [x] Final standard validation on reviewed product head `d66d1f3a40f94b80f153b5b74ed2aa2819874647`: Studio CI `32714238610`, Studio Visual Preview `32714238605`, Backend Architecture CI `32714238464`, and Required Check Compatibility `32714238492` all passed.
- [x] Final standard visual artifact `9515300251` was downloaded and inspected across Create/Image, Video, Edit, 390px mobile, and Gallery desktop/mobile regression states. No Item-10-specific visual defect or Gallery regression remained; diagnostics recorded no page errors.
- [x] REDGraft run `32714238545` deployed the runtime successfully and then failed at prefetch with `modal.exception.ConflictError: workspace ... is disabled`; downstream GPU smoke/persistence stages were skipped. This is the existing external Modal account blocker, not an Item 10 regression.
- [x] Professional review result for Item 10: complete. No new checklist item required.

### Iteration 11 — explicit Audio state

- [x] Kept the Audio action itself as a compact circular speaker control and added an adjacent textual state badge: `Audio On` / `Audio Off` on desktop and compact `On` / `Off` on 390px mobile.
- [x] Preserved `aria-pressed` plus action-oriented accessible labels (`Disable audio` / `Enable audio`) and added a 2px keyboard `:focus-visible` ring.
- [x] Added concise explanatory hover/focus copy: `Audio on · Generate with sound` and `Audio off · Generate without sound`.
- [x] Added `check-audio-control-contract.mjs` to the normal Studio build and `capture-audio-state-preview.mjs` to Studio Visual Preview, covering explicit text, accessible state, keyboard focus, compact geometry, toolbar containment, On/Off toggling, and desktop/mobile screenshots.
- [x] Professional review rejected an initial wide-pill implementation because it broke the established compact toolbar geometry; the final design restored the 36px/32px circular button and moved state wording into a separate adjacent badge.
- [x] Validation also caught two stale/incorrect test assumptions around programmatic `:focus-visible` and tooltip transition timing; the tests were corrected to enter keyboard modality and wait for the real CSS transition without weakening the accessibility contract.
- [x] Final reviewed product head: `b65d6cb48c100403e6643f00a32b35d9b12f836a`.
- [x] Final standard Studio CI `32717092869`, Studio Visual Preview `32717093243`, Backend Architecture CI `32717092902`, and Required Check Compatibility `32717092821` all passed.
- [x] Final visual artifact `9516351275` was downloaded and inspected. Accepted evidence includes `05i-video-audio-on.png`, `05j-video-audio-off.png`, `09b-mobile-video-audio-off.png`, and the wider Video/mobile regression captures. The Audio state is explicit without overpowering Generate, desktop controls remain balanced, mobile stays contained, and no Item-11-specific visual issue remains.
- [x] REDGraft run `32717092793` deployed the runtime successfully, then failed at prefetch with `modal.exception.ConflictError: workspace ... is disabled`; gateway/GPU/persistence stages were skipped. This remains the existing external Modal account blocker, not an Item 11 regression.
- [x] Professional review result for Item 11: complete. No new checklist item required. **Item 12 is next and remains gated on explicit user approval.**

### Iteration 12 — generation lifecycle feedback

- [x] Preserved real worker-backed lifecycle states from the Modal ecosystem fleet, including sleep/wake/load/ready/generating/finalizing plus unavailable, credit-exhausted, failover, completion, failure, and cancellation states.
- [x] Added `View Job` from the active Create progress surface, routing directly to Jobs & queue without losing the active job record.
- [x] Added provider-aware `Cancel` from Create using the same `/api/job-actions` cancellation path as Jobs; polling is abortable so user cancellation remains a distinct terminal state instead of becoming a later generic failure.
- [x] Added explicit running-job guidance: `Changes to settings now apply to your next generation.`
- [x] Added `check-generation-lifecycle-contract.mjs` to the normal Studio build and expanded Playwright coverage for failover feedback, View Job, cancellation, and settings guidance.
- [x] Final standard validation on head `4a6a996c0bc4dcbccd98d335b411e88d91db2d21`: Studio CI `32744435239`, Studio Visual Preview `32744435348`, Backend Architecture CI `32744434517`, Modal Worker Inventory `32744435147`, Worker Fleet Live Smoke `32744434530`, and Required Check Compatibility `32744434697` all passed.
- [x] Final visual artifact `9526513296` was produced successfully by the GitHub-only Playwright preview workflow; no Vercel Preview deployment was used.
- [x] Professional review result for Item 12: complete. Item 13 is next.

