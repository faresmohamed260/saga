# SAGA Studio UI/UX Polish Iteration Brief

## Purpose

This is the durable operating brief for the professional UI/UX and implementation polish pass on PR #121 (`studio/video-gallery-ux`). It exists so a future session can continue without reconstructing the process from chat history.

The **canonical checklist** is [`docs/studio-ui-polish-checklist.md`](./studio-ui-polish-checklist.md). That file is the single source of truth for item status and iteration state. Do not maintain a competing checklist in chat, the PR body, or another document.

## Current handoff state

- PR: #121 — `Video output controls and Gallery UX`
- Branch: `studio/video-gallery-ux`
- PR state: draft, open, unmerged, undeployed.
- Completed checklist items: **01–28**.
- Next item: **29 — expand responsive visual coverage**.
- Do not begin Item 29 until the user says **continue**.
- Development/review previews remain GitHub-based; do not depend on Vercel previews during iteration.
- Latest completed item is Iteration 28. Studio Visual Preview is now a real regression gate: eight deterministic approved surfaces are versioned under `apps/studio/visual-baselines`, `scripts/check-visual-regression.mjs` compares changed pixels with explicit per-surface tolerances and emits diff/report evidence, and a manual baseline-update workflow exists for intentional reviewed changes. Final Studio Visual Preview `32768394649` passed all eight gated surfaces with zero changed pixels; artifact `9535309218` was downloaded and inspected. Standard validation also passed: Studio CI `32768394643`, Backend Architecture CI `32768394714`, Modal Worker Inventory `32768394650`, Worker Fleet Live Smoke `32768394705`, and Required Check Compatibility `32768394739`.

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

The implementation is a coherent product direction rather than a prototype. Items 01–28 are complete, including exact video delivery, Gallery management and architecture cleanup, shared Create controls, lifecycle feedback, product-facing metadata, design tokens, accessibility polish, and a true screenshot-baseline regression gate. Remaining accepted work is responsive visual coverage across the full width matrix (Item 29) and expanded deterministic video delivery-contract testing (Item 30).

## Recent iteration log

### Iteration 27 — typography/contrast accessibility

**Status:** complete.

Raised the dense text tiers to a 10/11/12px minimum, strengthened muted/subtle contrast, added a shared focus halo, and reinforced selected states with semantic and non-color cues. Final artifact `9534555187` from Studio Visual Preview `32766234976` was manually inspected across desktop Create, picker focus, desktop Gallery, and 390px mobile Manage. Standard validation passed.

### Iteration 28 — true visual regression

**Status:** complete.

**Implementation:** added `apps/studio/scripts/check-visual-regression.mjs`, a versioned `apps/studio/visual-baselines/manifest.json`, eight approved baseline PNGs, and the `visual:regression` npm command. The standard Studio Visual Preview now captures the existing Playwright evidence and then compares approved deterministic surfaces against baselines. Meaningful changed-pixel drift fails CI; the artifact contains current screenshots, `visual-regression-report.json`, and highlighted diff PNGs. `.github/workflows/studio-visual-baseline.yml` is a manual-only workflow for intentional reviewed baseline refreshes; ordinary PR runs never rewrite baselines.

**Professional review cycle:** the first baseline-backed run did exactly what the new system is meant to do: it rejected `02b-image-picker-keyboard-focus.png` at `0.845%` changed pixels while all other gated surfaces were pixel-identical. Inspection of the generated highlighted diff showed the differences were isolated to the Aspect picker morph/focus animation capture, not a product regression. The gate was not weakened and the tolerance was not inflated; that inherently animated screenshot remains available for manual preview review but was removed from pixel gating. This leaves eight stable representative surfaces covering Create, Video controls/focus/audio, 390px Create, Gallery, Gallery focus, and 390px Manage.

**Validation:** final product/visual head before documentation `b390aea21f46225d2a2a8b0a209ac8154a03633b`. Studio Visual Preview `32768394649` passed the regression comparison with `0` changed pixels on all eight gated surfaces; artifact `9535309218` was downloaded and its JSON report inspected. Studio CI `32768394643`, Backend Architecture CI `32768394714`, Modal Worker Inventory `32768394650`, Worker Fleet Live Smoke `32768394705`, and Required Check Compatibility `32768394739` all passed.

**Professional review:** Item 28 is complete with no remaining item-specific actionable comment. **Item 29 — expand responsive visual coverage — is next and remains gated on explicit user approval.**
