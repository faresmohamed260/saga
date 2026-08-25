# Studio UI/UX Benchmark & Real-User Audit

Status: **COMPLETE — browser, responsive, accessibility, generation, and visual-regression signoff passed**  
Working branch: `studio/advanced-ui-audit`  
Purpose: final evidence record for the Studio UI/UX overhaul.

## Mission

Bring S.A.G.A. Studio to the interaction quality of leading image/video generation products while keeping the interface honest about what the production backend can actually do. Every visible control must either work end-to-end, be explicitly disabled with a reason, or be removed.

## Non-negotiable acceptance criteria

- [x] Test the product through Chromium as a real user would, not only through source-level contracts.
- [x] Review desktop and mobile layouts visually after material UI changes.
- [x] Benchmark current image/video creation UX against leading generation products and adopt useful patterns without copying branding.
- [x] Expose meaningful production worker parameters through understandable UI controls.
- [x] Remove decorative, placeholder, dead, misleading, or unsupported controls/actions.
- [x] Keep image, video, Gallery, Jobs, Uploads, Models, Workflows, Collections, Favorites, Settings, media preview, and batch-management surfaces coherent with each other.
- [x] Preserve keyboard navigation, focus visibility, labels, touch targets, reduced-motion behavior, and viewport-safe popovers.
- [x] Keep regression coverage for repaired interactions and approved visual surfaces.

## Benchmark cross-check

The final hierarchy was cross-checked against current public generation-product patterns, including Runway and Adobe Firefly, with the wider audit reference set including Luma Dream Machine, Midjourney web, Kling AI, Leonardo.Ai, Pika, and publicly documented OpenAI creation experiences.

Patterns retained in Studio:

- prompt/reference-first creation rather than model/provider-first chrome;
- a visually dominant primary action with mode-specific wording;
- generation controls adjacent to the composer, with less-common/model-specific controls in Advanced;
- reference-aware aspect behavior for image-to-video;
- explicit resolution, duration, frame-rate, and audio state where the production model supports them;
- visible generation lifecycle feedback rather than an apparently inert submit action;
- output reuse, favorites, downloads, collections, and batch management directly from media surfaces;
- responsive/mobile adaptation instead of shrinking the desktop layout unchanged.

## Completed implementation

- [x] LTX fixed step display simplified to user-facing `11` while preserving the production two-stage recipe.
- [x] Advanced dropdowns/popovers moved out of clipping contexts and kept viewport-safe.
- [x] Video frame-rate selector exposes backend-supported `24 / 25 / 30 fps`.
- [x] Image/Edit Advanced exposes live FLUX controls and transports their values to the worker request.
- [x] Negative prompt is exposed and wired for FLUX and LTX.
- [x] Image primary action is reference setup for the live FLUX edit path rather than fake original-image generation.
- [x] Placeholder/dead creation surfaces and presentation-only output/workflow/model state were removed.
- [x] Models and Workflows describe the live production ecosystems and route into useful Create actions.
- [x] Jobs prioritizes status/progress/model while provider/timestamps live under Technical details.
- [x] Settings routes users to the generation controls Studio actually owns.
- [x] Gallery has dense cards, hover/focus actions, touch action sheet, media details, manager selection, bulk operations, and no unsupported video Edit action.
- [x] Uploads is a persistent reusable-asset library with preview, search, rename, favorite, delete, batch management, and Create reuse.
- [x] Mobile submit/settings/navigation touch targets are at least 44px where required.
- [x] Production build/contracts and real-browser coverage are part of the audit gate.

## Final audit checklist

### 1. Creation composer
- [x] Benchmark composer layout and control disclosure against leading generation-product patterns.
- [x] Audit prompt field height, hierarchy, toolbar density, grouping, and primary CTA.
- [x] Verify FLUX Edit controls reach the actual request through a real UI submit journey.
- [x] Verify Video controls reach the actual LTX request through a real UI submit journey.
- [x] Remove remaining legacy disconnected/default presentation assumptions from the active Create path.
- [x] Remove dead output-count/workflow/model plumbing that did not affect production execution.
- [x] Validate reference upload, removal, multi-reference mention behavior, cleanup/renumbering, and mode transitions.
- [x] Review Advanced information architecture and default/reset behavior for FLUX and LTX.
- [x] Confirm dropdowns/popovers are keyboard-operable and viewport-safe on desktop, tablet, and mobile.
- [x] Confirm Add image / Edit / Generate labels communicate the next action before click.

