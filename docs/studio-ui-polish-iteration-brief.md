# SAGA Studio UI/UX Polish Iteration Brief

## Purpose

This is the durable operating brief for the professional UI/UX and implementation polish pass on PR #121 (`studio/video-gallery-ux`). It exists so a future session can continue without reconstructing the process from chat history.

The **canonical checklist** is [`docs/studio-ui-polish-checklist.md`](./studio-ui-polish-checklist.md). That file is the single source of truth for item status and iteration state. Do not maintain a competing checklist in chat, the PR body, or another document.

## Current handoff state

- PR: #121 — `Video output controls and Gallery UX`
- Branch: `studio/video-gallery-ux`
- PR state: draft, open, unmerged, undeployed.
- Completed checklist items: **01–30**.
- Next item: **none — accepted checklist complete**.
- Do not begin a new numbered item unless the user explicitly defines or approves new scope.
- Development/review previews remain GitHub-based; do not depend on Vercel previews during iteration.
- Latest completed item is Iteration 30. The normal Studio build now executes the production LTX worker's pure delivery math through AST extraction without importing Modal or requiring GPU generation. The deterministic contract covers 204 resolution/aspect/FPS cases and all 78 supported duration/FPS combinations, including six odd/reference ratios and exact rounding ties. It enforces even delivery dimensions, Studio/runtime parity, <=1px nearest-even aspect quantization, 64-aligned internal dimensions, 32-aligned low-stage dimensions, LTX 8n+1 padding, exact delivered frame/duration math, and canonical 1080p landscape/portrait output. Professional review found and fixed a real Python-bankers-rounding mismatch. Final product/test head `7808b2b001a6b1db3ae56b4067cc63c6817310d2` passed Studio CI `32774404109`, Studio Visual Preview `32774404096`, Backend Architecture CI `32774404083`, Modal Worker Inventory `32774404094`, Worker Fleet Live Smoke `32774404126`, and Required Check Compatibility `32774404076`; artifact `9537419708` was downloaded and all eight approved visual baselines had zero changed pixels.

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

The implementation is a coherent product direction rather than a prototype. Items 01–30 are complete, including exact video delivery, Gallery management and architecture cleanup, shared Create controls, lifecycle feedback, product-facing metadata, design tokens, accessibility polish, screenshot-baseline regression, full responsive coverage, and exhaustive deterministic video delivery-contract testing. No accepted checklist item remains.

## Recent iteration log

### Iteration 30 — deterministic video delivery contract

**Status:** complete; accepted checklist complete.

**Implementation:** expanded `apps/studio/scripts/check-resolution-contract.mjs` so the standard `npm run build` contract AST-extracts and executes the production LTX worker's pure dimension/frame functions without importing Modal or starting a GPU. Coverage is 204 resolution/aspect/FPS cases (four enabled resolutions, 11 supported aspect presets, six odd/reference ratios, 24/25/30 FPS) plus 78 duration/FPS cases covering every 5–30 second duration. Assertions cover even delivery dimensions, exact Studio/runtime parity, one-pixel nearest-even aspect quantization, 64-aligned internal dimensions, 32-aligned half-resolution low-stage dimensions, 8n+1 LTX frame padding, exact delivery frame/duration math, ffmpeg finalizer wiring, and canonical 1080p landscape/portrait dimensions.

**Professional review cycle:** the expanded test initially passed its broad matrix, then review added exact odd-pixel tie cases `481:480` / `480:481`. Those exposed a real cross-language defect: Python `round()` uses bankers rounding while Studio's JavaScript uses half-up `Math.round`, allowing a 2px UI/runtime mismatch. Runtime `_even` now performs explicit positive half-up rounding. The first tie-case run then exposed that a fixed 0.10% aspect threshold was impossible for a one-pixel quantization tie at 480p; rather than inflate the threshold, the contract was corrected to the exact physical rule that the flexible edge may differ from ideal by no more than one pixel, with relative tolerance derived per case.

**Validation:** final product/test head before documentation `7808b2b001a6b1db3ae56b4067cc63c6817310d2`. Studio CI `32774404109` passed and reported `matrixCases: 204`, `durationCases: 78`, worst aspect case `480p 481:480 -> 482×480`, canonical landscape `1920×1080`, and portrait `1080×1920`. Studio Visual Preview `32774404096` passed; artifact `9537419708` was downloaded and `visual-regression-report.json` confirmed zero changed pixels on all eight approved surfaces. Backend Architecture CI `32774404083`, Modal Worker Inventory `32774404094`, Worker Fleet Live Smoke `32774404126`, and Required Check Compatibility `32774404076` all passed.

