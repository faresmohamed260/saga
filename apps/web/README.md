# S.A.G.A. v2 Web

`apps/web` is the active S.A.G.A. v2 product surface.

## Stack

- Next.js 16
- React 19
- TypeScript
- Tailwind CSS
- Supabase SSR client
- Backblaze B2 through the AWS S3-compatible SDK boundary

## Commands

```text
npm install --no-audit --no-fund
npm run dev
npm run lint
npm run typecheck
npm run test:unit
npm run build
```

The production build must succeed without live Supabase/B2 credentials. Integration-dependent routes/features should fail only when invoked, not during a static application build.

## Environment Contract

### Supabase

Server/application configuration:

```text
SUPABASE_URL=
SUPABASE_PUBLISHABLE_KEY=
SUPABASE_SERVICE_ROLE_KEY=
```

The service-role key must remain server-only and should be introduced only to code paths that actually require privileged database/storage operations.

### Backblaze B2 runtime

Normal web runtime storage uses a **non-master, bucket-scoped application key**:

```text
SAGA_B2_BUCKET=
SAGA_B2_ENDPOINT=https://s3.<region>.backblazeb2.com
SAGA_B2_REGION=<region>
SAGA_B2_APPLICATION_KEY_ID=
SAGA_B2_APPLICATION_KEY=
```

Do not configure the bootstrap master key under these runtime names.

Repository bootstrap secrets are separate:

```text
SAGA_B2_KEY_ID
SAGA_B2_MASTER_APPLICATION_KEY
```

Those are consumed only by the bounded GitHub Actions bootstrap path and must never enter Vercel runtime configuration.

## Boundaries

- product/feature code must not instantiate `S3Client` directly;
- storage access flows through `src/server/storage`;
- Supabase server access flows through `src/server/supabase`;
- the `/api/health` route reports configuration presence only and does not contact providers;
- v2 code must not import pre-v2 Python/runtime implementation.

## Next

Phase 0 establishes the deployable shell and storage bootstrap. Phase 1 will turn this foundation into the main S.A.G.A. frontend/backend product before agentic AI implementation begins.