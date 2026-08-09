# Controlled Release Candidate Operations

The release controller is fail-closed. CI creates `release-candidate.json` from a clean commit and two attested image digests. Operators register that file; they do not construct release rows or mutable image tags manually.

## State Machine

`candidate -> staging -> canary -> production`

Any staging or canary release may become `failed` or `rolled_back`. Production may only become `rolled_back`. Direct staging-to-production promotion is invalid.

## Registration

```powershell
saga-deploy release register-candidate --candidate-file release-candidate.json
saga-deploy release gate-record --release-id <release-id> --evidence-file ci-gate-evidence.json
saga-deploy release transition --release-id <release-id> --status staging
```

Gate evidence files contain `gate`, `status`, `source`, `observed_at_ms`, `expires_at_ms`, `details`, and an optional `artifact_reference`. Failed evidence requires a non-empty `details.reason`. Secret-like values are redacted before persistence; oversized evidence is rejected.

## Canary Gates

All gates below must have latest status `passed`:

- `ci`: matching Git SHA; backend, frontend, container, architecture, and source-secret checks passed.
- `database_recovery`: backup SHA-256, restored revision, and matching table counts.
- `artifact_recovery`: archive SHA-256, verified object checksums, and object count.
- `migration`: current/head revision match and rollback/re-upgrade proof.
- `staging_readiness`: dependency readiness tied to the release; maximum TTL one hour.
- `process_health`: fresh worker, scheduler, and observability heartbeats tied to the release; maximum TTL one hour.
- `production_qualification`: accepted real-book report tied to the release and source SHA-256; maximum TTL 24 hours.
- `usage_cost`: positive charge count, zero unpriced charges, and provider reconciliation; maximum TTL 24 hours.
- `slo`: no breaches or insufficient samples; maximum TTL one hour.
- `rollback`: prior release ID, immutable runtime/dashboard digests, and tested restore path.

```powershell
saga-deploy release gate-evaluate --release-id <release-id> --target canary
saga-deploy release transition --release-id <release-id> --status canary
```

## Production Gate

Run a bounded canary cohort on the release-specific queue. Record `canary` evidence with the matching release ID, positive sample count, zero failures, zero SLO breaches, and a tested rollback trigger. Canary evidence expires within one hour.

```powershell
saga-deploy release gate-record --release-id <release-id> --evidence-file canary-gate-evidence.json
saga-deploy release gate-evaluate --release-id <release-id> --target production
saga-deploy release transition --release-id <release-id> --status production
```

Promotion must not be attempted when any check is missing, failed, or expired. Application rollback uses the prior candidate's immutable image digests. Database downgrade is prohibited after serving writes unless the tested migration explicitly guarantees data safety; restore or forward-fix is preferred.
