# S.A.G.A. v2 Phase 1 — Closed-Demo Main Site, Accounts & Invitations

**Status:** ACTIVE — CONTRACT/ARCHITECTURE PASS

**Tracking:** #151

## Goal

Turn the Phase-0 web foundation into the first real S.A.G.A. v2 application: a closed invite-only demo with account/session boundaries, email invitations, admin access management, and a production-quality narrative workspace shell.

Phase 1 establishes the product/app/auth/UI contracts that the future AI system will operate behind.

## User Value

An invited demo user should be able to:

1. receive a S.A.G.A. invitation email;
2. confirm the invitation through the supported Auth flow;
3. establish credentials;
4. sign in later;
5. reach the private S.A.G.A. workspace;
6. browse the first application information architecture without seeing internal provider/pipeline complexity.

An active S.A.G.A. admin should be able to:

- invite a person by email;
- revoke a still-pending invitation;
- inspect S.A.G.A.-owned account state;
- suspend/reactivate an account;
- promote/demote roles without relying on browser metadata.

## Verified Starting State

Merged Phase-0 baseline:

- repository: `faresmohamed260/saga`
- `main`: `261b75ff2a60dfcada681af6b6c918c1ff5e3366`
- tree: `50f34409fb52540ce48c506f9446a3b75e608b08`
- PR: #149
- Phase-0 issue: #148 closed complete

Verified foundation:

- Next.js/React/TypeScript app under `apps/web/`;
- Supabase SSR configuration boundary;
- provider-neutral object storage + B2 S3 adapter;
- dedicated private B2 bucket validated through GitHub Actions;
- v2 web CI for install/lint/typecheck/tests/build;
- v1 runtime classified historical/reference.

External state:

- connected Supabase account exposes organization `Fares Home Lab`;
- there is no S.A.G.A.-owned Supabase project configured yet;
- creating one requires explicit organization selection/cost confirmation;
- B2 master/bootstrap credentials exist, but no scoped runtime B2 application key is configured yet;
- hosted invitation-email SMTP/template configuration is not yet verified.

## Owner Constraint — Closed Demo

S.A.G.A. v2 is not open signup.

- Public self-signup is disabled.
- Account creation/admission begins with an admin invitation email.
- Supabase Auth remains identity/session authority.
- S.A.G.A. owns product access/role/status/invitation state.
- A public brand/landing page may remain available.
- Private product routes require a fresh verified identity plus active S.A.G.A. account access.

## RenderLab Reference Boundary

RenderLab is read-only reference material for process/setup/UI patterns only.

Useful reference principles inspected for this phase include:

- repository-first continuity;
- execution-ready phase contracts merged before implementation;
- Server Components by default and small client interaction islands;
- maintained accessible primitive layer;
- responsive/accessibility/reduced-motion requirements;
- explicit account identity vs product access separation;
- normalized-email invitation records above Supabase Auth;
- fresh server-side Auth checks for privileged/private authorization;
- admin-only account/invitation services;
- clear distinction between application code and hosted email/SMTP operational readiness;
- rendered UI validation separate from build success.

Do not copy RenderLab code, table names, routes, branding, visual composition, data, credentials or resources. Do not modify its repository during S.A.G.A. work.

S.A.G.A.'s own contracts are:

- `docs/v2/FRONTEND_ARCHITECTURE.md`
- `docs/v2/UI_SYSTEM.md`
- `docs/v2/ACCESS_AND_INVITATIONS.md`

## In Scope

### 1. Account / invitation persistence

Add S.A.G.A.-owned relational records for:

- account access keyed by verified Supabase Auth user ID;
- account role (`member|admin` initially);
- account status (`active|suspended` initially);
- pending/accepted/revoked/expired invitation lifecycle keyed by normalized email;
- inviter/claim/audit timestamps needed for deterministic authorization and operations.

RLS must be enabled; browser access to privileged access/invitation state is not the default. Server-only service paths own privileged mutation/read access.

### 2. Auth/session boundary

Implement:

- public sign-in surface;
- server invite confirmation route;
- password setup/change flow for confirmed invited users;
- sign-out;
- SSR cookie refresh/session plumbing;
- fresh current-user verification for private product/account/admin authorization;
- server S.A.G.A. account resolver that fails closed for unknown/suspended identities;
- safe same-origin redirect validation.

No public create-account action.

### 3. Invitation workflow

Implement narrow server/admin operations for:

- create invitation by normalized email + intended role;
- trigger supported Supabase invitation email server-side;
- revoke pending invitation;
- claim an eligible pending invitation only after verified Auth identity/email is established;
- reject mismatched, expired, revoked, consumed or ineligible invitation state;
- avoid storing reusable raw Auth invitation tokens.

