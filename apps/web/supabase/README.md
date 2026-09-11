# S.A.G.A. v2 Supabase migrations

This directory is the **active v2 database lineage** for `apps/web`.

## Important boundary

The repository-root `supabase/migrations/` directory predates the v2 rebuild and belongs to the historical v1 persistence/runtime work. **Do not apply those root migrations to the new S.A.G.A. v2 Supabase project.**

A fresh v2 project begins from the migrations in this directory only, in lexical/timestamp order.

## Application rules

- migrations are additive and reviewed in GitHub before hosted application;
- schema/table/function names are S.A.G.A.-owned and must not reuse RenderLab/Studio ownership;
- privileged tables use RLS plus explicit grants/revokes;
- browser roles do not receive access merely because RLS exists;
- Auth identity is referenced by UUID, but application authorization remains in S.A.G.A.-owned records;
- raw invite/recovery tokens or reusable Auth secrets must never be persisted in application tables;
- hosted migration application is a separate operation and requires the new S.A.G.A.-owned Supabase project.

Phase 1B starts the lineage with closed-demo account access and invitation state.