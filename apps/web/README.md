# S.A.G.A. v2 Web

`apps/web` is the **current S.A.G.A. v2 product surface**.

The repository has completed the Phase 1 closed-demo/account foundation and the Phase 2 repository foundation. Phase 3 local-first narrative analysis is active. The complete v2 product is not yet production-ready end to end; see [`../../PROJECT.md`](../../PROJECT.md) for current status.

## Stack

- Next.js 16
- React 19
- TypeScript
- Tailwind CSS
- Supabase SSR client
- Backblaze B2 through the AWS S3-compatible SDK boundary

## Requirements

- Node.js 24
- npm
- Supabase/B2 credentials only for integration-dependent runtime paths

The production build should succeed without live Supabase/B2 credentials. Integration-dependent routes/features should fail only when invoked, not during a static application build.

## Setup

Install exactly from the application lockfile:

```bash
npm ci
```

Copy `.env.example` to `.env.local` and provide the runtime values needed by the features you are exercising. Never commit `.env.local` or real secrets.

Start the development server:

```bash
npm run dev
```

## Quality gates

Run the same model-light checks used by the v2 web CI:

```bash
npm run lint
npm run typecheck
npm run test:unit
npm run build
```

## Environment contract

Use [`.env.example`](.env.example) as the source of truth for variable names.

### Supabase

Current application configuration includes:

```text
SUPABASE_URL=
SUPABASE_PUBLISHABLE_KEY=
SUPABASE_SECRET_KEY=
```

`SUPABASE_SERVICE_ROLE_KEY` exists only as a legacy compatibility path when the modern secret key is not configured. Privileged credentials must remain server-only and should only enter code paths that require them.

### Backblaze B2 runtime

Normal web runtime storage uses a **non-master, bucket-scoped application key**:

```text
SAGA_B2_BUCKET=
SAGA_B2_ENDPOINT=https://s3.<region>.backblazeb2.com
SAGA_B2_REGION=<region>
SAGA_B2_APPLICATION_KEY_ID=
SAGA_B2_APPLICATION_KEY=
```

Do not configure B2 bootstrap/master credentials under runtime variable names.

Repository bootstrap secrets are separate and are consumed only by bounded GitHub Actions bootstrap paths. They must never enter normal Vercel/runtime configuration.

## Architectural boundaries

- Product/feature code must not instantiate `S3Client` directly.
- Storage access flows through the web storage boundary under `src/server/storage`.
- Supabase server access flows through `src/server/supabase`.
- `/api/health` reports configuration presence only and does not contact providers.
- Current v2 code must not import pre-v2 Python/runtime implementation as authoritative application behavior.
- Browser code must not directly call local analysis models.

## Repository context

Useful entry points:

- [`../../README.md`](../../README.md) — public project overview and quick start.
- [`../../PROJECT.md`](../../PROJECT.md) — current project handoff.
- [`../../docs/README.md`](../../docs/README.md) — documentation index.
- [`../../docs/v2/ANALYSIS_ARCHITECTURE_2026.md`](../../docs/v2/ANALYSIS_ARCHITECTURE_2026.md) — current analysis architecture.
- [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md) — repository contribution workflow.

`apps/dashboard_api` and `apps/dashboard_pro` are retained earlier application surfaces. New v2 frontend/product work belongs here unless an active issue explicitly says otherwise.
