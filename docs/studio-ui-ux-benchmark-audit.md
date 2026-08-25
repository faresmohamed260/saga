# Studio UI/UX Benchmark & Real-User Audit

Status: **ACTIVE — final audit phase**  
Working branch: `studio/advanced-ui-audit`  
Purpose: persistent handoff document for continuing the Studio UI/UX overhaul across chat sessions.

## Mission

Bring S.A.G.A. Studio to the interaction quality of leading image/video generation products while keeping the interface honest about what the production backend can actually do. Every visible control must either work end-to-end, be explicitly disabled with a reason, or be removed.

## Non-negotiable acceptance criteria

- Test the product through the browser as a real user would, not only through source-level contracts.
- Review desktop and mobile layouts visually after every material UI change.
- Benchmark current image/video creation UX against leading generation products and adopt useful patterns without copying branding.
- Expose all meaningful production worker parameters through understandable UI controls.
- Remove decorative, placeholder, dead, misleading, or unsupported controls/actions.
- Keep image, video, Gallery, Jobs, Uploads, Models, Workflows, Collections, Favorites, Settings, media preview, and batch-management surfaces coherent with each other.
- Preserve accessibility: keyboard navigation, focus visibility, labels, touch targets, reduced-motion behavior, and viewport-safe popovers.
- Keep regression coverage for the repaired interactions and visual surfaces.

## Benchmark products / patterns to research

- Runway
- Adobe Firefly
- Luma Dream Machine
- Midjourney web
- Kling AI
- Leonardo.Ai
- Pika
- OpenAI image/video creation experiences where publicly documented

Research focus:

- composer hierarchy and primary action clarity
- prompt/reference workflow
- model and preset discovery
- aspect ratio / resolution / duration / frame-rate controls
- advanced-parameter disclosure
- progress, queue, retry, cancel, failure recovery
- history/gallery organization
- hover/tap media actions
- batch selection and bulk operations
- mobile adaptation
- empty/loading/error states
- terminology and information density

## Completed in current pass

- [x] LTX fixed step display simplified from `11 + 3`-style/internal schedule notation to user-facing `11`.
- [x] Advanced dropdowns moved out of scroll clipping using viewport-level portals.
- [x] Video frame-rate selector exposes backend-supported `24 / 25 / 30 fps`.
- [x] Image setup Advanced surface exposes live FLUX controls rather than a fake disconnected state.
- [x] Negative prompt exposed and wired for FLUX and LTX.
- [x] Image-mode primary action changed from fake generation to reference-image setup for the live FLUX edit path.
- [x] Placeholder `More` creation surface removed.
- [x] Model/workflow catalog aligned with live production ecosystems.
- [x] New UI/backend contract coverage added.
- [x] Full Studio build/contracts passed on the audit branch after these changes.

## Active audit checklist

### 1. Creation composer
- [ ] Benchmark composer layout against leading products.
- [ ] Audit prompt field height, hierarchy, toolbar density, grouping, and primary CTA.
- [ ] Verify every Image control changes the actual FLUX request.
- [ ] Verify every Video control changes the actual LTX request.
- [ ] Remove remaining legacy `default-image` / `saga-image-auto` state assumptions.
- [ ] Remove dead output-count/workflow/model plumbing if it cannot affect current production execution.
- [ ] Validate reference upload, removal, reorder/mention behavior, and mode transitions.
- [ ] Review advanced-control information architecture and default/reset behavior.
- [ ] Confirm all dropdowns/popovers are viewport-safe at desktop, tablet, and mobile widths.
- [ ] Confirm Generate/Edit/Add-image actions always communicate what will happen before click.

### 2. Progress / jobs
- [ ] Test generation submission through UI with representative success/failure/cancel states.
- [ ] Verify immediate feedback after clicking the primary action.
- [ ] Review progress copy, stage naming, elapsed time, failover messaging, retry/cancel actions.
- [ ] Verify Jobs filters and auto-refresh through browser interaction.
- [ ] Ensure no state can leave the user wondering whether a click worked.

