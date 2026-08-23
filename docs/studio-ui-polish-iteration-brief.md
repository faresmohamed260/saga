# SAGA Studio UI/UX Polish Iteration Brief

## Purpose

This document is the durable handoff and operating checklist for the professional UI/UX and implementation polish pass on PR #121 (`studio/video-gallery-ux`). It is intentionally stored in GitHub so a future ChatGPT session can continue without reconstructing the process from chat history.

## Non-negotiable process

1. Work only on the existing feature branch `studio/video-gallery-ux` / PR #121 unless the user explicitly changes the plan.
2. Keep PR #121 **draft, unmerged, and undeployed** until the user explicitly approves merge/deployment.
3. Use the remote GitHub workflow for implementation and review. Do not depend on Vercel previews during iteration.
4. Work in numbered iterations. Prefer one checklist item at a time; combine items only when they are technically inseparable.
5. For each iteration:
   - pick the highest-priority unchecked item;
   - implement it;
   - add/update deterministic tests where practical;
   - run GitHub CI and the GitHub Studio Visual Preview workflow;
   - inspect the generated screenshots/artifacts, not just workflow status;
   - act as a professional web developer/product UX reviewer and critique the result;
   - record any newly discovered issue as a new checklist item;
   - update this checklist/status notes on GitHub;
   - **stop after the iteration** and report to the user what changed, what the professional review found, the updated checklist, CI status, and visual evidence. Wait for the user to say continue or stop.
6. Every iteration must provide visual feedback. If the iteration is backend-only, still inspect and provide a current visual-regression screenshot to prove no UI regression, and explicitly state that no deliberate visual change was expected.
7. Do not call an iteration complete merely because tests pass. The visual artifact must be inspected by the professional reviewer.
8. Continue the implementation → visual review → professional critique → checklist update cycle until the professional reviewer has no remaining comments or suggestions, or the user stops the process.
9. Favor reusable components, explicit state/data flow, accessibility, performance, and maintainability over one-off CSS/DOM patches.
10. Do not silently weaken tests to make them pass. If a visual or correctness test exposes a real problem, fix the product.

## Definition of done for the whole pass

The pass is finished only when all accepted checklist items are complete, current GitHub checks are green, visual-regression screenshots are reviewed at the agreed breakpoints, the professional review produces no further actionable comments, and the user approves ending the iteration cycle.

## Master checklist

Status legend: `[ ]` pending · `[~]` in progress · `[x]` complete · `[-]` intentionally rejected/deferred by user.

### P0 — correctness, interaction safety, accessibility

- [x] **01. Exact requested video duration after LTX 8n+1 padding.** Preserve model-required 8n+1 generation frames while clamping delivered video frames and trimming audio to the requested duration; validate 24/25/30 FPS with ffprobe. **Iteration 1 complete.**
- [ ] **02. Reduce per-card immediate actions, especially on mobile.** Desktop should expose only high-frequency actions plus an overflow menu; mobile should use touch-safe primary actions and a `More` sheet/menu. Delete must not sit beside routine actions.
- [ ] **03. Refactor MediaCard interaction semantics/accessibility.** Remove nested button-like semantics; use a dedicated primary preview button or explicit checkbox/select interaction, correct focus order, and accessible labels.
- [ ] **04. Complete keyboard behavior for custom pickers.** Enter/Space open, Arrow navigation, Home/End, Enter select, Escape close, focus return, clear `:focus-visible` states.

### P1 — core UX and architecture

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

### P2 — product polish and scale

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

## Professional-review baseline comments

The current implementation is a credible product direction rather than a broken prototype. Strengths: cohesive dark visual language, centered Create composer, corrected 1080p path, useful generation status, much better Gallery density/selection mode, and a strong remote GitHub preview discipline. Main weaknesses: action density, mobile touch ergonomics, accessibility semantics/keyboard behavior, video-thumbnail performance, ambiguous Auto/aspect state, brittle portal/querySelector composition, growing App.jsx responsibility, and CSS specificity debt.

## Iteration log

### Iteration 1 — exact video delivery duration

**Status:** complete.

**Goal:** preserve LTX-required 8n+1 frame padding internally while making the delivered MP4 match the user's requested duration exactly.

**Implementation:**
- Kept the 8n+1 internal frame-count contract required by LTX.
- Passed `duration_seconds` through the delivery finalizer.
- The first implementation used ffmpeg `-t`, but the real 25 FPS generated-audio smoke exposed a 5.160000-second delivery for a requested 5 seconds. The test was not loosened.
- Replaced the insufficient `-t` approach with explicit delivered-frame clamping (`duration_seconds × frame_rate`) plus audio `atrim`/PTS reset. This keeps the internal latent sequence valid while enforcing the external delivery contract.
- Expanded the live Modal smoke coverage to representative 24, 25, and 30 FPS paths, including generated audio and gateway image-to-video.

**Validated delivery results:**
- 24 FPS text-to-video, muted: **5.000000 s**, H.264, 854×480.
- 25 FPS text-to-video with generated AAC audio: **5.000000 s**, H.264 + AAC, 854×480.
- 30 FPS gateway image-to-video, muted: **5.000000 s**, H.264, 854×480.

**Validation status:**
- REDGraft LTX 2.5 Modal validate job: passed.
- Live R2 + Supabase persistence job: passed.
- Studio CI: passed.
- Studio Visual Preview: passed.
- Backend Architecture CI: passed.
- Required Check Compatibility: passed.

**Visual review:** this was deliberately a backend correctness iteration. The latest GitHub-rendered Create, generation-progress, desktop Gallery, and mobile Gallery-manager screenshots were inspected. No visual/layout regression was introduced.

**Professional review result:** P0 duration correctness is resolved. The implementation now separates the model's internal temporal constraint from the user's delivery contract, which is the correct architecture. No new visual issues were introduced by this change. The next highest-priority unresolved item is **02 — reduce per-card action density and improve mobile touch safety**.
