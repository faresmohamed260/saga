# S.A.G.A. v2 UI / UX System

## Objective

Define a reusable, deliberate UI system for a narrative-intelligence workspace without turning S.A.G.A. into either a generic admin dashboard or a visual clone of RenderLab.

RenderLab's UI documentation is a read-only process/reference source. S.A.G.A. adopts the useful discipline—maintained primitives, semantic tokens, responsive/accessibility rules, explicit redesign/fidelity gates—while owning its own visual identity and product composition.

## Product UX Principle

**Narrative first, complexity on demand.**

S.A.G.A. should make stories, source text, evidence, characters, places, relationships, timelines, canon and media feel primary. Internal orchestration/model/provider details remain hidden unless an advanced/admin surface genuinely needs them.

Design priorities:

- narrative/evidence clarity;
- strong information hierarchy;
- compact professional density without crowding;
- progressive disclosure;
- minimal chrome around dense story work;
- spatial continuity between related story objects;
- consistent reusable mechanics;
- accessibility and touch/keyboard parity;
- purposeful motion where it helps the user understand state/continuity.

## Visual Character

S.A.G.A. should feel like a premium narrative research/creative workspace: part story bible, part evidence desk, part temporal/world map, part authoring environment.

It should **not** feel like:

- a cloud-admin panel;
- a collection of identical cards;
- an AI-provider playground;
- a ComfyUI/node graph mirror;
- a copy of RenderLab's dark creative-media identity;
- a fantasy-themed decorative site that sacrifices information density/readability.

The final brand palette/type pairing is deliberately not locked in this document. It must come from a S.A.G.A.-specific visual concept/review pass.

## Surface Expressiveness

Different surfaces have different motion/visual ceilings.

| Surface | Ambition | Direction |
|---|---:|---|
| Public landing | 4/4 | Highest-expression storytelling/brand surface; richer typography/graphics/choreography may be explored. |
| Project workspace | 3/4 | Signature narrative instrument; strong spatial continuity among source, entities, evidence and story views. |
| Timeline / relationship / world views | 3/4 | Direct manipulation and object continuity where useful; dense data remains legible. |
| Library / source viewer | 3/4 | Reading/media/evidence continuity; focused source interaction. |
| Home / Activity | 2/4 | State-driven polish; calm operational overview. |
| Application shell | 2/4 | Tactile navigation continuity subordinate to content. |
| Settings | 1/4 | Calm trust/security emphasis. |
| Admin | 1/4 | Operational clarity first. |

These are ceilings, not quotas. Lower motion intensity never means lower craft.

## Two Work Modes

### Integration Mode — default

Use for ordinary feature work after a surface has an accepted design language.

1. Read current repository decisions and UI rules.
2. Inspect the current rendered surface when presentation is affected.
3. Integrate the feature using existing primitives/patterns.
4. Run deterministic and responsive/accessibility gates.
5. Inspect rendered output.
6. Update docs only from verified implementation.

### Visual R&D / Authorized Redesign Mode

Use when the owner explicitly asks to redesign, modernize, reimagine or establish a major new visual surface.

1. Define what product/architecture/security contracts remain fixed.
2. Build a reference matrix for important interactions.
3. Produce complete concepts for desktop and narrow/mobile plus important states.
4. Write interaction choreography before choosing animation mechanics.
5. Prototype signature temporal behavior when screenshots cannot prove it.
6. Obtain explicit design approval for the concept/prototype.
7. Treat the accepted concept as implementation specification.
8. Validate functional correctness and visual fidelity separately.

A static concept can approve composition/palette/type/spacing, but it cannot by itself approve claimed morphing/physics/temporal behavior.

## Design-Before-Code Gate for Major New Surfaces

For a new shell/workspace/landing redesign, concept work must cover the **complete requested surface**, not only a hero or one card.

Before production implementation, capture:

