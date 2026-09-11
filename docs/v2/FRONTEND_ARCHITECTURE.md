# S.A.G.A. v2 Frontend Architecture

## Purpose

This document defines the Phase-1 frontend/server ownership model for the active `apps/web` product.

It borrows proven architectural *principles* from the read-only RenderLab repository—Server Components by default, narrow client islands, maintained primitives, explicit server boundaries, fresh auth checks, remote validation—but the routes, data model, code, product concepts and visual composition here are S.A.G.A.-owned.

## Framework

- Next.js App Router
- React 19
- TypeScript
- Tailwind CSS
- Server Components by default
- Client Components only for browser interaction that truly requires local state
- Supabase SSR/Auth/Postgres/Realtime at infrastructure/data boundaries
- provider-neutral object storage under `src/server/storage`
- Motion for deliberate interaction continuity where approved

## Top-Level Runtime Shape

```text
browser
  -> Next.js route/layout
       -> server route composition
       -> current-session verification
       -> S.A.G.A. account/access resolver
       -> domain/repository services
            -> Supabase Postgres/Auth
            -> ObjectStorage -> Backblaze B2
            -> future durable job boundary
```

The browser does not call Supabase service-role APIs, Auth Admin APIs, B2 master credentials or future model workers directly.

## Proposed Source Ownership

```text
apps/web/src/
  app/
    (public)/
      page.tsx                 # landing
      sign-in/
    (auth)/
      auth/confirm/
      set-password/
    (app)/
      layout.tsx               # private AppShell boundary
      home/
      library/
      projects/
      activity/
      settings/
      admin/
    api/
      admin/
      account/
      ...future product APIs

  components/
    ui/                        # maintained normalized primitives
    shell/                     # persistent app chrome only

  features/
    account/
    admin/
    home/
    library/
    projects/
    characters/
    world/
    timeline/
    canon/
    story/
    media/
    activity/

  lib/
    api/                       # typed browser-facing product contracts
    auth/                      # shared redirect/type helpers only
    supabase/
      config.ts
      browser.ts
      server.ts
      proxy.ts

  server/
    account/                   # identity/access/invite claim services
    admin/                     # active-admin services
    data/                      # repositories/SQL boundaries
    projects/                  # later project domain services
    library/                   # later source/library services
    jobs/                      # later durable job control
    storage/                   # ObjectStorage + B2 provider implementation
```

This structure is directional. Do not create empty directories/modules solely to match the diagram. Add ownership boundaries when the first real feature needs them.

## Route Groups / Public Boundary

Use route groups to separate layouts without forcing implementation names into URLs.

Initial direction:

```text
/                         public landing
/sign-in                  public sign-in
/auth/confirm             server invite/recovery confirmation
/set-password             confirmed/session-bound credential setup

/home                     private app home
/library                  private source/library workspace
/projects                 private projects
/projects/[projectId]     private project workspace
/activity                 private activity
/settings                 private account/settings
/admin                    active-admin only
```

Future project subroutes may include `characters`, `world`, `timeline`, `canon`, `story`, and `media` after the first project workflow proves what deserves a route.

Rules:

- route groups may split public/auth/app layouts;
- public routes do not mount the private AppShell;
- private routes resolve S.A.G.A. account access server-side before private domain reads;
- `/admin` always performs fresh active-admin authorization;
- `next`/redirect parameters are untrusted and must resolve only to allowed same-origin relative application paths;
- no provider/model/pipeline stages become top-level routes by default.

## Server Components by Default

Prefer Server Components for:

- private layout/account resolution;
- Home summary composition;
- Library/source lists;
- Project lists/workspace metadata;
- entity/canon/timeline reads;
- Settings current-account state;
- Admin account/invitation datasets;
- future Activity/job history.

Benefits expected:

- no duplicate global client data store;
- authorization happens before private data rendering;
- smaller client bundles;
- URL/server state remains authoritative for shareable browsing/filtering;
- feature code does not need to reconstruct server truth after hydration.

## Client Components Deliberately

Use Client Components for bounded interaction such as:

- sign-in/password form pending/error state;
- mobile shell disclosure/navigation;
- invitation/account admin mutation forms;
- search/filter controls that require client interaction while URL/server state remains authoritative;
- drag/drop/upload interaction later;
- entity canvas/timeline direct manipulation later;
- dialogs/sheets/popovers/menus;
- intentional motion/gesture behavior.

A Client Component should not become the durable source of truth for accounts, projects, library assets, canon or jobs merely because it makes UI state easier.

## Supabase Boundaries

### Browser client

May use the public/publishable Supabase client for supported user-session operations such as:

- sign in;
- sign out;
- password update/recovery completion when the verified session allows it;
- Realtime subscriptions later when a product workflow requires them.

It never receives service-role/Auth Admin credentials.

### Server client

Owns:

- SSR/session-aware Auth reads;
- current verified identity lookup;
- ordinary user-scoped database operations where RLS makes sense.

### Privileged server client

A service-role/Auth Admin capability may exist only in server-only modules that need it for:

- invitation sending/admin operations;
- S.A.G.A. access-row mutation/claim;
- trusted internal data operations not safely expressible with user RLS.

Do not re-export a privileged client through general-purpose modules imported by browser/features.

## Auth / Product Authorization Split

Supabase Auth proves identity. S.A.G.A. account records decide product access.

Private request flow:

```text
request
  -> cookie/session maintenance
  -> fresh `auth.getUser()`-equivalent server verification
  -> verified non-anonymous auth user
  -> S.A.G.A. account access lookup
  -> active role/status
  -> private domain operation
```

