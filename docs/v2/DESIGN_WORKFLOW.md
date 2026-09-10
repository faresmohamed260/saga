# S.A.G.A. v2 Design Workflow

## Purpose

Keep UI quality high across long-running AI-assisted development without allowing each session to reinterpret the product.

The repository remains authoritative. Visual artifacts and external references support decisions; they do not override accepted product, security, route, data, or architecture contracts.

RenderLab's design-governance documents are read-only references for process quality. S.A.G.A. owns its own visual identity and implementation decisions.

## Two Work Modes

### Integration Mode — default

Use this for ordinary product work where the existing S.A.G.A. composition is not being explicitly redesigned.

Procedure:

1. read `PROJECT.md`, `AGENTS.md`, active phase, `docs/v2/UI_SYSTEM.md`, and relevant feature/architecture docs;
2. inspect the current rendered surface when presentation is affected;
3. preserve existing accepted information architecture and interaction behavior unless the task requires changing them;
4. use maintained primitives and semantic tokens;
5. implement the requested feature with the smallest appropriate client-state boundary;
6. run deterministic build/type/lint/tests;
7. verify affected screens at desktop and narrow/mobile sizes;
8. update repository documentation from verified implementation reality.

### Authorized Redesign Mode — explicit only

Enter this mode only when the owner explicitly asks to redesign, restyle, modernize, visually elevate, reimagine, or otherwise reopen a named S.A.G.A. surface/system.

Then:

1. audit current product behavior and rendered implementation;
2. state exactly which visual decisions are reopened and which product/security/data contracts remain fixed;
3. create a reference matrix for important interactions;
4. create a complete visual direction for the requested surface, including desktop and narrow/mobile states;
5. define interaction choreography independently from any specific animation library;
6. prototype signature temporal behavior when static frames cannot prove it;
7. obtain explicit human design approval;
8. record the accepted design/phase decision in the repository;
9. implement faithfully rather than reinterpreting the approved concept into a generic UI;
10. validate functionality and visual fidelity separately.

A technically green implementation can still fail design review.

## Reference Matrix

For meaningful redesign work, record:

- S.A.G.A. task/interaction;
- exact reference source;
- behavior/quality to learn from;
- what must not be copied;
- desktop/pointer behavior;
- narrow/touch behavior;
- keyboard/focus behavior;
- reduced-motion/static equivalent.

References may include RenderLab, other products, component libraries, interaction research, or generated design concepts. The output must still read as one S.A.G.A. system.

## Static vs Temporal Approval

Static screenshots/concepts can approve:

- layout;
- typography;
- spacing;
- palette;
- surface hierarchy;
- component geometry;
- responsive composition.

They cannot alone approve:

- morphing;
- physics/spring feel;
- drag/reorder behavior;
- pointer-responsive depth;
- scroll choreography;
- other time-dependent interaction quality.

Those require reviewable temporal evidence.

## Component Sourcing

Before creating a generic mechanic, search in this order:

1. existing S.A.G.A. component;
2. existing S.A.G.A. primitive;
3. shadcn/ui/Radix-compatible maintained primitive;
4. Motion for React / maintained motion component;
5. another production-appropriate maintained source after accessibility/license/performance review;
6. custom implementation only when justified.

Do not recreate a maintained component from memory just to avoid integrating it properly.

When a maintained component becomes part of the product, normalize it to S.A.G.A. tokens/semantics rather than allowing a competing component-library visual language to leak through.

## Design Tokens

Once a semantic token exists, use it instead of inventing another arbitrary value for the same role.

Token families should cover:

- color/surfaces/status;
- typography;
- spacing;
- radii;
- control heights;
- elevation;
- z-index;
- motion timing;
- breakpoints when project-specific evidence requires them.

## Validation Loop

Preferred remote-first loop:

`repository contract -> GitHub implementation -> GitHub Actions -> rendered screenshots/browser evidence -> review -> repository update`

For explicit redesign:

`current render -> references/concepts -> human approval -> repository contract -> implementation -> functional CI -> rendered fidelity review -> repository update`

A design-tool artifact is never more authoritative than the repository.

## Rendered Review

When a UI change affects presentation, inspect the actual rendered result rather than relying on code inspection/build success alone.

Minimum review dimensions:

- a representative desktop viewport;
- a narrow/mobile viewport around 390px when practical.

Check:

- visible copy and hierarchy;
- typography and spacing;
- shell/feature boundary;
- surface nesting;
- control semantics and focus;
- overflow/clipping;
- touch reachability;
- reduced-motion behavior when motion exists;
- visual state honesty (no fake progress/access/provider status).

## Closed-Demo Design Rules

Access UI must communicate the product truth:

- S.A.G.A. is invitation-only;
- there is no public registration promise;
- sign-in is for invited/authorized users;
- an invitation email action must not visually guarantee delivery beyond backend evidence;
- suspended/unadmitted users should receive clear bounded access messaging;
- admin invitations/account state are operational controls and should prioritize clarity over spectacle.

Do not expose whether an arbitrary email is already a Supabase/S.A.G.A. account through public-facing responses.

## Approval Language

- **Experimental** — design/implementation exists for evaluation only;
- **Reviewed candidate** — direction is ready for the next gate but not yet accepted implementation;
- **Approved** — affected engineering + responsive rendered + design-fidelity requirements passed;
- **Locked** — intentionally finalized; changing it requires an explicit reason/owner decision.

## Scope Discipline

A UI task does not authorize backend/schema/product changes merely because they would simplify implementation.

Likewise, an auth/backend change does not authorize an unrelated visual redesign.

RenderLab must remain unchanged. If its implementation reveals a useful principle, write the corresponding S.A.G.A. rule or reimplement the capability under S.A.G.A.-owned contracts instead of coupling the projects.
