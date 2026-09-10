# S.A.G.A. v2 UI System

## Purpose

Define a durable S.A.G.A.-owned product UI system for the web rebuild.

RenderLab's mature UI documentation is a **read-only process/quality reference**. This document does not import RenderLab's visual identity, product layout, routes, or component implementation.

## Product Character

S.A.G.A. is a narrative-intelligence workspace. The interface should feel calm, precise, cinematic when appropriate, and information-rich without reading like an admin dashboard or internal AI control panel.

Core rule: **story first, machinery second**.

- source text, story structure, canon evidence, characters, places, events, relationships, and generated media are the primary content;
- AI/provider/model details are secondary operational information and should appear only where the user needs them;
- internal pipeline stage numbers must not drive top-level navigation;
- complexity is progressively disclosed.

## Quality Principles

- simple by default, powerful when needed;
- strong hierarchy and typography before decoration;
- semantic tokens before one-off values;
- maintained accessible primitives before custom generic controls;
- deliberate motion only when it communicates continuity, hierarchy, or state;
- no decorative effect should compete with narrative content;
- desktop and mobile/narrow are designed as one product, not separate products;
- keyboard, focus, screen-reader semantics, touch reachability, and reduced motion are non-negotiable.

## Surface Expressiveness

Different S.A.G.A. surfaces have different visual ceilings.

| Surface | Level | Direction |
|---|---:|---|
| Public landing | 3 / 4 | Distinctive narrative atmosphere and polished motion are welcome when purposeful. |
| Application shell | 2 / 4 | Quiet navigation continuity; feature content dominates. |
| Library / Projects | 2 / 4 | Dense, readable workspace with strong object hierarchy. |
| Story / Canon exploration | 3 / 4 | Spatial relationships, evidence continuity, timeline/graph interactions may be expressive. |
| Media | 3 / 4 | Cinematic inspection and continuity where appropriate. |
| Activity / Jobs | 2 / 4 | State-driven motion only. |
| Settings | 1 / 4 | Calm trust/security surface. |
| Admin | 1 / 4 | Operational clarity first. |

These are design ambition ceilings, not animation quotas.

## Semantic Visual Foundation

Phase 1 keeps the dark-first foundation established in Phase 0 but replaces scattered literals progressively with semantic tokens.

Initial semantic roles:

- `canvas` — application background;
- `surface-1` — primary navigation/panel surface;
- `surface-2` — raised control/detail surface;
- `surface-3` — hover/selected/elevated surface;
- `border` — default separation;
- `text` — primary text;
- `text-muted` — secondary/supporting text;
- `accent` — primary action/focus/selection;
- `success`, `warning`, `danger` — state semantics only.

Accent is not a large-surface fill by default. Status colors must communicate real state, never fabricate progress or availability.

## Typography

Prefer a compact functional sans-serif for application chrome and a restrained editorial accent only if a later approved design establishes one for narrative content.

Initial application scale:

- page title: 28–32px / semibold;
- section heading: 18–22px / semibold;
- body: 15–16px / regular;
- UI label: 13–14px / medium/semibold;
- metadata/caption: 12–13px / regular.

Do not inflate headings merely to make sparse screens appear designed. Story content may use its own reading typography later behind a dedicated contract.

## Spacing and Shape

Use a 4px spacing base with a practical sequence such as:

`4, 8, 12, 16, 20, 24, 32, 40, 48, 64`

Preferred radius roles:

- compact controls: 6–8px;
- standard controls/surfaces: 8–12px;
- larger panels/media frames: 12–18px.

Avoid universal pills and excessive rounded-card nesting.

## Surface Hierarchy

Prefer:

1. whitespace and alignment;
2. typography and grouping;
3. tonal surfaces/borders;
4. elevation only for floating/temporary layers.

Avoid card-within-card-within-card layouts. Tables, rails, canvases, lists, split panes, timelines, graphs, and open workspaces are often more appropriate to S.A.G.A. than generic dashboard cards.

## Application Shell

The persistent shell owns:

