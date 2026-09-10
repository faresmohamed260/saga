# S.A.G.A. v2 Phase 1 — Closed Demo Web Product

**Status:** ACTIVE  
**Tracking:** #150  
**Base:** `261b75ff2a60dfcada681af6b6c918c1ff5e3366`

## Goal

Turn the Phase-0 scaffold into the first real S.A.G.A. application: a polished web workspace with explicit public/private routing, invite-only accounts, admin-managed email invitations, and stable application ownership boundaries ready for later source/project/canon features.

S.A.G.A. is a **closed demo**. It is not a public-registration SaaS product.

## Owner Direction

- accounts are required for private application access;
- admission is invitation-only;
- invitations are initiated by an authorized S.A.G.A. admin and sent by email;
- there is no public self-service sign-up;
- RenderLab is a separate project and is read-only reference material for engineering/setup/UI governance only;
- do not copy RenderLab brand, routes, product components, schema names, resources, credentials, or deployment state.

## Verified Starting State

Phase 0 merged through PR #149 at:

`261b75ff2a60dfcada681af6b6c918c1ff5e3366`

Verified foundation:

- Next.js 16 / React 19 / TypeScript web app under `apps/web/`;
- v2-specific Web CI;
- Supabase SSR configuration boundary;
- provider-neutral object-storage boundary;
- validated private Backblaze B2 bucket and safe storage metadata;
- bootstrap-only B2 master credentials isolated from the web runtime;
- post-merge v2 Web CI, Backend Architecture CI, and compatibility workflow passed.

## RenderLab Reference Rules

Read-only reference sources may include:

- `renderlab/AGENTS.md`;
- `docs/architecture/FRONTEND_ARCHITECTURE.md`;
- `docs/architecture/INFRASTRUCTURE.md` when infrastructure behavior is relevant;
- `docs/ui/DESIGN_WORKFLOW.md`;
- `docs/ui/UI_SYSTEM.md`;
- `docs/ui/VISUAL_NORTH_STAR.md`;
- relevant component/screen decision docs.

Adopt principles, not implementation state. Useful reference principles include:

- repository-first durable continuity;
- Server Components by default and deliberately small Client Components;
- identity/session authority separated from product admission;
- fresh server verification for private/privileged access;
- service-role/admin capability never entering browser code;
- maintained UI primitives before custom generic controls;
- semantic design tokens and progressive disclosure;
- rendered responsive verification separate from build success;
- design-before-code only when a surface is deliberately being redesigned.

## Access Model

### Identity

Supabase Auth is the identity/session authority.

### Product admission

S.A.G.A. owns a separate account-access record. A valid Auth identity alone does not grant private application access.

Initial states:

- role: `member | admin`;
- status: `active | suspended`.

Only `active` admitted accounts enter private application routes.

Unknown, pending/unclaimed, suspended, anonymous, revoked, or unverifiable identities fail closed.

### Invitations

S.A.G.A. owns invitation records independently from Supabase's email-delivery mechanics.

An invitation has at least:

- opaque ID;
- normalized email;
- intended role;
- inviter identity;
- expiry;
- created time;
- claimed time or null;
- revoked time or null.

Rules:

- at most one currently open invitation per normalized email;
- expired open invitations may be revoked/replaced;
- invitation claim must bind the authenticated email/identity to the recorded invitation before access is granted;
- an invitation can be revoked before claim;
- invitation delivery responses must be generic enough to avoid account/email enumeration.

## Email Delivery Contract

Admin invitation creation is server-only. The server may use Supabase Auth Admin invitation capability once a S.A.G.A.-owned Supabase project is configured.

The database invitation record is the durable product truth. Email-provider acceptance is delivery attempt/evidence, not proof the recipient received the message.

Production use requires:

- correct Supabase Site URL and redirect allowlist;
- invite/confirmation/recovery templates appropriate for S.A.G.A.;
- production-capable custom SMTP or equivalent Supabase email hook/provider;
- sender-domain authentication and acceptable delivery/rate limits;
- operational verification before claiming email delivery is production-ready.

Do not commit SMTP/service-role secrets.

## Public vs Private Routing

Target ownership:

```text
/                     public S.A.G.A. landing
/login                public sign-in only; no sign-up
/auth/confirm          public auth/invitation completion boundary

/app                  private application shell / dashboard
/app/library          private sources/library
/app/projects         private story workspaces
/app/activity         private jobs/activity
/app/settings         private account/settings
/app/admin            private admin surface; fresh active-admin authorization
```

