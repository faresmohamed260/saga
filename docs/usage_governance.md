# Provider Usage And Cost Governance

`packages/observability_runtime` owns provider-neutral accounting, pricing, budget admission, reconciliation, and operational summaries. Provider runtimes own only extraction of their native usage evidence. Agents and orchestration contain no provider billing logic.

## Accounting Flow

1. `production_orchestration` establishes release, run, series, stage, and agent attribution with `runtime_common.usage_scope`.
2. A provider runtime reserves declared maximum usage before an upstream request.
3. The provider runtime extracts native or directly measured usage from the response at its transport boundary.
4. `UsageGovernanceRuntime` appends a reservation release and immutable charge to `usage_ledger`.
5. Atomic PostgreSQL advisory locks serialize applicable global, project, run, provider, account, and model budgets.
6. Qualification and Dashboard surfaces query the normalized ledger; they never recalculate provider-specific usage.

Reservations expire after a bounded TTL. Settlement is idempotent. Failed requests are still recorded as measured request attempts. Credentials and raw provider responses are excluded from ledger evidence and sanitized before observation export. Ledger failures fail open at the shared runtime boundary and cannot turn a successful provider request into a workload failure; explicit hard-budget denials still fail closed before the request.

Summaries distinguish provider-confirmed units from locally measured and declared units. Provider-confirmed coverage is independent from pricing coverage because provider-native usage and provider-native billing cost are different claims.

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

`UsageBudgetPolicy` supports hard or warning limits over `request_count`, token units, compute seconds, images, audio seconds, and USD cost. Scopes are `global`, `project`, `run`, `provider`, `account`, and `model`. A blank non-global scope value applies the limit independently to each value in that scope.

Hard-limit admission fails before the provider call. Soft breaches emit `usage.budget_warning`; hard denials emit `usage.budget_denied`. Material actual-cost overages above the reservation emit `usage.reconciliation_anomaly`; conservative reservations that settle lower do not.

## Production Gate

Production qualification requires:

- at least one attributed provider charge;
- zero unpriced charges;
- provider latency/error/rotation telemetry;
- no secret exposure;
- immutable release and run attribution.

The Dashboard API exposes summaries and policy configuration at `/runtime/usage/summary` and `/runtime/usage/budgets/{policy_id}`. Summary filtering and breakdowns support explicit `project_id` attribution in addition to run, stage, provider, account, and model dimensions.

## Provider Support Matrix

- Ollama: provider-confirmed input/output token counts and evaluation compute duration when returned.
- Mistral: provider-confirmed input/output/cached token counts; transcription audio duration is measured from source audio.
- Gemini: provider-confirmed prompt, candidate, and cached-content token counts when returned.
- OpenAI-compatible general compute: provider-confirmed input/output/cached token counts and native cost only when present upstream.
- Modal image/coreference/TTS: account-attributed requests and response-reported or locally measured execution duration; image count and rendered audio duration are measured. Workflow responses do not currently expose provider-native billed GPU seconds or request cost.
- Web search and MediaWiki: measured HTTP request counts. Public endpoints do not expose native billable usage or cost.

## Validation Evidence

- Isolated PostgreSQL migration: usage governance was introduced at `202608090300`; explicit project attribution was added at schema head `202608120100`.
- Real Mistral inference on 2026-08-09 returned 40 input and 10 output tokens. The immutable charge matched those native counts exactly and reconciled to `$0.00014` using the dated `$2/M` input and `$6/M` output rate.
- Persisted production data contains 2,186 provider-confirmed Ollama charges, 606 provider-confirmed Mistral charges, 1,173 measured Mistral transcription attempts, and 125 measured Modal charges with compute/image/audio units.
- Deterministic tests cover concurrent hard-budget admission, project/run isolation, expired-reservation settlement, release of unused reservations, idempotent settlement, native-cost priority, explicit unpriced usage, source coverage, fail-open telemetry errors, and secret sanitization.
