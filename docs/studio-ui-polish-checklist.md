# SAGA Studio UI/UX Polish Checklist

This file is the **canonical source of truth** for the professional polish pass on PR #121 (`studio/video-gallery-ux`). Do not maintain a competing checklist in chat, the PR body, or another document. Every iteration must update this file before reporting back to the user.

Process and handoff instructions live in [`docs/studio-ui-polish-iteration-brief.md`](./studio-ui-polish-iteration-brief.md).

Status legend: `[ ]` pending · `[~]` in progress · `[x]` complete · `[-]` intentionally rejected/deferred by user.

## Current iteration

**Iteration 5 — stored video poster thumbnails**

- Status: `[x]` complete
- Completed item: **05**
- Next item: **06 — lazy-load Gallery hover video previews**
- Rule: do not start Item 06 until the user explicitly says continue. Each future iteration must follow implement → deterministic test → GitHub CI/visual preview → inspect screenshots → professional critique → record improvements → update this file → stop for user approval.

## P0 — correctness, interaction safety, accessibility

- [x] **01. Exact requested video duration after LTX 8n+1 padding.** Preserve model-required 8n+1 generation frames while clamping delivered video frames and trimming audio to the requested duration; validate 24/25/30 FPS with ffprobe. **Iteration 1 complete.**
- [x] **02. Reduce per-card immediate actions, especially on mobile.** Desktop now exposes Favorite, Download, Open, and More; secondary actions live in More. Mobile exposes three touch-safe actions (Favorite, Open, More) and moves Download into the More surface. Delete is separated in the overflow surface. **Iteration 2 complete.**
- [x] **03. Refactor MediaCard interaction semantics/accessibility.** Media frames are structural containers; each card now has one native primary button for open/select, selection uses `aria-pressed`, the visible checkbox is non-interactive/decorative, focus order starts with the primary media action, and nested button-like semantics are removed. **Iteration 3 complete.**
- [x] **04. Complete keyboard behavior for custom pickers.** Enter/Space open, Arrow navigation, Home/End, Enter/Space select, Escape close, focus return, clear `:focus-visible` states. **Iteration 4 complete.**

## P1 — core UX and architecture

- [x] **05. Replace fallback video-as-thumbnail behavior with stored poster thumbnails.** Completed videos now expose a server-side poster through the Modal gateway; Studio converts it to the standard 512px WebP thumbnail, persists it in R2/Supabase, and Gallery displays the stored poster first with `preload="none"`. **Iteration 5 complete.**
- [ ] **06. Lazy-load Gallery hover video previews.** `preload="none"`/deferred `src`, attach/play on hover/focus/visibility, pause/detach appropriately, respect reduced motion and touch behavior.
- [ ] **07. Merge Auto + aspect ratio into one clear Aspect control.** Example states: `Aspect · Auto 16:9`, `Aspect · Auto 4:3 · From reference`, or manual ratio.
- [ ] **08. Unify Image and Video aspect selection into one reusable `AspectPicker`.** Shared ratio preview, labels, selection behavior, keyboard support, responsive positioning, optional reference-source indicator.
- [ ] **09. Standardize resolution terminology and expose actual delivery dimensions.** Prefer `1080p` over `Full HD`; show context such as `1920×1080 at 16:9` or `1080×1920 at 9:16`.
- [ ] **10. Strengthen the Generate primary action.** Make Generate read clearly as the principal verb/action on desktop while retaining a compact mobile treatment.
- [ ] **11. Make Audio state explicit and non-color-dependent.** Clear On/Off state, tooltip/popover copy, accessible pressed state.
- [ ] **12. Improve generation lifecycle feedback.** Only expose real backend stages, add View Job and Cancel if supported, and clarify that setting edits during a running job apply to the next generation.
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

- [x] Internal LTX 8n+1 frame requirement preserved.
- [x] Delivery video clamped to requested `duration × fps` frames.
- [x] Generated audio trimmed/reset to the requested duration.
- [x] Live 24 FPS muted T2V: 5.000000 s.
- [x] Live 25 FPS generated-audio T2V: 5.000000 s with H.264 + AAC.
- [x] Live 30 FPS gateway I2V: 5.000000 s.
- [x] Studio CI, visual preview, architecture CI, compatibility, Modal smoke, and persistence checks passed on the validated product head.
- [x] Visual regression inspection found no Iteration 1 UI regression.