- visible copy and information architecture;
- desktop layout;
- narrow/mobile layout;
- container model (rails, panels, lists, canvas, editor, table, etc.);
- typography hierarchy;
- semantic tokens/palette direction;
- component families;
- icon style;
- interaction states;
- motion/reduced-motion intent;
- accessibility needs;
- asset/media needs.

Do not improvise major unapproved component families during implementation because they are convenient.

## Component Source Policy

Do not repeatedly implement solved conventional control mechanics from scratch.

Preferred source order:

1. existing approved S.A.G.A. component;
2. existing S.A.G.A. primitive;
3. shadcn/ui + Radix (or equivalent maintained accessible primitive) where suitable;
4. Motion Primitives / Motion for React for deliberate interaction continuity;
5. another reviewed maintained source such as Aceternity UI, Magic UI or React Bits when it provides a suitable mechanic and passes accessibility/performance/license review;
6. S.A.G.A.-specific product composition from approved primitives;
7. custom interaction mechanics only when no suitable maintained source satisfies the product requirement.

External components are mechanics/reference—not visual authority. Normalize them to S.A.G.A. tokens and interaction rules.

## Primitive Purity Direction

As Phase 1 grows, conventional visible controls in `src/features` and `src/components/shell` should use the normalized primitive layer rather than locally hand-styled raw elements.

Native hidden/file inputs may remain browser plumbing where appropriate.

Initial likely primitives:

- Button / IconButton
- Input / Textarea
- Label / Field / Error
- Select
- Dropdown Menu
- Dialog / Alert Dialog
- Sheet / Drawer
- Tabs / Toggle Group
- Tooltip
- Checkbox / Switch
- Separator
- Spinner / Skeleton / Alert / Toast
- Empty-state composition

Do not install every primitive in advance. Add one when the first real surface needs it, normalize it once, test it, then reuse it.

A future `verify:ui-purity`-style structural check is appropriate once Phase 1 has enough feature/shell code for the rule to be enforceable.

## Semantic Tokens

Use semantic tokens rather than arbitrary values once the first accepted visual concept establishes them.

Token families should include:

- canvas/background;
- surface hierarchy;
- border/separator;
- primary/secondary/muted text;
- accent/focus;
- success/warning/danger/info;
- evidence/confidence/canon-specific semantics only when product meaning is clear;
- spacing;
- radii;
- elevation/shadow/blur;
- control heights;
- typography scale;
- motion timing/springs;
- z-index layers.

Do not assign different arbitrary colors to every entity type or confidence value without a semantic accessibility plan.

## Typography

S.A.G.A. needs two complementary typography roles:

1. **Application chrome / data UI** — compact, highly legible, neutral enough for dense controls/tables.
2. **Narrative/source content** — optimized for longer reading, excerpts, evidence and story writing.

The exact fonts are not locked until concept review. Avoid oversized marketing typography inside the application workspace.

Typical hierarchy should distinguish:

- page/workspace title;
- section heading;
- body/narrative text;
- UI labels;
- metadata/captions;
- code/IDs only when an admin/debug surface genuinely needs them.

## Layout / Container Rules

Avoid solving every surface with cards.

Prefer the container model that matches the task:

- rails for global/project navigation;
- open lists/tables for source/entity collections;
- split views for source + evidence/detail;
- canvases for relationship/world exploration;
- timeline lanes/tracks for temporal views;
- editor/document surfaces for story/canon text;
- drawers/sheets for contextual secondary controls;
- dialogs only for bounded decisions/forms;
- cards only when an item genuinely benefits from standalone framed identity.

Avoid card-within-card-within-card hierarchies. Use alignment, whitespace, tonal surface changes, separators and rails before adding another rounded container.

## Application Shell Direction

The shell owns only global navigation/account/activity context and the route-content frame.

It must not permanently reserve space for feature-specific inspectors or future AI controls.

Desktop direction:

- compact persistent navigation is acceptable;
- content/workspace gets most horizontal area;
- current project context may be exposed without duplicating a full top nav;
- Admin is shown only to authorized admins;
- Activity/status becomes prominent only when there is real state requiring attention.

Narrow/mobile direction:

