# S.A.G.A. Vercel Deployment Policy

**Status:** Owner-authorized operational policy — 2026-09-11

## Rule

S.A.G.A. does not deploy to Vercel automatically from Git pushes, branches, pull requests, or merges.

The owner must give **explicit deployment approval for the specific deployment** before any agent/session triggers a Vercel Preview or Production deployment.

A request to implement, test, review, merge, or continue development is **not** deployment authorization.

## Default Development Path

Normal development uses:

1. focused GitHub branch/PR work;
2. deterministic GitHub Actions CI;
3. repository visual/render validation where already available;
4. exact-head review and merge.

Do not create a hosted Preview merely because a branch or PR exists. Prefer deterministic CI unless hosted behavior genuinely cannot be established without Vercel.

## When Deployment May Be Proposed

A deployment may be proposed after a major cohesive update, when a hosted integration must be tested, or when the owner asks to inspect a deployed version.

Before triggering it:

1. explain why a Vercel deployment is needed;
2. state whether Preview or Production is proposed;
3. identify the exact Git commit/ref intended for deployment;
4. ask the owner for explicit approval;
5. wait for approval before invoking Vercel or another deployment mechanism.

Approval is one-time and scoped to the deployment described. It does not authorize later deployments.

## Enforcement

The active Vercel project root is `apps/web/`.

`apps/web/vercel.json` must keep:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "git": {
    "deploymentEnabled": false
  }
}
```

This disables Git-triggered Preview and Production deployments while retaining the ability to deploy manually after owner approval.

`apps/web/tests/unit/foundation.test.mjs` contains a structural guard that fails if this switch is removed or enabled.

## Project Ownership

Active S.A.G.A. Vercel project:

- project name: `saga`
- project ID: `prj_AKQ8XTGUwpgOZRB9GHMd2lqIfRrc`
- Git repository: `faresmohamed260/saga`
- root directory: `apps/web`

The historical Vercel project `studio` (`prj_6rcIyP3exqAJ0KtIspFs2V1KoeSx`) was disconnected from the S.A.G.A. Git repository on 2026-09-11 and must not be reconnected without a new owner decision.

RenderLab is separate and must not be modified as part of S.A.G.A. deployment work.

## Current Production Baseline at Policy Adoption

At adoption, the owner manually created a READY S.A.G.A. Production deployment from `main` commit:

`b171d96f9a7391be1bef3894a29804ec95a53822`

Do not assume Production advances with later merges. Always inspect the actual deployed source SHA when hosted state matters.