- product navigation;
- current workspace/project context where useful;
- account access;
- bounded Activity attention state;
- route-content region.

It does not own feature-specific editors, source controls, canon filters, character tools, timeline controls, generation parameters, or media inspectors.

### Desktop

- compact persistent side navigation;
- largest area reserved for current story/workspace content;
- primary destinations near the top;
- utility/account/admin destinations visually secondary;
- avoid duplicate top-level chrome when the side rail already supplies context.

### Narrow/mobile

- do not compress the desktop sidebar into a tiny strip;
- use a touch-friendly compact navigation treatment;
- keep current task and primary action reachable;
- move secondary feature controls into sheets/disclosures where needed;
- no hover-only essential actions.

## Maintained Primitive Policy

Conventional visible controls must use a shared maintained primitive layer under `apps/web/src/components/ui/` once introduced.

Preferred source order:

1. existing S.A.G.A. primitive/component;
2. shadcn/ui + Radix-compatible maintained primitive;
3. Motion for React / maintained motion primitive when interaction needs it;
4. approved external component adapted to S.A.G.A. semantics/tokens;
5. custom generic mechanic only when a maintained option is unsuitable and the reason is documented.

Feature code should not repeatedly hand-style raw buttons, inputs, selects, textareas, dialogs, menus, tabs, tooltips, or sheets when a normalized primitive exists.

Native file/hidden inputs may remain platform plumbing.

## Component Ownership

Target structure:

```text
apps/web/src/
  app/                   # routes/layouts/transport
  components/
    ui/                  # generic maintained primitives
    shell/               # persistent application chrome
  features/              # product-specific composition
  lib/                   # framework-neutral helpers/contracts
  server/                # privileged/vendor/data boundaries
```

Generic primitives never absorb S.A.G.A. domain data contracts. Feature components compose primitives rather than turning shared UI into a global feature store.

## Motion

Motion should communicate continuity and state.

Useful candidates:

- shell navigation selection/route continuity;
- source/project object → detail continuity;
- character/location/event relationship exploration;
- timeline focus/selection changes;
- contextual disclosure from its trigger;
- media inspection/continuation;
- drag/drop/reorder where later product workflows need it.

Avoid perpetual decorative motion, generic staggered fades everywhere, or glow-only attempts at visual quality.

Every animated interaction needs a clear reduced-motion equivalent.

## Responsive Rules

- wide desktop: allow workspace + relevant supporting context without waste;
- standard desktop/tablet landscape: compress secondary chrome first;
- narrow/tablet portrait/mobile: move secondary tools into disclosures/sheets while preserving the current task;
- never require hover for essential behavior;
- no horizontal overflow for primary content.

## Accessibility Baseline

- visible keyboard focus;
- semantic labels/names for interactive controls;
- logical tab order;
- sufficient contrast;
- touch targets approximately 44×44px where practical;
- status conveyed by more than color alone;
- reduced-motion support;
- dialogs/menus/sheets use maintained accessible mechanics;
- dynamic job/state updates should be announced appropriately when later implemented.

## Closed-Demo Access UI

Because S.A.G.A. is invitation-only:

- public landing may offer `Sign in` or an equivalent access CTA, not `Create account`;
- login copy must not imply open registration;
- unknown/unadmitted signed-in users receive a clear closed-demo access state rather than a broken dashboard;
- admin invite screens should be restrained operational UI, not a marketing surface;
- invitation success language should say the invite was recorded/sent or delivery was attempted only to the degree actually known by the backend.

## RenderLab Reference Boundary

Allowed use:

- learn governance/process patterns;
- compare architecture/interaction decisions;
- use similar maintained library ecosystems;
- learn from proven auth/admin/security separation and validation discipline.

Forbidden use:

- copying RenderLab brand tokens or screen composition as S.A.G.A. defaults;
- sharing its routes/schema names/storage resources/credentials;
- importing RenderLab source packages;
- modifying RenderLab to make S.A.G.A. easier.

S.A.G.A. must remain visually and architecturally its own product.