Root/proxy JWT parsing/cookie refresh is not the final authorization decision when immediate revocation matters.

Admin flow repeats fresh identity verification and then requires `role=admin` + `status=active` from S.A.G.A.-owned state.

See `ACCESS_AND_INVITATIONS.md`.

## Application Shell Boundary

The persistent shell owns:

- product/global navigation;
- current high-level route/project context where useful;
- account menu/access;
- lightweight Activity attention state later;
- responsive desktop/mobile navigation container;
- route-content frame.

The shell does **not** own:

- source upload forms;
- project-specific entity/canon/timeline controls;
- story editor/planner tools;
- media controls;
- feature-specific inspectors/filters;
- admin account operations.

Keep shell chrome restrained so narrative/project content has the largest useful area.

## Product Information Architecture

The UI is organized by user concepts:

- Home
- Library / Sources
- Projects / Stories
- Characters / Relationships
- World / Locations
- Timeline / Events
- Canon / Evidence
- Story / Planning
- Media
- Activity
- Settings
- Admin

Do not expose old v1 stage numbers or future agent names as the main navigation model.

## State Ownership

### URL state

Use for shareable/discoverable state such as:

- selected project/route;
- Library query/filter/sort/page when those features ship;
- selected canon/entity/timeline view where a stable URL helps.

### Server/database state

Owns:

- account/access/invitations;
- projects/sources/entities/canon/events;
- durable media/object references;
- future job/run lifecycle;
- admin policy/config that affects product truth.

### Client-local state

Owns only transient interaction such as:

- open/closed dialog/sheet/popover;
- local form pending/error/success;
- drag hover/reorder preview;
- selected rows for a current-page operation;
- temporary editor affordances before explicit persistence.

Do not promote local convenience state into a global store without a second real product need.

## API Boundary

Use product-level APIs when browser mutations or non-Server-Action boundaries are appropriate.

Initial expected endpoints:

```text
POST   /api/admin/invitations
GET    /api/admin/invitations
DELETE /api/admin/invitations/[invitationId]
GET    /api/admin/accounts
PATCH  /api/admin/accounts/[userId]
```

Additional account/auth operations should prefer Supabase's supported Auth client/server APIs unless S.A.G.A. genuinely needs a product-specific mutation.

Future project/library/media/job APIs are added when those slices ship; do not prebuild a large generic API layer.

## Error / Enumeration Rules

- Foreign/missing private object IDs collapse to ordinary not-found where practical.
- Sign-in/reset flows should not reveal whether arbitrary email addresses are registered beyond what the chosen Auth provider necessarily exposes.
- Admin invitation/account endpoints may return specific operational errors because they are already behind active-admin authorization.
- Browser-visible errors are product-level; raw Supabase/Postgres/provider messages stay server-side/logged safely.

## Storage Boundary

Feature code depends on `ObjectStorage`, not `S3Client`.

Browser direct upload/download later must use short-lived server-issued tickets/URLs scoped to application-generated object keys. Durable application identity is a relational record ID, not a raw B2 key or signed URL.

The B2 master bootstrap key never enters the web runtime.

## Maintained UI Primitive Boundary

Conventional controls should be normalized under `src/components/ui` as they are needed. Feature/shell code should compose those primitives instead of creating visually competing raw controls.

Candidate foundation primitives:

- Button / IconButton
- Input / Textarea
- Label / Field
- Select
- Dropdown Menu
- Dialog / Alert Dialog
- Sheet / Drawer
- Tabs / Toggle Group
- Tooltip
- Checkbox / Switch
- Separator
- Skeleton / Spinner / Alert / Toast
- Empty-state composition

Do not install the full catalog preemptively. Add a primitive when a real Phase-1 surface needs it, normalize it to S.A.G.A. tokens, test it, then reuse it.

## Responsive Direction

Desktop productivity is primary because S.A.G.A. eventually includes dense narrative/timeline/entity workspaces.

- desktop: compact persistent navigation may coexist with broad workspaces;
- medium/narrow: collapse secondary feature chrome before shrinking core content into unusable panels;
- mobile: use touch-friendly navigation/sheets and preserve primary reading/account/project tasks;
- no hover-only essential actions;
- minimum effective touch targets should approach 44×44 px where practical;
- no horizontal overflow on ordinary product routes.

Exact shell geometry belongs to the approved Phase-1 visual concept rather than this architecture file.

## Accessibility / Motion

Target WCAG 2.2 AA behavior for normal product UI.

Required:

- keyboard-operable controls;
- visible focus;
- semantic maintained dialog/menu/form behavior;
- accessible names for icon-only actions;
- status not conveyed by color alone;
- appropriate focus trap/restore for modals;
- touch reachability;
- `prefers-reduced-motion` support.

Motion communicates continuity, hierarchy and direct manipulation. It must never fabricate analysis progress, job state, confidence, authorization or completion.

## Validation Direction

Phase-1 frontend changes require:

- lint;
- typecheck;
- unit/structural tests;
- production build;
- secret/client-boundary tests;
- auth/access tests for private/admin behavior;
- responsive rendered review for major surfaces;
- keyboard/focus/touch review where affected;
- reduced-motion verification where motion is introduced;
- exact-head GitHub CI before merge.

Functional CI and visual-fidelity review are separate gates.

## RenderLab Reference Disclaimer

This document was informed by proven engineering patterns visible in RenderLab's documentation, especially its frontend architecture and account/admin boundaries. It is not a copy of RenderLab's product contract. Where the products differ, S.A.G.A.'s narrative-domain needs and this repository's decisions win.