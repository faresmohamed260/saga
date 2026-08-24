# SAGA Studio Visual Review Policy

This policy applies to every remaining UI/UX iteration on PR #121 (`studio/video-gallery-ux`). It is a required completion gate, not an optional review step.

## Completion rule

An iteration that changes UI, interaction, responsive layout, or user-visible state is **not complete** merely because Studio CI or Studio Visual Preview passes.

Before marking an iteration complete, the reviewer must:

1. Run the normal GitHub validation suite, including Studio Visual Preview.
2. Download the generated Studio Visual Preview artifact for the final candidate commit.
3. Manually inspect the actual rendered screenshots relevant to the iteration.
4. Inspect both desktop and mobile captures whenever the changed surface exists at both breakpoints.
5. Check for clipping, overflow, collisions, awkward spacing, unreadable text, hierarchy problems, inconsistent alignment, undersized touch targets, broken responsive behavior, stale states, and visual regressions outside the directly changed surface.
6. Review interaction-state captures where relevant, including hover, focus, selected, loading, error, disabled, menu/popover, and Manage-mode states.
7. Treat any item-specific visual problem as a blocker: fix it and repeat CI + artifact inspection until no actionable item-specific issue remains.
8. If manual inspection reveals a separate issue outside the current iteration, record or preserve it as a later checklist item rather than silently ignoring it or expanding scope without review.
9. Record the final Visual Preview run/artifact IDs and a short visual-review conclusion in the canonical checklist/iteration notes before reporting completion.

Automated Playwright assertions remain required, but they supplement rather than replace manual artifact inspection.

## Retroactive review note — Iterations 12–14

The final artifacts for Iterations 12, 13, and 14 were manually reviewed after those iterations had initially been closed from automated validation alone.

- Iteration 12: generation lifecycle feedback is visually coherent on desktop; worker state, next-generation guidance, View Job, and Cancel remain contained in the composer without obscuring the primary generation controls. No Item-12-specific clipping or hierarchy issue was found.
- Iteration 13: desktop bulk Add to Collection integrates cleanly into Gallery Manage mode and selected-card treatment remains clear. No Item-13-specific desktop regression was found.
- Iteration 14: `Select visible` fits the desktop Manage toolbar and accurately describes the loaded-item scope. No Item-14-specific wording/layout regression was found.
- Mobile Manage mode is visibly too dense and cramped in the reviewed artifacts. This is not a regression from Items 13 or 14; it directly confirms the existing next checklist item, Iteration 15 — improve mobile Manage mode with a sticky bottom action bar and larger touch targets.

This policy is mandatory for Iteration 15 and all subsequent UI iterations.
