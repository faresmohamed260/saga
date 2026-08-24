# SAGA Studio UI/UX Polish Iteration Brief

## Purpose

This is the durable operating brief for the professional UI/UX and implementation polish pass on PR #121 (`studio/video-gallery-ux`). It exists so a future session can continue without reconstructing the process from chat history.

The **canonical checklist** is [`docs/studio-ui-polish-checklist.md`](./studio-ui-polish-checklist.md). That file is the single source of truth for item status and iteration state. Do not maintain a competing checklist in chat, the PR body, or another document.

## Current handoff state

- PR: #121 — `Video output controls and Gallery UX`
- Branch: `studio/video-gallery-ux`
- PR state: draft, open, unmerged, undeployed.
- Completed checklist items: **01–10**.
- Next item: **11 — make Audio state explicit and non-color-dependent**.
- Do not begin Item 11 until the user says **continue**.
- Development/review previews must remain GitHub-based; do not depend on Vercel previews during iteration.
- Latest completed item is Iteration 10. Final standard Studio CI `32714238610`, Studio Visual Preview `32714238605`, Backend Architecture CI `32714238464`, and Required Check Compatibility `32714238492` passed on reviewed product head `d66d1f3a40f94b80f153b5b74ed2aa2819874647`. Visual artifact `9515300251` was downloaded and professionally reviewed across Image, Video, Edit, mobile Create, and Gallery regression states. Desktop now exposes an explicit primary `Generate`/`Edit` CTA while mobile remains compact. REDGraft Modal validation remains externally blocked because the configured Modal workspace is disabled.

## Non-negotiable process

1. Work only on `studio/video-gallery-ux` / PR #121 unless the user explicitly changes the plan.
2. Keep PR #121 **draft, unmerged, and undeployed** until the user explicitly approves merge/deployment.
3. Use the remote GitHub workflow for implementation and review. Do not depend on Vercel previews during iteration.
4. Work in numbered iterations, one checklist item at a time unless items are technically inseparable.
5. At the start of every iteration, read the canonical checklist first and mark the working item `[~]` in the repo before product implementation.
6. Implement the item and add/update deterministic tests where practical.
7. Run GitHub CI plus **Studio Visual Preview**.
8. Download and inspect the generated screenshots/artifacts, even for backend-focused work.
9. Act as a professional developer/product UX reviewer after implementation. If the review finds an item-specific problem, fix it and repeat test + visual review within the same iteration until no item-specific actionable comment remains.
10. If review finds a separate/out-of-scope issue, record it as a checklist item instead of silently expanding scope.
11. Do not weaken tests simply to make them pass. Fix the product or correct a stale/incorrect assertion while preserving the intended contract.
12. Update both the canonical checklist and this brief before reporting completion.
13. **Stop after each completed iteration** and wait for the user to say continue or stop.
14. Favor reusable components, explicit state/data flow, accessibility, performance, and maintainability over one-off CSS/DOM patches.
15. Before starting a new session or iteration, reread this file and the canonical checklist from the branch so the process cannot drift.

## Definition of done for the whole pass

The pass is finished only when all accepted checklist items are complete, current GitHub checks are green or external infrastructure blockers are explicitly documented, visual evidence has been reviewed at the agreed breakpoints, the professional review produces no remaining actionable comments, and the user approves ending the iteration cycle.

## Professional-review baseline

The implementation is a coherent product direction rather than a prototype. Completed work has improved exact video delivery, Gallery action density and touch safety, card semantics/accessibility, custom-picker keyboard behavior, stored video posters, deferred preview loading, unified/shared aspect selection, resolution terminology/delivery geometry, and Create primary-action hierarchy. Remaining high-value work includes explicit Audio state, real lifecycle feedback, bulk-management improvements, Create composition refactoring, Gallery naming/internal cleanup, App.jsx responsibility reduction, card metadata simplification, search/sort, design-token consolidation, broader accessibility, and true screenshot-baseline regression testing.