### 4. Admin account management

Implement private admin UI/API for:

- pending invitations;
- S.A.G.A.-known accounts only;
- role/status mutation;
- self-lockout/last-admin protection when applicable;
- sanitized operational feedback.

Do not expose the whole shared `auth.users` directory as product data.

### 5. Main application shell / information architecture

Implement the first real shell around S.A.G.A. user concepts.

Target product areas:

- Home
- Library
- Projects
- Characters
- World
- Timeline
- Canon
- Story
- Media
- Activity
- Settings
- Admin (authorized only)

Phase 1 need not fully implement every domain surface. It must establish the shell, routing model, responsive navigation, page composition rules and initial Home/Library/Projects footholds without presenting fake analysis results.

### 6. UI foundation

Create S.A.G.A.-owned:

- semantic visual tokens;
- maintained primitive layer as real controls are needed;
- application shell primitives;
- auth/admin/account primitives;
- responsive rules;
- keyboard/focus/touch/reduced-motion behavior;
- UI structural/purity tests where practical.

Major new product surfaces require complete visual concepts and rendered review before being called approved.

### 7. CI / validation

Expand v2 CI so Phase 1 can prove:

- lint/typecheck/unit/build;
- no service-role/Auth Admin/master object-store secret enters client paths;
- no public signup affordance/path is introduced;
- private/admin authorization contracts are structurally covered;
- migration/schema safety checks when the v2 Supabase migration path is added;
- responsive/rendered UI checks for implemented shell/auth/admin surfaces.

## Explicitly Out of Scope

- agentic AI/LLM orchestration;
- identity/coreference/canon extraction runtime;
- generation planning/narrative generation;
- live visual/audio model execution;
- a public signup/request-access product;
- social login unless separately approved;
- billing/subscriptions;
- organization/team multi-tenancy;
- copying/modifying RenderLab;
- production deployment without separate owner authorization;
- claiming email deliverability before hosted configuration is verified.

## Target Route Boundary

Initial direction; route groups may separate public/auth/app layouts without leaking those group names into URLs.

```text
/                         public landing/brand
/sign-in                  public sign-in
/auth/confirm             server invitation/recovery confirmation
/set-password             confirmed/session-bound credential setup

/home                     private application home
/library                  private source/library workspace
/projects                 private project list
/projects/[projectId]     private project workspace
/projects/[projectId]/characters
/projects/[projectId]/world
/projects/[projectId]/timeline
/projects/[projectId]/canon
/projects/[projectId]/story
/projects/[projectId]/media
/activity                 private activity/jobs later
/settings                 account/settings
/admin                    active-admin only
```

Routes beyond the first implementation slices are information-architecture direction, not a promise that every route ships in the first PR.

## Target Account / Invitation State

### Account access

```text
user_id        uuid, verified Supabase Auth identity, primary key
role           member | admin
status         active | suspended
invited_by     nullable admin auth user id
accepted_at    timestamptz
created_at     timestamptz
updated_at     timestamptz
```

### Invitation

```text
id               uuid primary key
email_normalized text/citext, normalized server-side
email_display    text
intended_role    member | admin
status           pending | accepted | revoked | expired
invited_by       admin auth user id
invited_at       timestamptz
expires_at       timestamptz aligned with hosted Auth policy
accepted_by      nullable auth user id
accepted_at      nullable timestamptz
revoked_at       nullable timestamptz
```

Raw reusable Auth tokens/secrets are not application columns.

The concrete SQL may refine field names/constraints as implementation evidence requires, while preserving the security semantics above.

## Authorization Model

```text
request/session
  -> SSR Auth cookie maintenance
  -> fresh server Supabase Auth identity verification
  -> S.A.G.A. account-access lookup
  -> role/status decision
  -> owner/admin-scoped domain service
```

Rules:

- anonymous -> sign-in boundary;
- verified identity with no S.A.G.A. account -> access denied / invitation-completion state, not auto-admitted;
- suspended account -> private product denied but bounded security/account recovery/sign-out may remain available;
- active member -> private product;
- active admin -> private product + admin operations;
- role is never read from browser/user metadata for authorization.

## Invitation Flow

```text
active admin
  -> POST invitation(email, role)
  -> normalize + validate email
  -> persist pending S.A.G.A. invitation
  -> request Supabase Auth invite email server-side
  -> recipient opens supported token-hash/confirmation link
  -> server verifies Auth invitation
  -> fresh verified identity/email
  -> transactional claim of matching eligible S.A.G.A. invitation
  -> active S.A.G.A. account established
  -> credential setup / private app
```

