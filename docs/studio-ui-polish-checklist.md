# SAGA Studio UI/UX Polish Checklist

This file is the **canonical source of truth** for the professional polish pass on PR #121 (`studio/video-gallery-ux`). Do not maintain a competing checklist in chat, the PR body, or another document. Every iteration must update this file before reporting back to the user.

Process and handoff instructions live in [`docs/studio-ui-polish-iteration-brief.md`](./studio-ui-polish-iteration-brief.md).

Status legend: `[ ]` pending · `[~]` in progress · `[x]` complete · `[-]` intentionally rejected/deferred by user.

## Current iteration

**Iteration 2 — Gallery action density and mobile touch safety**

- Status: `[x]` complete
- Completed item: **02**
- Next item: **03 — MediaCard interaction semantics/accessibility**
- Rule: implement → deterministic test → GitHub CI/visual preview → inspect screenshots → professional critique → record improvements → update this file → stop for user approval.

## P0 — correctness, interaction safety, accessibility

- [x] **01. Exact requested video duration after LTX 8n+1 padding.** Preserve model-required 8n+1 generation frames while clamping delivered video frames and trimming audio to the requested duration; validate 24/25/30 FPS with ffprobe. **Iteration 1 complete.**
- [x] **02. Reduce per-card immediate actions, especially on mobile.** Desktop now exposes Favorite, Download, Open, and More; secondary actions live in More. Mobile exposes three touch-safe actions (Favorite, Open, More) and moves Download into the More surface. Delete is separated in the overflow surface. **Iteration 2 complete.**
- [ ] **03. Refactor MediaCard interaction semantics/accessibility.** Remove nested button-like semantics; use a dedicated primary preview button or explicit checkbox/select interaction, correct focus order, and accessible labels.
- [ ] **04. Complete keyboard behavior for custom pickers.** Enter/Space open, Arrow navigation, Home/End, Enter select, Escape close, focus return, clear `:focus-visible` states.

## P1 — core UX and architecture

- [ ] **05. Replace fallback video-as-thumbnail behavior with stored poster thumbnails.** Extract and persist a poster frame after generation; Gallery loads posters first and video only on demand.
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
