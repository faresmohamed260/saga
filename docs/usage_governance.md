# Provider Usage And Cost Governance

`packages/observability_runtime` owns provider-neutral accounting, pricing, budget admission, reconciliation, and operational summaries. Provider runtimes own only extraction of their native usage evidence. Agents and orchestration contain no provider billing logic.

## Accounting Flow

1. `production_orchestration` establishes release, run, series, stage, and agent attribution with `runtime_common.usage_scope`.
2. A provider runtime reserves declared maximum usage before an upstream request.
3. The provider runtime extracts native or directly measured usage from the response at its transport boundary.
4. `UsageGovernanceRuntime` appends a reservation release and immutable charge to `usage_ledger`.
5. Atomic PostgreSQL advisory locks serialize applicable global, run, provider, account, and model budgets.
6. Qualification and Dashboard surfaces query the normalized ledger; they never recalculate provider-specific usage.

Reservations expire after a bounded TTL. Settlement is idempotent. Failed requests are still recorded as measured request attempts. Credentials and raw provider responses are excluded from ledger evidence and sanitized before observation export.

## Pricing

Native provider cost has priority. Otherwise, a versioned `CostRate` supplied through `SAGA_PROVIDER_COST_RATES_JSON` prices explicit units. Rates may target a provider, model, account alias, or account-model pair; the most specific matching rate wins regardless of configuration order. Missing rates remain `unpriced`; cost is never inferred from latency.

```json
[
  {
    "provider": "mistral",
    "model": "mistral-large-2512",
    "input_per_million": 2.0,
    "cached_input_per_million": 0.2,
    "output_per_million": 6.0,
    "pricing_version": "mistral-public-2026-08-09"
  }
]
```

Rates are deployment configuration, not source defaults. Review them against the provider's current billing page before each release. Ollama individual cloud plans are subscription and usage-weight based, so their token usage remains visible but must stay unpriced unless account-native billing evidence or an explicit contract rate is available.

## Budgets

`UsageBudgetPolicy` supports hard or warning limits over `request_count`, token units, compute seconds, images, audio seconds, and USD cost. Scopes are `global`, `run`, `provider`, `account`, and `model`. A blank non-global scope value applies the limit independently to each value in that scope.

Hard-limit admission fails before the provider call. Soft breaches emit `usage.budget_warning`; hard denials emit `usage.budget_denied`. Material actual-cost overages above the reservation emit `usage.reconciliation_anomaly`; conservative reservations that settle lower do not.

## Production Gate

Production qualification requires:

- at least one attributed provider charge;
- zero unpriced charges;
- provider latency/error/rotation telemetry;
- no secret exposure;
- immutable release and run attribution.

The Dashboard API exposes summaries and policy configuration at `/runtime/usage/summary` and `/runtime/usage/budgets/{policy_id}`. The Providers page presents request, cost, pricing coverage, provider breakdown, and active-budget counts.

## Validation Evidence

- Isolated PostgreSQL migration: usage governance was introduced at `202608090300`; the current release schema head is `202608090400`.
- Real Mistral inference on 2026-08-09 returned 40 input and 10 output tokens. The immutable charge matched those native counts exactly and reconciled to `$0.00014` using the dated `$2/M` input and `$6/M` output rate.
- Deterministic tests cover concurrent hard-budget admission, per-run isolation, expired-reservation settlement, release of unused reservations, idempotent settlement, native-cost priority, explicit unpriced usage, and secret sanitization.
