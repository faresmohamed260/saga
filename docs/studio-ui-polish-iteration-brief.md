# SAGA Studio UI/UX Polish Iteration Brief

## Purpose

This document is the durable handoff and operating brief for the professional UI/UX and implementation polish pass on PR #121 (`studio/video-gallery-ux`). It is intentionally stored in GitHub so a future ChatGPT session can continue without reconstructing the process from chat history.

The **canonical checklist** is stored separately at [`docs/studio-ui-polish-checklist.md`](./studio-ui-polish-checklist.md). That checklist is the single source of truth for item status and iteration state. Every iteration must update it before reporting back to the user. Do not maintain a competing checklist in chat or another file.

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
   - update the canonical checklist and this iteration log on GitHub;
   - **stop after the iteration** and report to the user what changed, what the professional review found, the updated checklist, CI status, and visual evidence. Wait for the user to say continue or stop.
6. Every iteration must provide visual feedback. If the iteration is backend-only, still inspect and provide a current visual-regression screenshot to prove no UI regression, and explicitly state that no deliberate visual change was expected.
7. Do not call an iteration complete merely because tests pass. The visual artifact must be inspected by the professional reviewer.
8. Continue the implementation → visual review → professional critique → improvement cycle inside the current checklist item until that item has no remaining actionable comments; then close the iteration and wait for the user.
9. Favor reusable components, explicit state/data flow, accessibility, performance, and maintainability over one-off CSS/DOM patches.
10. Do not silently weaken tests to make them pass. If a visual or correctness test exposes a real problem, fix the product.
11. Before starting a new session or iteration, read this brief and the canonical checklist from the branch so the process cannot drift.

## Definition of done for the whole pass

The pass is finished only when all accepted checklist items are complete, current GitHub checks are green, visual-regression screenshots are reviewed at the agreed breakpoints, the professional review produces no further actionable comments, and the user approves ending the iteration cycle.

## Professional-review baseline

The current implementation is a credible product direction rather than a broken prototype. Strengths: cohesive dark visual language, centered Create composer, corrected 1080p path, useful generation status, much better Gallery density/selection mode, and a strong remote GitHub preview discipline. Main weaknesses: action density, mobile touch ergonomics, accessibility semantics/keyboard behavior, video-thumbnail performance, ambiguous Auto/aspect state, brittle portal/querySelector composition, growing App.jsx responsibility, and CSS specificity debt.

## Iteration log

### Iteration 1 — exact video delivery duration

**Status:** complete.

**Implementation:** preserved LTX-required 8n+1 internal frames while enforcing an exact user-facing delivery contract. The first ffmpeg `-t` approach was rejected after the live 25 FPS generated-audio smoke delivered 5.160000 seconds for a requested 5 seconds. The final approach explicitly clamps delivered video frames (`duration_seconds × frame_rate`) and trims/resets audio timestamps.

**Validated results:** 24 FPS muted T2V = 5.000000 s; 25 FPS generated-audio T2V = 5.000000 s with H.264 + AAC; 30 FPS gateway I2V = 5.000000 s. Studio CI, Studio Visual Preview, Backend Architecture CI, Required Check Compatibility, Modal smoke, and live R2/Supabase persistence all passed on the validated product head. Visual inspection found no UI regression.

**Professional review:** duration correctness is resolved. No new visual issues introduced.

### Iteration 2 — Gallery action density and mobile touch safety

**Status:** complete.

**Implementation:** reduced desktop per-card immediate actions from seven to four: Favorite, Download, Open, and More. Reuse, Edit, Add/Remove collection, and Delete moved into the More menu. Mobile now shows only Favorite, Open, and More as immediate actions; Download moves into More. Mobile action targets are at least 44px and are visible without hover. Delete is separated from routine actions and styled as destructive in overflow.

**Deterministic checks:** visual-preview assertions now verify four visible desktop primary actions, three visible mobile primary actions, no immediate Delete action, expected More contents, and minimum mobile touch-target size.

**Professional review cycle:** the first visual review found that the initial mobile More implementation was clipped by the card/overlay containing block, so only the lower overflow actions were visibly usable. That implementation was not accepted. The mobile overlay backdrop-filter was removed as a containing block, allowing the fixed More surface to span the viewport. A second GitHub visual-preview run was inspected and confirmed the More surface now renders at full mobile width with safe margins, all secondary actions visible, and Delete separated.

**Validation:** Studio CI, Studio Visual Preview, Backend Architecture CI, and Required Check Compatibility passed on the final Iteration 2 product head `2cd1a0de5ac3c55b2f9af9eca905e1cafc081c9e`. The REDGraft Modal smoke is unrelated to this UI-only item and continued independently on the PR.

**Professional review:** no remaining action-density or mobile touch-safety comments for item 02. The next highest-priority item is **03 — refactor MediaCard interaction semantics/accessibility**. That remains separate so accessibility work is handled deliberately rather than mixed into the visual-density pass.