If outbound email fails, the product must surface a bounded invitation-delivery failure and preserve enough product state to retry/revoke safely without leaking token material.

## Email Operational Gate

Before the invite flow can be called end-to-end validated in a hosted demo, verify:

- S.A.G.A. Supabase project Site URL;
- allowlisted same-origin callback/redirect URLs;
- invite and recovery email templates using supported confirmation/token-hash variables;
- custom SMTP or equivalent Auth email hook;
- sender domain authentication;
- acceptable rate limits;
- actual inbox delivery for at least one bounded test invitation.

Application CI is not required to send real external email.

## UI/UX Contract

Primary product principle: **Narrative first, complexity on demand.**

The application should feel like a focused narrative intelligence workspace rather than a generic admin dashboard or an AI-provider console.

Core rules:

- maintained accessible controls before custom mechanics;
- story/source/evidence/entity/timeline content dominates chrome;
- progressive disclosure for advanced controls;
- no default card-grid solution for every page;
- prefer rails, lists, split workspaces, canvases, editors, relationship/timeline views and focused detail panels where they fit the user task;
- desktop productivity is primary, but mobile/narrow access remains coherent and touch-friendly;
- WCAG-oriented keyboard/focus semantics;
- no hover-only essential behavior;
- meaningful motion only, with reduced-motion/static equivalents;
- concept and rendered fidelity review are separate from functional CI.

See `docs/v2/UI_SYSTEM.md`.

## Phase Slices

### 1A — Contract / architecture / UI governance

Merge this execution contract and the three Phase-1 subsystem documents first.

### 1B — Account/invitation persistence + server authorization

Add v2 Supabase migrations/contracts, account/invitation services and deterministic tests without requiring outbound email delivery.

### 1C — Auth/invite/password surfaces

Implement sign-in, confirmation, password setup, session/account boundaries and protected layout behavior.

### 1D — Application shell / first product surfaces

Implement approved responsive shell and first Home/Library/Projects composition using S.A.G.A.-owned visual concepts.

### 1E — Admin invitation/account operations + hosted integration

Implement admin UI/APIs, configure/verify the new S.A.G.A. Supabase project/email path and prove a real bounded invite acceptance flow. Scoped B2 runtime credentials may also be established when source upload becomes part of the first product workflow.

Slices may be split into separate PRs; later slices do not silently change earlier contracts without updating the authoritative docs.

## Validation Matrix

| Claim | Required evidence |
|---|---|
| Phase contract current | docs/PROJECT/DECISIONS exact-head review |
| No public signup | structural/API/UI tests + rendered auth review |
| Private route denial | deterministic auth/access tests |
| Suspended/unknown denial | deterministic server account resolver tests |
| Admin-only invitation mutation | fresh-auth + active-admin tests |
| Invite claim matches verified email | transactional integration test |
| No raw invite token persistence | schema/structural test |
| No privileged secret in browser | bundle/source structural checks |
| UI shell responsive | desktop + narrow rendered evidence |
| Auth/admin accessible | keyboard/focus/touch review |
| Reduced motion | implemented motion paths audited |
| Hosted invitation delivery | explicit live inbox test after SMTP/templates configured |
| Merge safety | exact-head `SAGA v2 Web CI` + required repo checks |

## External Dependencies / Blockers

Not blockers for contract or most deterministic implementation:

- new S.A.G.A. Supabase project;
- custom SMTP/email hook;
- scoped B2 runtime application key.

They become blockers only for the hosted end-to-end slices that require them.

Supabase project creation through the connected tool requires the owner to explicitly choose an organization and confirm the reported cost before mutation. Do not assume this authorization from generic “keep going.”

## Exit Criteria

Phase 1 closes only when:

1. Phase-1 contracts are merged and authoritative;
2. S.A.G.A.-owned account/invitation schema is applied to the new S.A.G.A. Supabase project;
3. public self-signup is absent;
4. invite confirmation + credential setup + later sign-in work end-to-end;
5. private routes require fresh verified identity + active S.A.G.A. account;
6. suspended/unknown identities fail closed;
7. active admins can create/revoke invitations and manage bounded account role/status;
8. at least one real invitation email is delivered and accepted through the hosted configuration;
9. the private application shell and initial narrative information architecture are implemented and responsive;
10. no privileged credentials/tokens leak to browser, repository or logs;
11. exact-head v2 CI and relevant rendered/accessibility review pass;
12. `PROJECT.md` records the merged baseline and the next application/agent phase from verified reality.

## Next-Phase Direction

Do not fully design the agentic AI phase yet.

Once Phase 1 establishes real projects/sources/accounts/storage/jobs/UI ownership, plan the next immediate phase around the first durable story/source workflow and the job boundary the future agents will consume.