### 2. Progress / jobs
- [x] Test FLUX image submission through the visible Add image → Edit flow, including running and completed states.
- [x] Test LTX video submission through the visible Video flow, including reference upload and request transport.
- [x] Verify immediate visible feedback after clicking the primary action and disabled submit while busy.
- [x] Review progress copy, stage naming, elapsed time, failover messaging, View Job, cancel, retry, and terminal states.
- [x] Fix stale worker-state precedence so completed/failed/cancelled terminal job status cannot remain visually stuck on Generating.
- [x] Verify Jobs filters, live-state hierarchy, retry/cancel availability, and refresh behavior through the browser suite.

### 3. Gallery / media cards
- [x] Remove the unsupported placeholder Elements surface from the audited Gallery UX.
- [x] Remove video Edit until a real video-edit workflow exists.
- [x] Review card density, thumbnail framing, video posters, media details, and size consistency.
- [x] Test keyboard and mouse hover video preview plus reduced-motion/touch fallback.
- [x] Fix hover activation so a directly hovered video does not remain poster-only because of stale visibility-observer state.
- [x] Review action-overlay discoverability and mobile action-sheet behavior.
- [x] Test full-media details/preview sizing and keyboard/mobile behavior.
- [x] Verify manager selection, select-all/exit behavior, favorite/download/collection/delete bulk actions covered by the Gallery interaction suite.
- [x] Review search/filter/sort/collections density and responsive behavior.

### 4. Uploads / reusable assets
- [x] Test persistent Uploads lifecycle through the UI.
- [x] Test preview, favorite, rename, download, delete, selection, and batch manager behavior.
- [x] Test Create reuse / reference and video-generation transitions from reusable assets.
- [x] Keep Uploads as an explicit Gallery asset tab with distinct reusable-asset semantics rather than a decorative standalone route.

### 5. Navigation / catalog / settings
- [x] Test every desktop sidebar destination: Create, Jobs, Gallery, Favorites, Collections, Models, Workflows, Settings.
- [x] Test mobile navigation destinations and confirm the drawer closes after navigation.
- [x] Test catalog continuation actions with conflicting saved Create modes; selected catalog intent wins visibly.
- [x] Audit Models and Workflows for production capability information rather than decoration.
- [x] Audit Settings ownership and verify its generation-settings action routes to Create and opens Advanced.
- [x] Remove/avoid routes and actions that imply unsupported production capability.

### 6. Responsive / accessibility
- [x] Browser-test the requested ~1440, 1280, 1024, 768, 430, 390, 360, and 320 CSS-px widths; the suite additionally covers 900, 1100, and 1920 samples.
- [x] Keyboard pass for composer pickers, Advanced, Gallery, Jobs, Uploads, and navigation.
- [x] Validate focus return after popovers and strong `:focus-visible` treatment.
- [x] Validate FPS Space-open → option focus → End → Enter interaction through Chromium.
- [x] Validate reduced-motion behavior for Gallery video preview and progress animation.
- [x] Validate touch targets and horizontal-overflow safety at mobile widths.
- [x] Validate readable contrast, secondary text hierarchy, labels, and non-color state communication through contracts plus screenshot review.

### 7. Visual benchmark / artifact review
- [x] Use GitHub Actions browser artifacts as the final visual-review source of truth; Figma capture was optional and not required for signoff.
- [x] Review final Create/Edit/Video/Advanced, Gallery/manager, Jobs, Uploads, Models, Workflows, Settings, and mobile frames.
- [x] Review dedicated FLUX running/completed screenshots and LTX output-control/generation states.
- [x] Review responsive frames across the requested width matrix.
- [x] Review and approve the 12 deterministic pixel-baseline surfaces before refreshing them.
- [x] Keep animated/morph-only captures available for manual review while excluding nondeterministic animation from pixel gating.

### 8. Automated browser coverage
- [x] Extend Playwright/capture coverage for repaired interactions.
- [x] Use real click, hover, keyboard, file-chooser, focus, and touch-style paths rather than only source-string assertions.
- [x] Verify frame-rate menu bounds/focus and all supported options.
- [x] Verify Image/Edit Advanced live FLUX controls and actual request payload after clicking Edit.
- [x] Verify Video Advanced controls and actual LTX request payload after clicking Generate.
- [x] Verify Gallery hover/focus/tap actions, media details, and manager behavior.
- [x] Verify Uploads, Jobs, navigation, catalog continuation, responsive widths, and mobile Advanced behavior.
- [x] Enforce visual regression in ordinary `visual:preview`; baseline refresh is a separate explicit capture/update path and ordinary review runs cannot rewrite baselines.