Later story/canon/character/world/timeline routes live under `/app/**` unless a future accepted information-architecture decision changes this.

## Frontend/UI Scope

Phase 1 establishes:

- S.A.G.A.-owned design tokens and maintained primitive layer;
- public landing/access CTA appropriate for a closed demo;
- sign-in and invitation-completion states;
- private application shell with desktop and narrow/mobile navigation;
- first dashboard/workspace composition around S.A.G.A. product concepts;
- account/settings surface;
- bounded admin invitation/account surface.

The product UI is organized around sources, projects, canon, characters, world, timeline, media, and activity—not internal AI pipeline stages.

## Backend Scope

Phase 1 establishes:

- browser/server Supabase clients and cookie refresh/session boundary;
- fresh server identity verification for private access;
- S.A.G.A. account-access resolution;
- S.A.G.A. invitation persistence/claim/revocation services;
- admin-only invitation/account endpoints;
- no service-role capability in browser bundles;
- first v2 migration/schema ownership path.

## Explicitly Out of Scope

- agent/LLM orchestration;
- source parsing/book analysis;
- identity/coreference runtime;
- final canon/event/world schema;
- generation planning/model execution;
- public registration;
- billing/subscriptions;
- copying RenderLab implementation or design identity;
- production deployment/email activation without separate operational validation.

## Security Invariants

1. Browser code never receives Supabase service-role/admin credentials.
2. Product authorization derives from fresh server-verified identity, not browser-supplied user IDs or `user_metadata` roles.
3. Private queries are owner/account scoped.
4. Admin routes verify current identity and active admin access on the server.
5. Public sign-up is absent and server admission fails closed for identities without S.A.G.A. access.
6. Invitation responses do not become an email/account enumeration oracle.
7. Raw access/invitation tables are server-owned with RLS enabled and browser grants revoked.
8. Authentication success and S.A.G.A. admission success are separate decisions.

## UI/UX Invariants

1. Simple by default, powerful when needed.
2. The story/workspace is visually dominant; chrome stays restrained.
3. Use maintained accessible primitives for conventional controls.
4. Reuse semantic tokens; avoid arbitrary one-off visual values when a token exists.
5. Prefer spacing/alignment/surface hierarchy over nested card stacks.
6. Motion explains hierarchy/continuity; reduced-motion behavior is mandatory.
7. Desktop and narrow/mobile behavior are designed together.
8. Build success is not visual approval: affected screens need rendered responsive review.
9. RenderLab references can guide process/quality, never S.A.G.A. visual identity.

## Validation

Minimum deterministic web gate:

```text
cd apps/web
npm install --no-audit --no-fund
npm run lint
npm run typecheck
npm run test:unit
npm run build
```

Phase-specific tests must also prove:

- no public signup surface/operation;
- service-role/admin credentials are server-only;
- private route authorization is fail-closed;
- invitation email normalization and duplicate-open-invite behavior;
- admin-only invitation mutation boundary;
- RenderLab is never imported as a runtime dependency.

Rendered verification must cover at least desktop and narrow/mobile views for public landing/access, private shell, and admin invitation states once those surfaces exist.

## External Dependencies

Phase 1 may implement all contracts before external provisioning, but live end-to-end completion requires:

- a S.A.G.A.-owned Supabase project selected/created by the owner;
- repository/Vercel Supabase public + server credentials;
- hosted Auth redirect configuration;
- production-capable email delivery configuration;
- bucket-scoped B2 runtime credentials before real source upload is enabled.

Missing external configuration must fail honestly; do not fabricate successful live integration.

## Exit Criteria

Phase 1 closes when:

1. repository handoff points to this phase and records the closed-demo decision;
2. S.A.G.A.-specific UI/design governance is committed;
3. public landing and private application shell boundaries exist;
4. public self-signup does not exist;
5. account-access + invitation schema/services exist under v2 ownership;
6. private access requires fresh verified identity + active admission;
7. admin invitation creation/revocation is server-only and anti-enumeration-safe;
8. invitation email delivery path exists and its operational SMTP/template dependency is documented honestly;
9. exact-head Web CI passes;
10. rendered desktop/narrow review passes for affected product surfaces;
11. no RenderLab file/resource was modified;
12. `PROJECT.md` records the merged Phase-1 baseline and next phase from verified reality.