- do not shrink desktop rails into unusable strips;
- primary destinations use a compact touch-friendly treatment;
- secondary/project-specific controls move into sheets/disclosures;
- preserve the current task, account access, project/source navigation and important state;
- avoid vertically reproducing all desktop chrome.

Exact shell geometry belongs to the accepted Phase-1 visual concept.

## Narrative Workspace Principles

### Projects

A project is the main story workspace, not merely a card leading to unrelated pages.

Preserve continuity as the user moves among:

- source material;
- characters;
- locations/world;
- timeline/events;
- canon/evidence;
- story/planning;
- media.

### Evidence / Canon

Evidence needs traceability and reading clarity. Avoid visual treatments that make confidence/provenance decorative rather than understandable.

### Characters / Relationships

Relationships may benefit from spatial/canvas views, but accessible list/detail alternatives remain important. Do not make essential data discoverable only through a graph hover state.

### Timeline

Time-axis anatomy and event ordering are product truth. Motion may help navigation/selection but must not fabricate chronology or uncertainty.

### Story / Planning

Writing/planning surfaces prioritize content and editing focus. Advanced generation/AI controls later use progressive disclosure rather than permanently crowding the editor.

## Motion Principles

Motion explains:

- where a selected story object came from;
- what moved/changed state;
- how navigation/context relates spatially;
- direct manipulation/reorder/attachment;
- opening/closing contextual tools;
- real job/activity transitions later.

Prefer transform/layout/spring behavior when continuity matters. Opacity-only fades are fine for low-importance supporting content but should not become the defining interaction language of a signature workspace.

Do not animate fake analysis progress, confidence, model stages, ETA, queue position, authorization or availability.

Every animated interaction needs a complete `prefers-reduced-motion` equivalent.

## Responsive Rules

Desktop is the primary productivity target, but responsiveness is part of the initial design, not cleanup.

- wide desktop: dense workspaces may expose related rails/inspectors without excessive line lengths;
- standard desktop/tablet: compress secondary chrome before degrading the primary reading/work area;
- narrow/mobile: move secondary controls into sheets/disclosures and preserve reading, navigation and key actions;
- no essential hover-only behavior;
- icon-only actions need accessible names and adequate effective touch targets;
- avoid horizontal overflow/clipped primary content.

Tailwind defaults may be used initially; introduce custom breakpoints only after rendered evidence justifies them.

## Accessibility Baseline

Target WCAG 2.2 AA behavior for normal product UI.

Required:

- keyboard operability;
- visible focus;
- semantic headings/landmarks;
- maintained menu/dialog/form semantics;
- no status meaning by color alone;
- accessible names for icon-only actions;
- focus trap/restore for modal surfaces;
- no hover-only essential actions;
- touch reachability;
- sufficient contrast;
- reduced-motion support;
- alternate accessible representation when a visual graph/canvas cannot convey all information to assistive technology.

## Visual Fidelity Gate

Functional QA and visual-fidelity QA are separate.

After an approved concept is implemented, compare the real browser render against the accepted concept for at least:

- copy/hierarchy;
- typography;
- spacing/alignment;
- palette/surface depth;
- container model;
- component geometry;
- icon treatment;
- media/source/evidence framing;
- desktop/narrow behavior;
- motion origin/destination/timing when applicable;
- keyboard/focus/touch/reduced-motion equivalents.

A passing build does not make a materially generic or drifting implementation approved.

## Performance

Prefer:

- compositor-friendly transforms/opacity;
- event-driven motion rather than permanent loops;
- lazy heavy public/visual effects;
- native scrolling for ordinary app surfaces;
- one primary motion runtime for application UI;
- explicit justification before adopting a second animation runtime, smooth-scroll layer, canvas/WebGL scene or continuous pointer loop.

## RenderLab Reference Disclaimer

The governance/process ideas in this document were informed by mature RenderLab UI documentation, but the product semantics and final visual system are S.A.G.A.'s. RenderLab assets, tokens, routes, components and compositions are not imported or made authoritative here.