### Iteration 2 — Gallery action density and mobile touch safety

- [x] Reduced desktop immediate Gallery actions from seven to four: Favorite, Download, Open, More.
- [x] Moved Reuse, Edit, Add/Remove collection, and Delete into the desktop More menu.
- [x] Removed Delete from the routine immediate-action row and visually separated it as the destructive overflow action.
- [x] Mobile exposes only Favorite, Open, and More as immediate controls; Download moves into More.
- [x] Mobile primary controls use a 46px action bar and deterministic tests require at least 44px touch targets.
- [x] Mobile actions are visible without hover.
- [x] Added deterministic visual-preview assertions for desktop immediate-action count, overflow contents, destructive-action separation, mobile immediate-action count, and mobile touch-target size.
- [x] First professional visual review caught a real issue: the initial mobile More implementation was clipped by the card/overlay containing block and showed only the bottom overflow actions.
- [x] Fixed the clipping by removing the mobile overlay backdrop-filter containing block so the fixed More surface can span the viewport.
- [x] Second professional visual review confirmed the mobile More surface now spans the viewport width, sits at the bottom with safe margins, exposes all secondary actions, and keeps Delete separated.
- [x] Studio CI, Studio Visual Preview, Backend Architecture CI, and Required Check Compatibility passed on the final Iteration 2 product head (`2cd1a0de5ac3c55b2f9af9eca905e1cafc081c9e`).
- [x] Professional review result for item 02: no remaining action-density or touch-safety comments. Accessibility semantics remain intentionally tracked as item 03 rather than being folded into this iteration.

### Iteration 3 — MediaCard interaction semantics and accessibility

- [x] Removed `role="button"`/manual keyboard handlers from the structural `.media-frame` container.
- [x] Added one native `.media-frame-primary` button per card as the first focusable control; native Enter/Space activation now drives open/select behavior.
- [x] Browse mode exposes an accessible Open label without selection state; Manage mode exposes Select/Deselect labels plus `aria-pressed`.
- [x] Converted the visible selection checkbox from a second interactive button into an `aria-hidden` visual indicator, so clicking the indicator still resolves to the full-frame primary selection control without duplicate tab stops.
- [x] Replaced the redundant non-Gallery hover Open button with a decorative icon while preserving the primary full-frame native button.
- [x] Added a visible 2px keyboard focus ring to the primary media action and retained action-overlay disclosure on `focus-within` so keyboard users can discover secondary actions.
- [x] Added deterministic Playwright assertions for: no button-like frame role, no nested buttons, one native primary action per card, primary-first focus order, `:focus-visible` strength, browse/manage ARIA state, non-interactive selection indicators, and Enter/Space selection behavior on desktop/mobile.
- [x] The first CI run exposed a test-timing issue rather than a product defect: the assertion checked the 160ms action-overlay fade only 50ms after focus left. The test was corrected to observe the completed transition rather than weakening the product behavior.
- [x] Final Studio Visual Preview passed and generated the dedicated `10b-gallery-keyboard-focus.png` evidence plus desktop/mobile Manage screenshots.
- [x] Professional visual review: the full-frame focus ring is clearly visible, keyboard focus reveals the action bar, selection remains visually distinct through the card border/check indicator, and the focused selected card retains a separate inner focus boundary. No additional item-03 defects were found.
- [x] Studio CI, Studio Visual Preview, Backend Architecture CI, and Required Check Compatibility passed on the validated Iteration 3 product head (`1503d40a1421a81e4c7b169edbfda0affc6e42d9`).
- [x] Professional review result for item 03: complete. No new checklist item was required; broader typography/contrast tuning remains tracked under item 27.

### Iteration 4 — custom-picker keyboard behavior