## Iteration log

### Iteration 1 — exact video delivery duration

**Status:** complete.

Preserved LTX-required 8n+1 internal frames while enforcing exact delivered duration. Final live checks: 24 FPS muted T2V = 5.000000 s; 25 FPS generated-audio T2V = 5.000000 s; 30 FPS gateway I2V = 5.000000 s. Visual inspection found no UI regression.

### Iteration 2 — Gallery action density and mobile touch safety

**Status:** complete.

Reduced desktop immediate card actions to Favorite, Download, Open, More; moved secondary/destructive actions into overflow. Mobile uses three immediate controls with >=44px touch targets. First visual review found the mobile More surface clipped by a containing block; that was fixed and revalidated. Final reviewed product head: `2cd1a0de5ac3c55b2f9af9eca905e1cafc081c9e`.

### Iteration 3 — MediaCard semantics/accessibility

**Status:** complete.

Replaced fake frame-button semantics with one native full-frame primary action, `aria-pressed` selection, decorative selection indicator, correct focus order, and clear focus treatment. Deterministic desktop/mobile keyboard coverage passed. Final reviewed product head: `1503d40a1421a81e4c7b169edbfda0affc6e42d9`.

### Iteration 4 — custom-picker keyboard behavior

**Status:** complete.

Added Enter/Space and Arrow opening, roving focus, Home/End, selection, Escape/focus return, nested Advanced Escape protection, and strong `:focus-visible` states. Multiple remote runs exposed real focus races and nested Escape issues; those were fixed rather than hidden by timing changes. Dedicated success run `32669033886`; implementation commit `9a09522d1c7dac4eed1fd4d6f4d5f4db78582a0f`.

### Iteration 5 — stored video poster thumbnails

**Status:** complete.

Modal gateway extracts a JPEG poster from completed MP4 output; Studio converts it to a 512px WebP thumbnail, persists it to R2/Supabase, and Gallery uses it first. An initial change to `LTX25Worker.generate()` return type was rejected as a compatibility break; final implementation preserves `-> bytes` and moves poster extraction to the gateway. Added `test:poster`. Final reviewed branch head before docs: `44e6f5df0e5e8d97a021078f0d31e21d431a8a81`. Live Modal poster/R2 verification remained blocked by the disabled workspace.

### Iteration 6 — lazy/deferred Gallery video previews

**Status:** complete.

Poster-backed videos attach MP4 only for eligible visible desktop fine-pointer hover or keyboard focus, then pause/detach when intent leaves. Reduced-motion and touch stay poster-only; legacy thumbnail-less rows keep a visible-only fallback. Source review rejected viewport width as a modality proxy; final implementation uses `(hover: hover) and (pointer: fine)`. Validation run `32671818722`, artifact `9501593078`.

### Iteration 7 — unified Video Aspect control

**Status:** complete.

Removed the separate Video Auto button and combined Auto/manual aspect state plus reference provenance in one Aspect picker. First visual review rejected abbreviated `Ref` provenance and found 21:9 partly hidden; final refinement uses `From reference` and exposes all desktop choices without scrolling. Refinement run `32673600494`, artifact `9502051993`, product head `93c4f7005ee651778775fb217892558487c1ede3`.

### Iteration 8 — shared Image/Video AspectPicker

**Status:** complete.

Extracted `features/create/AspectPicker.jsx` and made Image, Edit, and Video consume one shared component/preset source. Review cycles fixed focus handoff, a 2px border-box overflow, and truncated default Auto provenance. Final standard Studio Visual Preview `32676390654`, artifact `9502799506`, reviewed product head `333e32236b116be9a48234abada56582cbfd6ff2`. Modal prefetch remained externally blocked by the disabled workspace.

### Iteration 9 — resolution terminology and delivery dimensions

**Status:** complete.