### 3. Gallery / media cards
- [ ] Remove disabled placeholder `Elements` tab unless a real implementation exists.
- [ ] Remove/disable video `Edit` action until a real video-edit workflow exists.
- [ ] Review card aspect handling, thumbnail cropping, preview quality, and size consistency.
- [ ] Test hover video preview and non-hover/touch fallback.
- [ ] Review media action overlay discoverability and tap behavior.
- [ ] Test full-media modal for image/video sizing, metadata, keyboard close, and mobile layout.
- [ ] Verify batch select, select-all, favorite, download, collection, delete, partial failure, and exit behavior.
- [ ] Review filter/search/sort/collections interaction density against benchmark products.

### 4. Uploads / reusable assets
- [ ] Test persistent upload lifecycle end-to-end through UI.
- [ ] Test favorite, rename, download, delete, multi-select, batch actions.
- [ ] Test `Set as Reference` and `Generate Video` transitions into Create.
- [ ] Review whether Uploads belongs as a Gallery tab or deserves a clearer asset-library structure.

### 5. Navigation / catalog / settings
- [ ] Test every sidebar/mobile-nav destination.
- [ ] Audit Models and Workflows for useful actionable information vs. catalog decoration.
- [ ] Audit Settings for dead controls and unclear ownership.
- [ ] Remove any route/tab/button that cannot perform a useful production action.

### 6. Responsive / accessibility
- [ ] Browser-test at ~1440, 1280, 1024, 768, 430, 390, 360, and 320 CSS px.
- [ ] Keyboard-only pass for composer, Advanced, Gallery, modal, Jobs, Uploads, navigation.
- [ ] Validate focus return after dialogs/popovers.
- [ ] Validate reduced-motion behavior for video hover previews and progress animation.
- [ ] Validate touch targets and no horizontal page overflow.
- [ ] Validate readable contrast and secondary text hierarchy.

### 7. Visual benchmark / Figma
- [ ] Capture current Studio key screens into Figma when Figma write access permits.
- [ ] Produce side-by-side design review frames / annotations for Create, Advanced, Gallery, Jobs, Uploads, mobile.
- [ ] Use findings to refine spacing, hierarchy, control grouping, and density in code.
- [ ] Re-capture final states for signoff.

### 8. Automated browser coverage
- [ ] Extend Playwright/capture coverage for all repaired interactions.
- [ ] Add real-user click-path assertions, not only source-string contracts.
- [ ] Verify frame-rate menu bounds and all options visually.
- [ ] Verify Image Advanced live FLUX controls visually.
- [ ] Verify mobile composer and Advanced controls.
- [ ] Verify Gallery hover/tap actions, modal, and batch manager.
- [ ] Run visual-regression comparison after intentional baseline review.

## Definition of done

This audit is complete only when:

1. every visible interactive Studio control has been exercised through the UI;
2. all unsupported/dead UI is removed or clearly disabled;
3. backend-supported generation parameters are represented correctly in the UI;
4. desktop/mobile visual review finds no clipping, overflow, broken hierarchy, or misleading states;
5. browser interaction tests and Studio build/contracts are green;
6. visual-regression output has been reviewed and approved;
7. this checklist is updated with final evidence/commit/run references.

## Progress log

- 2026-08-25: Studio Browser UX Review #19 passed production build/contracts and the Chromium interaction/visual suite, covering Create/Edit/Video/Advanced, Gallery and manager, Uploads, Jobs, keyboard interactions, responsive widths, reduced motion and touch behavior. The workflow cleanup commit advanced the branch beyond its original trigger.
- 2026-08-25: Removed dead Create `outputs`, `workflowId`, and `modelId` React/localStorage plumbing that did not control production execution. Create now labels its mixed session/Favorites surface as Recent work, with session results first. Jobs keeps status/model/progress primary and moves provider/timestamps into Technical details.
- 2026-08-25: Created persistent benchmark/audit tracker after first Advanced-controls repair pass. Initial build/contracts were green on `studio/advanced-ui-audit` at commit `c338ebc02e503eb3ab293b349ad7a9fc8f29052b` before this tracker commit.