- [x] Kept native button triggers while adding keyboard opening with Enter/Space and Arrow keys across Image resolution/aspect, Video resolution, Advanced custom listboxes, and the Video aspect/FPS controls.
- [x] Added roving keyboard focus with Arrow navigation plus Home/End movement and Enter/Space selection for custom menu/listbox options.
- [x] Added deterministic Escape handling with focus restoration to the originating trigger.
- [x] Fixed nested Escape behavior in Advanced settings so Escape closes the active child picker first instead of also dismissing the parent Advanced panel.
- [x] Made selection/Escape focus restoration synchronous where the trigger remains mounted, eliminating a cross-picker race where delayed focus from one picker could steal focus from the next picker and close it.
- [x] Added clear 2px `:focus-visible` treatment for picker triggers and options without conflating keyboard focus with the selected state.
- [x] Added deterministic Playwright coverage for open/navigation/select/Escape/focus-return behavior and focus-indicator strength across the shared Create pickers and dedicated Video output pickers.
- [x] Final GitHub runner validation passed the build and the complete `visual:preview` suite in Studio Iteration 4 Keyboard Patch run `32669033886`; artifact `9500854358` contains all Create, Video, Gallery, desktop, and mobile screenshots with no page errors.
- [x] Dedicated visual evidence: `02b-image-picker-keyboard-focus.png`, `03b-advanced-picker-keyboard-focus.png`, and `05f-video-picker-keyboard-focus.png`.
- [x] Professional visual review confirmed the focus boundary is strong and consistent, selected state remains separately legible, menus stay within their established visual system, and no Iteration 4 layout regression was found.
- [x] Validated product implementation commit: `9a09522d1c7dac4eed1fd4d6f4d5f4db78582a0f`.
- [x] Professional review result for item 04: complete.

### Iteration 5 — stored video poster thumbnails

- [x] Added a server-side poster endpoint at `GET /jobs/{call_id}/poster` in the Modal LTX gateway and installed ffmpeg in the gateway image for poster extraction.
- [x] Preserved the established `LTX25Worker.generate() -> bytes` contract. The first implementation returned a `{video, poster}` object; professional review rejected that compatibility break and moved poster extraction to the gateway instead.
- [x] Studio provider polling now retrieves the completed MP4 and then the poster JPEG. Poster retrieval is opportunistic/non-fatal so an otherwise valid completed video is not discarded if thumbnail extraction fails.
- [x] Video persistence now converts the source poster to the shared 512px WebP thumbnail format, stores it in R2 under the standard thumbnail key, and persists `thumbnail_r2_key`, `thumbnail_url`, source dimensions, thumbnail dimensions, `thumbnailFormat`, and poster source MIME metadata in Supabase.
- [x] Gallery poster-backed video cards now use the persisted poster and `preload="none"`; the prior metadata-load/seek fallback remains only for legacy rows without a thumbnail. Full deferred-`src` hover loading remains Item 06.
- [x] Added `test:poster`, a deterministic non-GPU contract test. It verifies 1920×1080 JPEG → 512×288 WebP conversion, video + poster provider retrieval, gateway/runtime source contracts, result plumbing, persistence fields, and Gallery poster-first preload behavior.
- [x] Studio CI now runs `npm run test:poster` on every relevant PR build.
- [x] Visual-preview tests assert that mocked video Gallery rows have poster URLs and use `preload="none"`; dedicated evidence is `10c-gallery-video-posters.png`.
- [x] Professional visual review confirmed stored posters render cleanly in the existing dense Gallery grid on desktop and mobile without introducing sizing, clipping, or control regressions. The pre-existing synthetic blank image-card artifact remains unrelated to Item 05.
- [x] Final product compatibility refinement commit: `3b6bf01433a55bcea9cd7560b47b33cb80fb626e`; final reviewed branch head before checklist documentation: `44e6f5df0e5e8d97a021078f0d31e21d431a8a81`.
- [x] Required Check Compatibility, Studio CI (including poster contract), Studio Visual Preview, and Backend Architecture CI all passed on the final reviewed product head.
- [x] REDGraft live Modal smoke could not execute past prefetch because the configured Modal workspace is externally disabled (`modal.exception.ConflictError: workspace ... is disabled`). Runtime deployment succeeded before that rejection. This is recorded as an external validation blocker, not a product-code failure; live poster/R2 verification should be rerun when the workspace is re-enabled.
- [x] Professional review result for item 05: complete. No remaining Item 05 comments. **Item 06 is next and remains gated on user approval.**