## Definition of done

1. [x] Audited visible interactive Studio controls are exercised through real browser journeys.
2. [x] Unsupported/dead audited UI is removed or no longer presented as functional production capability.
3. [x] Backend-supported generation parameters are represented and transported correctly.
4. [x] Desktop/mobile visual review finds no blocking clipping, overflow, hierarchy, or misleading-state defects.
5. [x] Browser interaction tests and Studio build/contracts are green.
6. [x] Visual-regression output is reviewed, approved, refreshed intentionally, and then passes read-only.
7. [x] This checklist contains final evidence and run references.

## Final evidence

- **Studio Browser UX Review #58 — run `32869597748`, trigger commit `b8aa78dc0b7e3d3210ae69553961f63d95cd8456`: PASS.** Build/contracts, production preview, complete real-browser interaction suite, responsive captures, and read-only visual-regression comparison all passed.
- Visual regression on #58: 12/12 approved deterministic surfaces passed. Eleven were pixel-identical; `10-gallery-grid.png` differed by one pixel (`0.0000694%` changed), far below its `0.1%` tolerance. No baseline was rewritten by the acceptance run.
- FLUX UI journey on #58: visible reference chooser → Edit mode → prompt → Advanced → Edit submit → `Generating image` → `Generation ready` → completed Recent work card. The clicked UI submitted `flux2-klein-image-edit`, reference key/MIME/filename, seed `12345`, steps `6`, CFG `1.5`, negative prompt, and reference-derived `≈ 800 × 608 · 0.48 MP`; result polling traversed running to completed with no page errors.
- LTX UI journey: visible Video controls/reference/Advanced/Generate submit transport the production workflow, fixed 11 steps, selected CFG, 30 fps, reference-derived Auto aspect, duration/resolution/audio state, with generation progress visible to the user.
- Navigation diagnostics cover all desktop destinations and mobile Jobs/Gallery/Favorites/Collections/Models/Workflows/Settings; catalog continuation was tested against deliberately conflicting stored media modes.
- Responsive evidence covers Create Video and Gallery at 320, 390, 768, 900, 1024, 1100, 1440, and 1920 px, plus explicit audit captures at 360, 430, and 1280 px and Gallery manager checks at tablet widths.
- Reviewed visual baselines were intentionally refreshed in baseline run `32869377190`; its one-shot refresh workflow self-deleted after promotion. The persistent baseline workflow remains explicit/manual and uses `visual:capture` before update.
- Obsolete audit-bootstrap workflow/helper scripts were removed after signoff so the branch keeps product code, durable tests, durable visual tooling, and this evidence record.

## Progress log

- 2026-08-25: Browser run #19 established the first green production build/contracts + Chromium baseline across Create/Edit/Video/Advanced, Gallery/manager, Uploads, Jobs, keyboard, responsive, reduced-motion, and touch behavior.
- 2026-08-25: Removed dead Create `outputs`, `workflowId`, and `modelId` presentation plumbing; clarified Recent work and Jobs information hierarchy; refined Models, Workflows, Settings, navigation, and mobile settings behavior.
- 2026-08-25: Added missing requested-width coverage and fixed a real 360px 36×36 submit target by enforcing mobile 44px touch safeguards.
- 2026-08-25: Real catalog navigation testing found stored Create mode could override the action the user clicked; mode restoration was moved to the app owner so catalog intent wins.
- 2026-08-25: Keyboard testing found the Advanced FPS portal could render without focusing an option; focus now occurs only after the positioned portal is visibly committed.
- 2026-08-25: Gallery hover testing found actions could appear while deferred video remained inactive; direct hover now activates the preview without waiting on stale intersection state while reduced-motion/pointer safeguards remain.
- 2026-08-25: Added a true FLUX image-generation UI journey. It found and fixed stale worker status overriding completed terminal progress, then passed together with the existing LTX Video journey in run #54.
- 2026-08-25: Restored the pixel-regression comparator to the ordinary browser acceptance command, reviewed/refreshed the intentionally changed baselines, and obtained final read-only green run #58 with all 12 approved surfaces passing.
