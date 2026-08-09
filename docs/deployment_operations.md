# Production Deployment And Operations

## Scope

This runbook covers only the active package architecture. API, execution workers, scheduler, observability, frontend, PostgreSQL migrations, and artifact recovery are independently operable. No deployment role imports or starts legacy application code.

## Process Topology

| Role | Responsibility | Scale model | Health authority |
|---|---|---|---|
| `migrate` | Apply one versioned Alembic migration chain | One job per rollout | Migration head check |
| `api` | HTTP control/read surface | Horizontal, stateless | `/live` and dependency-aware `/ready` |
| `worker` | Lease and execute queued runs | Horizontal by queue/capability | Durable process heartbeat |
| `scheduler` | Recover leases and sample queue depth | One active replica | Durable process heartbeat |
| `observability` | Retention, SLO evaluation, alert export | One active replica | Durable process heartbeat |
| `frontend` | Static dashboard and API reverse proxy | Horizontal | HTTP server health |
| `otel-collector` | Receive OTLP metrics/traces/logs | Independent collector tier | Collector process health |

Workers coordinate through PostgreSQL leases and capability limits. API startup does not start workers. Process roles share contracts and release identity, not process memory.

## Build And Configuration

Use `uv.lock`, digest-pinned base images, and the production Dockerfiles. CI publishes commit- and version-tagged images to GHCR with build-provenance attestations, refuses to overwrite an existing version tag, and retains a release manifest containing both component digests. Deploy by image digest, never by a mutable tag.

Set `SAGA_RUNTIME_IMAGE` and `SAGA_DASHBOARD_IMAGE` to the manifest's complete GHCR `name@sha256:digest` references. Runtime roles join both the private `saga-production` network and the configurable external `SAGA_PERSISTENCE_NETWORK`; the default `supabase_default` value supports the documented self-hosted Supabase topology without exposing PostgreSQL or Storage through ad hoc host routing.

Copy `deploy/production/.env.example` to a secret-managed deployment environment. Inject database fields, Supabase keys, and provider credentials at deployment time. Do not commit the populated file or pass passwords in command arguments. Production startup validates Alembic revision `202608090400` and fails closed if schema or dependencies are unavailable.

## Staged Rollout

1. Run the complete CI gate and publish both images from a clean commit.
2. Back up the `public` application schema and all configured artifact buckets.
3. Run `saga-deploy migrate upgrade` as a single job.
4. Run `saga-deploy migrate check` and `saga-deploy health`.
5. Register the CI-produced immutable candidate with `saga-deploy release register-candidate`, import CI evidence, then transition it to `staging`.
6. Start one API, scheduler, observability process, and one worker on a staging queue.
7. Verify `/ready`, process heartbeats, OTLP receipt, queue depth, and one real-book execution audit.
8. Record all required immutable gate evidence and evaluate eligibility with `saga-deploy release gate-evaluate --target canary`.
9. Transition to `canary`, route only the bounded validation cohort, and record fresh canary evidence.
10. Transition to `production` only when `gate-evaluate --target production` passes.

Release promotion is serialized with a PostgreSQL advisory transaction lock and protected by a unique partial index, so only one production release can exist. Direct staging-to-production transitions are invalid.
The deployment runtime rejects canary and production promotion unless the manifest declares clean source provenance, contains a full 40-character Git SHA, includes immutable runtime and dashboard image digests, and has complete non-expired gate evidence. Dirty local validation builds cannot be registered as release candidates.

## Rollback

Application rollback uses the prior immutable image digests. Mark the failed release `rolled_back`, deploy the prior API/process images, and verify readiness and heartbeats. Do not downgrade a database revision unless its documented downgrade is data-safe and a tested backup exists. Forward-fix is preferred after a migration has served writes.

## Database Recovery

`saga-deploy backup create --output <file>` creates a custom-format backup of application-owned `public` data only, excludes ownership/ACL coupling, writes a SHA-256 manifest, and keeps passwords out of argv. Restore requires an exact database-name confirmation, provisions the required `vector` extension, and restores only configured application schemas.

