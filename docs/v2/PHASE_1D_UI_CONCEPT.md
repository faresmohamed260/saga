# S.A.G.A. v2 Phase 1D UI Concept — Narrative Desk

**Status:** APPROVED — owner approved on 2026-09-11 for Phase 1D production implementation

**Phase:** V2.1D

**Parent contract:** `docs/v2/UI_SYSTEM.md`

## Purpose

Establish a complete S.A.G.A.-owned visual and interaction direction for the first authenticated application shell plus Home, Library, and Projects before production UI implementation begins.

This concept intentionally does not copy RenderLab and does not extend the Phase-0 landing-page composition into the private application by default.

## Fixed Product / Architecture Contracts

The concept does not change these existing decisions:

- closed-demo access remains invitation-only;
- private routes remain behind fresh Supabase identity verification plus active S.A.G.A. account access;
- Server Components remain the default;
- the shell owns global navigation/account context only;
- feature-specific inspectors and future AI controls do not live permanently in the shell;
- Home, Library, and Projects are the first Phase-1D product footholds;
- no fake project/source/analysis/job state may be invented to make the UI appear populated;
- agent/LLM runtime work remains out of scope.

## Review of the Current UI

The existing public landing page is appropriate as a foundation-era brand surface, but its private-workspace language should not be copied wholesale.

Current characteristics that should stay primarily public-facing:

- violet/cyan glow as a dominant visual device;
- floating glass-panel composition;
- repeated framed mini-cards;
- large marketing typography;
- decorative grid/background effects.

The Phase-1C `/home` route is intentionally only an access checkpoint and therefore establishes no durable private-workspace visual language.

The private application is free to adopt a calmer, denser, more editorial identity that better fits sustained narrative research and writing.

## Selected Concept Candidate: Narrative Desk

**Narrative Desk** treats S.A.G.A. as a premium editorial/research instrument rather than an AI dashboard.

The visual metaphor is a modern story desk: dark graphite application chrome, warm neutral text, broad uncluttered working space, precise separators, editorial typography, and restrained use of one brand accent.

The desired feeling is:

- serious enough for evidence/canon work;
- calm enough for long reading and writing sessions;
- modern enough to feel like a current creative tool;
- spatially coherent enough to grow into timelines, relationship views, source readers, and story editors later;
- clearly distinct from a generic admin SaaS dashboard.

## Desktop Shell

### Geometry

Use one persistent left global rail at approximately **216–232 px** wide on ordinary desktop widths.

The rail contains only global product context:

1. S.A.G.A. wordmark / product identity;
2. Home;
3. Library;
4. Projects;
5. later Activity when real activity exists;
6. Settings near the lower rail;
7. Admin only for active admins;
8. account affordance at the bottom.

The content plane owns the rest of the viewport.

Do not add a second permanent top navigation bar. Each route owns its own local page header inside the content plane. A future project workspace may add project-local navigation inside that workspace without expanding the global rail into a feature control center.

### Content Frame

- shell canvas fills the viewport;
- rail uses a subtly distinct tonal surface rather than glass blur;
- content uses open alignment and separators before bordered containers;
- ordinary route content receives roughly 28–40 px desktop gutters;
- lists may span broad widths while prose/reading content later constrains line length independently;
- no permanent right inspector in Phase 1D.

## Narrow / Mobile Shell

Do not shrink the desktop rail into a narrow icon strip.

Use:

- a compact ~56 px top bar;
- product mark at the start;
- current route title/context in the center/available space;
- one menu/account trigger at the end;
- a touch-friendly navigation sheet for Home, Library, Projects, Settings, and authorized Admin;
- page content directly below with 16–20 px gutters.

Project-specific controls later move into contextual sheets/disclosures rather than stacking all desktop chrome vertically.

The mobile shell must preserve the current task first; persistent navigation visibility is less important than readable narrative/product content.

## Typography

Use two deliberate roles.

### UI / chrome

**Geist Sans** or an equivalent compact neutral sans with system fallbacks.

Use for:

- navigation;
- controls;
- metadata;
- labels;
- tables/lists;
- page titles where dense UI hierarchy matters.

### Narrative / reading

**Source Serif 4** or a comparable highly legible editorial serif with `ui-serif`/Georgia fallbacks.

Reserve for:

- source excerpts;
- evidence quotations;
- story prose;
- long-form canon/narrative reading surfaces.

Phase 1D may establish the font token without forcing serif text onto Home/Library/Projects where no narrative excerpt exists yet.

Avoid oversized marketing-scale headings inside the authenticated application.

## Palette Direction

The private app keeps dark-mode continuity with the current product while removing glow as the primary depth mechanism.

Initial semantic direction:

| Token role | Direction |
|---|---|
| Canvas | near-black graphite, around `#0B0C0E` |
| Global rail | slightly lifted neutral, around `#101215` |
| Primary surface | `#15181C` range |
| Elevated/context surface | `#1B1F24` range |
| Separator/border | restrained neutral, around `#2A2F35` |
| Primary text | warm off-white, around `#F0EDE6` |
| Muted text | neutral warm gray, around `#9B9C98` |
| Brand accent | restrained iris/periwinkle, around `#8F83FF` |
| Focus accent | brighter accessible companion to brand accent |
| Future reading paper | warm light neutral, around `#E9E4D9`, with dark ink text |

The exact values must be contrast-checked during implementation and may move slightly while preserving the approved visual relationships.

Do not assign decorative colors per entity type. Evidence/canon/confidence colors are introduced only when their semantics exist and have an accessibility plan.

