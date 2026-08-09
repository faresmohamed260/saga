# Observability Runtime

`packages/observability_runtime` is the provider-neutral operational telemetry and SLO boundary. It consumes existing runtime traces, terminal execution state, queue events, and lineage; it does not instrument agents or own deployment-specific monitoring infrastructure.

## Guarantees

- Correlation IDs are first-class fields, not metric dimensions.
- Observation IDs are deterministic, making terminal ingestion idempotent and safe under concurrent delivery.
- Metrics cover run throughput/success/duration, queue depth/wait/retries/lease expiry/dead letters, stage latency and acceptance, artifact reuse/invalidation, quality outcomes, provider latency/errors/rotation/cold starts, and explicit usage/cost data.
- Cost is emitted only from explicit usage plus versioned injected rates. Cold-start metrics require explicit provider metadata; neither is guessed from latency.
- Dimension keys are allowlisted and bounded. Nested payloads are depth/size limited and secret-like fields are redacted.
- Operational history is queryable through `persistence_runtime.observability`, with indexed time, run, metric, component, and provider filters.
- SLO aggregation and breach IDs are deterministic. Alert records are append-only and idempotent.
- Exporters are injected ports. Export failure is reported but cannot reverse committed execution or observation persistence.
- `OpenTelemetryJsonExporter` maps records to portable span, metric, and log semantics without requiring a vendor SDK in the core package.
- Retention is explicit and operator-triggered through `enforce_retention`; production execution never deletes history implicitly.

## Integration

`execution_runtime.ExecutionWorker` invokes an independent terminal observer after durable queue completion. `PersistenceExecutionObserver` supplies queue depth, current and historical lineage, and the orchestration result. Domain agents and provider runtimes remain unaware of monitoring infrastructure.

The existing JSON runtime-report exporter remains a separate diagnostic artifact. It is not the normalized metrics store and can be retired independently if operations no longer require raw reports.

Configuration:

- `SAGA_OBSERVABILITY_RETENTION_DAYS`, default `30`
- exporter transports, pricing tables, SLO definitions, and alert routing are injected deployment configuration rather than environment access inside the package

## Validation

Deterministic tests cover idempotent and concurrent persistence, aggregation and p95 breaches, alert deduplication, retention, exporter failure isolation, OpenTelemetry mapping, cardinality controls, cost calculation, explicit cold-start/rotation signals, and secret safety.

Run a bounded observation of an already accepted production execution without invoking providers:

```powershell
python -m scripts.validate_real_observability_runtime --run-id <accepted-run-id>
```

On August 8, 2026, the accepted `real-lineage-input-20260808a` execution produced 91 idempotent observations from 15 queue events, 10 lineage records, nine latest stage outcomes, and seven unique provider traces recovered from immutable snapshots. The audit measured a 45 ms queue wait, 673.026 seconds total execution, three reused stages, six invalidated/executed stages, zero provider errors, and Ollama/Mistral provider latencies from 2.828 to 11.302 seconds. Run success, queue wait, dead-letter, lease-expiry, stage-acceptance, and provider-error SLOs were healthy; the environment-secret scan passed.

The complete active suite passed as four bounded groups: 226 passed and 3 environment-dependent tests skipped.

## Operational Ownership

- `runtime_common` owns trace creation and correlation contracts.
- Domain/provider runtimes own accurate trace and explicit usage metadata emission.
- `execution_runtime` owns the observation composition boundary.
- `observability_runtime` owns normalization, aggregation, SLO evaluation, safeguards, and exporter contracts.
- `persistence_runtime` owns durable observation records.
- Deployment configuration owns collectors, dashboards, alert routing, retention scheduling, and versioned pricing.

## Residual Risks

- Provider traces absent from terminal outcomes or lineage snapshots cannot be reconstructed; provider runtimes should consistently retain their trace envelopes in owned outcome metadata.
- Queue depth is a terminal snapshot, not a continuously sampled gauge. A deployment scheduler should invoke periodic sampling if second-level queue dashboards are required.
- Default SLOs are conservative starting points and need production traffic history before contractual objectives and paging thresholds are finalized.
- Pricing is intentionally unset by default to prevent misleading cost estimates.