Restore into a newly created isolated database first:

```powershell
saga-deploy backup restore --input <file> --confirm-target <exact_database_name>
saga-deploy migrate check
saga-deploy health --service recovery-validation
```

Compare critical table counts and execute a read/write validation before cutover. Supabase-managed schemas are recovered with the Supabase platform procedure, not the application archive.

## Artifact Recovery

`saga-deploy artifacts create --output <file> --buckets <comma-separated-buckets>` snapshots objects through the provider-neutral `ObjectStorageStore`. Every object has a size and SHA-256 entry. Restore requires `--confirm-target artifact-storage`, verifies each checksum, creates missing buckets, and uploads through the same abstraction. This is separate from database recovery because object bytes and storage metadata have different consistency and retention requirements.

For a consistent recovery point, pause new execution leases, wait for active writes to drain, record the release ID, then create database and artifact snapshots in the same maintenance window.

## Operational Checks

- `/live` proves only that the API process can answer.
- `/ready` validates database connectivity and migration ownership; it returns 503 when dependencies are degraded.
- `saga-deploy process-health --role <role>` verifies recent durable heartbeats.
- Container health checks use the bounded `packages.deployment_runtime.heartbeat_probe` path, which performs one direct PostgreSQL heartbeat query with a three-second connection deadline instead of initializing the full control plane. Workers emit process heartbeats on an independent thread so long-running jobs remain distinguishable from stalled processes.
- Scheduler metrics include queue depth; execution observations include latency, failures, retries, lineage, and SLO results.
- OTLP uses the pinned official collector image and `/v1/metrics`, `/v1/traces`, and `/v1/logs` endpoints.

## Residual Risks

- The local Compose topology is a deployment reference, not an HA orchestrator. Production should use a platform with replicated scheduling, managed secrets, and environment approvals.
- Database and object snapshots are coordinated operationally, not by a distributed transaction.
- Alert delivery currently depends on configured observability exporters; production paging integration must be supplied per environment.
- Capacity limits require load-specific tuning from measured queue and provider latency.
- Production canary traffic requires an environment-specific router or queue cohort; the deployment runtime owns eligibility and evidence, not vendor-specific traffic switching.

## Validation Evidence

The 2026-08-09 staging validation established:

- Alembic upgrade, rollback, re-upgrade, and one-head checks on isolated PostgreSQL; release-gate schema validated at `202608090400`.
- Concurrent PostgreSQL promotion attempts both completed while the unique invariant retained exactly one production release.
- Runtime and frontend images built successfully; runtime executes as non-root and frontend dependency audit reports zero vulnerabilities.
- API liveness remained 200 while an unavailable database produced readiness 503.
- Containerized API, scheduler, observability, and worker roles started against self-hosted Supabase; all durable role health checks passed.
- Official OpenTelemetry Collector `0.152.1` received scheduler metrics with no export errors.
- A 98,797,551-byte application backup restored at migration head with exact sampled table-count matches.
- A 112,095,596-byte artifact archive restored 132 objects across six non-empty buckets with per-object checksum verification.
- Real-book audit for `real-lineage-input-20260808a` completed with terminal success, nine observed stages, ten lineage records, 91 observations, all six SLOs healthy, and secret audit passed.
- Clean-checkout backend regression: 248 passed, 3 skipped. Dashboard: 13 passed, production build and dependency audit passed with zero vulnerabilities.
- Runtime and dashboard containers build from digest-pinned bases and run as non-root users; the dashboard image passed its internal health check as UID 101.
- The obsolete 96.5 MB SQLite seed deployment was removed from the active tree; Supabase/PostgreSQL remains the only production persistence path.

The original qualification release is explicitly marked `source_state=dirty`; it remains validation metadata and cannot be promoted. Release stabilization verified the complete migration chain through `202608090200`; usage governance added `202608090300`; immutable release-gate evidence and canary state add `202608090400`.