## Iconography

Use Lucide as the default icon family already present in the product.

Direction:

- mostly 17–19 px in application chrome;
- approximately 1.7–1.9 stroke width;
- do not place every icon in a colored square tile;
- active navigation state is communicated by position/background/type plus `aria-current`, not icon color alone;
- icon-only controls require accessible names and tooltips where discoverability needs them.

## Home Surface

Home should be a calm orientation surface, not an analytics dashboard.

Phase-1D composition:

1. compact page heading and one-sentence product context;
2. one primary workspace section that directs the user toward Library and Projects;
3. honest empty/availability states where product data/workflows do not exist yet;
4. no fabricated counts, recent projects, progress bars, activity, model status, or analysis results.

When real project/source state exists later, Home may evolve toward open recent-work lists and attention items, not a grid of KPI cards.

## Library Surface

Library is designed as a future source/evidence workspace.

Phase-1D composition should establish:

- page heading and restrained supporting copy;
- an open list/table container model rather than source cards;
- space for future search/filter/sort without rendering non-functional controls prematurely;
- an honest empty state in the content plane when no real source repository exists yet;
- clear future path to source title, type, edition/file metadata, project associations, and ingestion state once those contracts ship.

A future source reader may use a warm paper-toned reading surface inside the dark application shell, creating a purposeful distinction between application chrome and narrative text.

## Projects Surface

Projects are story workspaces, not generic tiles.

Phase-1D composition should establish an open project list pattern:

- project title is primary;
- secondary metadata aligns consistently when it becomes real;
- rows may expose a small cover/art marker later but should not require one;
- the list has enough visual identity to become a project launcher without turning into a gallery of oversized cards;
- the empty state remains honest until project creation/persistence is implemented.

Future project-local navigation can grow from this model into Characters, World, Timeline, Canon, Story, and Media while preserving global shell continuity.

## Container / Component Families

Phase 1D should introduce only the primitives/compositions needed by the real shell:

- `AppShell`;
- `NavigationRail`;
- `MobileNavigationSheet`;
- `PageHeader`;
- `NavItem` using maintained/link semantics;
- `AccountMenu` or bounded account affordance;
- `Separator`;
- `Sheet` / drawer primitive for narrow navigation;
- `Tooltip` for compact icon affordances if needed;
- reusable `EmptyState` composition;
- reusable open-list/list-row composition when Library/Projects need it.

Do not create a universal `Card` abstraction as the primary layout solution for Phase 1D.

Conventional menu/sheet/tooltip mechanics should use maintained accessible primitives rather than bespoke focus-management code.

## Interaction Choreography

The shell should feel tactile but quiet.

Approved motion intent:

- active navigation indicator may translate/morph between destinations;
- mobile navigation sheet enters from the logical navigation edge;
- route-local content may use a very small one-time transition only when it helps continuity;
- hover/focus states should be immediate and restrained;
- no permanent floating, pulsing, shimmer, glow loops, or fake status motion in the private app.

Typical transition duration should remain roughly **160–220 ms** for simple UI state. Spring behavior is reserved for direct/spatial continuity where it materially helps.

With `prefers-reduced-motion`, navigation and disclosure remain fully understandable with static state changes.

## Accessibility Contract

Phase 1D must prove:

- semantic `nav`, `main`, headings, and lists;
- `aria-current="page"` for active navigation;
- visible keyboard focus against every surface tone;
- keyboard-operable navigation sheet/account menu;
- focus trap and restore for modal/sheet primitives;
- effective touch targets near 44×44 px on narrow layouts;
- no hover-only essential affordances;
- no status communicated only by color;
- no horizontal overflow at ordinary narrow widths;
- reduced-motion behavior when motion is added.

## Responsive Breakpoint Intent

Use existing Tailwind breakpoints initially.

- wide desktop: persistent global rail + broad content plane;
- ordinary desktop/tablet landscape: same model with tighter gutters/rail width;
- below the point where the rail meaningfully competes with content, switch to the compact mobile top bar + navigation sheet;
- do not introduce custom breakpoints until rendered evidence demonstrates a need.

## What Phase 1D Must Not Pretend Exists

Until backed by real product contracts, do not render believable-looking fake:

- source files/editions;
- projects/stories;
- character counts;
- canon facts;
- analysis status;
- recent activity;
- jobs/progress;
- storage usage;
- AI/model/provider status.

Honest empty states are part of the product design, not a temporary failure to make the screen look full.

## Phase 1D Visual Acceptance Criteria

Before the implementation PR can be considered visually ready:

1. desktop shell shows one restrained global rail and content-first route frame;
2. narrow shell switches to a touch-friendly top bar/sheet rather than a compressed desktop rail;
3. Home, Library, and Projects share shell language but use task-appropriate open compositions rather than repeated cards;
4. application typography is compact and editorial, with the narrative serif token ready for later reading surfaces;
5. glow/glass effects are subordinate or absent in private chrome;
6. active navigation and focus states remain obvious without color alone;
7. no fake domain data is present;
8. no permanent feature inspector or AI control region is added to the shell;
9. reduced-motion behavior is defined for every introduced motion path;
10. rendered desktop and narrow evidence is reviewed separately from functional CI.

## Approval Gate

This document is the approved Phase-1D design specification.

Owner approval was given on 2026-09-11. Production shell/Home/Library/Projects implementation may proceed from this specification. Any material change to the shell/navigation/composition direction should be recorded here before implementation diverges from the approved fidelity target.