**Implementation:** standardized user-facing resolution language and separated friendly preset names from exact delivery geometry. Video exposes `480p`, `720p`, `1080p`, and `2K`; picker rows, preview, title, and accessible label show aspect-aware delivered dimensions. The shared effective Aspect state drives those dimensions, including reference-derived Auto ratios. Image uses explicit pixel terminology with computed aspect-aware dimensions. Video 4K was removed because the production workflow/runtime does not currently enable it.

**Deterministic coverage:** `features/create/ResolutionPresets.js` is the shared preset/dimension source and `scripts/check-resolution-contract.mjs` runs in the normal Studio build. The contract verifies canonical 1080p landscape/portrait/4:3 delivery, enabled runtime/workflow parity, and guards against `Full HD`/disabled Video 4K regressions.

**Professional review cycle:** first validation run `32678010842` exposed a stale text expectation after terminology changed; the assertion was corrected while retaining keyboard behavior. Refinement run `32678135023` passed the full visual suite, and validation-generated screenshots/package-lock were removed before final standard validation.

**Validation:** reviewed product head `26fc3501aaaef91fd2e831ec30d5bb41c2caf0da`. Studio CI `32678441763`, Studio Visual Preview `32678441802`, Backend Architecture CI `32678441772`, and Required Check Compatibility `32678441777` passed. Final artifact `9503419570` was inspected. REDGraft Modal remained externally blocked by the disabled workspace.

### Iteration 10 — strengthen the Generate primary action

**Status:** complete.

**Implementation:** promoted the desktop submit control from an icon-only 36px utility circle into a clearly labeled principal action. Image and Video expose `Generate`; Edit exposes `Edit`. The CTA is a restrained high-contrast rounded rectangle with a 112px minimum width, bold verb text, send arrow, subtle elevation, hover/active feedback, and a 2px keyboard focus indicator. Existing mode-specific accessible names (`Generate image`, `Generate video`, `Edit image`) remain intact. The 390px mobile layout deliberately collapses the visible label and retains the compact 36×36 circular arrow.

**Deterministic coverage:** `capture-ui-preview.mjs` now asserts desktop CTA geometry/hierarchy, mode-specific visible verbs and accessible names, strong focus-visible treatment, and compact mobile behavior, and captures dedicated evidence `01b-generate-primary.png`. `check-generate-action-contract.mjs` is part of the normal Studio build and guards the visible verb markup, promoted desktop dimensions, focus treatment, mobile collapse, and corresponding Playwright assertions.

**Professional review cycle:** the successful GitHub product/visual refinement run `32713936104` passed build and the full Playwright suite, uploaded artifact `9515188794`, and committed product implementation `eaec5e4528885b6012f1a43d5e9eb6b2c6d0192d` while restoring temporary validation machinery. Professional review accepted the hierarchy: the desktop CTA is materially more discoverable without overpowering the composer, Video remains balanced despite its denser toolbar, Edit reads contextually, and mobile remains appropriately compact. No Item-10-specific follow-up was required.

**Visual review:** the final standard artifact `9515300251` from Studio Visual Preview `32714238605` was downloaded and inspected across Image `Generate`, Video `Generate`, Edit `Edit`, 390px mobile Create, and Gallery desktop/mobile regression states. No clipping, collision, hierarchy regression, responsive break, or Gallery regression was found. Diagnostics recorded no page errors; only the same generic tolerated resource 404 messages seen in prior preview suites.

**Validation:** final reviewed product head `d66d1f3a40f94b80f153b5b74ed2aa2819874647`. Studio CI `32714238610`, Studio Visual Preview `32714238605`, Backend Architecture CI `32714238464`, and Required Check Compatibility `32714238492` passed. REDGraft run `32714238545` deployed the runtime, then failed at prefetch with `modal.exception.ConflictError: workspace ... is disabled`, so downstream GPU smoke/persistence stages were skipped; this remains the existing external account blocker unrelated to Item 10.

**Professional review:** Item 10 is complete with no remaining actionable comments. **Item 11 — make Audio state explicit and non-color-dependent — is next and remains gated on explicit user approval.**