**Professional review:** Item 30 is complete with no remaining item-specific actionable comment. **The accepted Items 01–30 polish checklist is complete. No new numbered item should begin without explicit user scope.**

### Iteration 29 — responsive visual coverage

**Status:** complete.

**Implementation:** added `apps/studio/scripts/capture-responsive-preview.mjs` to the GitHub visual pipeline with required widths 320/390/768/1024/1440/1920 plus transition probes at 900/1100. Create/Video and Gallery are captured at every width; Gallery Manage is captured at 768/900/1024/1100. Assertions reject horizontal overflow, viewport escape, collapsed cards, overlapping Search/Sort controls, and unusably narrow mobile Search/Model controls. `visual:responsive` is available as a direct npm command as well as part of `visual:preview`.

**Professional review cycle:** the first responsive run exposed 20px document overflow in Create/Video at 1024px. The product was fixed by sizing the Create stage to its actual workspace rather than subtracting the sidebar from `100vw`. Artifact inspection then exposed a 320px Gallery Search/Sort collision that overflow assertions alone did not catch, so explicit overlap/minimum-width assertions were added. Those assertions subsequently exposed intrinsic sizing pressure from the density control; the 320px toolbar was reflowed into readable compact rows rather than weakening the test. The intentional 390px toolbar change was reviewed, its approved Gallery Manage baseline was refreshed explicitly, and the temporary connector-only refresh trigger was removed with the baseline workflow restored to manual-only.

**Validation:** final product/visual head before documentation `c2b95923686a338b93eb6aade3b8cfe1cf08a6ca`. Studio Visual Preview `32771622937` passed 20 responsive captures and all eight approved visual-regression surfaces with `0` changed pixels; artifact `9536443571` and `responsive-diagnostics.json` were downloaded and inspected. The final diagnostics recorded no horizontal overflow or page errors; mobile Search widths were 168px at 320 and 174px at 390, both above the 140px contract. Studio CI `32771622957`, Backend Architecture CI `32771622891`, Modal Worker Inventory `32771622900`, Worker Fleet Live Smoke `32771622860`, and Required Check Compatibility `32771622922` all passed.

**Professional review:** Item 30 is complete with no remaining item-specific actionable comment. **Items 01–30 and the accepted polish checklist are complete; no new numbered item should begin without explicit user scope.**

### Iteration 27 — typography/contrast accessibility

**Status:** complete.

Raised the dense text tiers to a 10/11/12px minimum, strengthened muted/subtle contrast, added a shared focus halo, and reinforced selected states with semantic and non-color cues. Final artifact `9534555187` from Studio Visual Preview `32766234976` was manually inspected across desktop Create, picker focus, desktop Gallery, and 390px mobile Manage. Standard validation passed.

### Iteration 28 — true visual regression

**Status:** complete.

**Implementation:** added `apps/studio/scripts/check-visual-regression.mjs`, a versioned `apps/studio/visual-baselines/manifest.json`, eight approved baseline PNGs, and the `visual:regression` npm command. The standard Studio Visual Preview now captures the existing Playwright evidence and then compares approved deterministic surfaces against baselines. Meaningful changed-pixel drift fails CI; the artifact contains current screenshots, `visual-regression-report.json`, and highlighted diff PNGs. `.github/workflows/studio-visual-baseline.yml` is a manual-only workflow for intentional reviewed baseline refreshes; ordinary PR runs never rewrite baselines.

**Professional review cycle:** the first baseline-backed run did exactly what the new system is meant to do: it rejected `02b-image-picker-keyboard-focus.png` at `0.845%` changed pixels while all other gated surfaces were pixel-identical. Inspection of the generated highlighted diff showed the differences were isolated to the Aspect picker morph/focus animation capture, not a product regression. The gate was not weakened and the tolerance was not inflated; that inherently animated screenshot remains available for manual preview review but was removed from pixel gating. This leaves eight stable representative surfaces covering Create, Video controls/focus/audio, 390px Create, Gallery, Gallery focus, and 390px Manage.

**Validation:** final product/visual head before documentation `b390aea21f46225d2a2a8b0a209ac8154a03633b`. Studio Visual Preview `32768394649` passed the regression comparison with `0` changed pixels on all eight gated surfaces; artifact `9535309218` was downloaded and its JSON report inspected. Studio CI `32768394643`, Backend Architecture CI `32768394714`, Modal Worker Inventory `32768394650`, Worker Fleet Live Smoke `32768394705`, and Required Check Compatibility `32768394739` all passed.

**Professional review:** Item 30 is complete with no remaining item-specific actionable comment. **Items 01–30 and the accepted polish checklist are complete; no new numbered item should begin without explicit user scope.**
