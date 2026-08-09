# Modal Runtime

`packages/modal_runtime` is the active reusable runtime surface for Modal-backed provider pools.

It is the single architecture boundary for:

- Modal endpoint rotation
- live endpoint discovery
- retry/failover behavior
- sticky warm-endpoint reuse
- provider operational state persistence

## Current Components

- `packages/modal_runtime.pool.ModalEndpointPool`
- `packages/modal_runtime.models`
- `packages/modal_runtime.state`

## Contracts

Provider operational state is normalized through:

- `ModalRuntimeState`
- `ModalTokenStatus`
- `ModalLastSuccessfulRequest`
- `ModalEndpointUrls`
- `ModalEndpointDescriptor`
- `ModalEndpointRequestMetadata`
- `ModalExecutionRequestMetadata`
- `ModalExecutionResult`

These contracts absorb legacy per-provider field drift such as:

- `last_render_ok`
- `last_live_ok`

and normalize them to a shared request-success surface.

`ModalExecutionRequestMetadata` is now runtime-owned observability metadata, not just a pass-through of upstream provider fields. In the active architecture:

- `modal_runtime` always generates its own `trace_id`
- `run_id` and `parent_trace_id` come from the active runtime trace scope
- upstream provider traces, when present, are preserved separately as `upstream_trace_id`
- persisted `last_successful_request` snapshots now carry the same normalized trace metadata shape

Persisted state is stored through the unified persistence runtime in:

- `provider_configs.payload.runtime_state`
- `provider_statuses`

Active callers should not read those storage rows directly. They should consume either:

- `packages.modal_runtime.state`
- `persistence_get_provider_operational_state`

When a caller needs an operationally safe, agent-facing view, `persistence_get_provider_operational_state` is the preferred surface because it now reports normalized active state plus lifecycle diagnostics for malformed or contradictory persisted provider metadata.

## Required Usage Rules

Do not bypass the runtime by:

- writing raw pool state JSON files as a source of truth
- writing directly to `provider_configs` or `provider_statuses` outside the runtime
- scraping nested `config.payload.runtime_state` shapes in API or agent code when the normalized operational-state contract exists
- storing Modal operational state in integration-local globals
- inventing per-provider parallel status schemas

Integrations should:

- subclass `ModalEndpointPool`
- persist runtime state through `packages.modal_runtime.state`
- keep provider-specific request logic inside the integration package
- keep provider-independent pool behavior inside `packages/modal_runtime`
- rely on validated upstream provider/runtime config rather than silently accepting malformed endpoint settings

## Operational Semantics

- `app_name` and `runtime_generation` are part of the persisted runtime identity.
- mismatched runtime metadata invalidates stale state instead of reusing it.
- token/account state is keyed by stable `token_name`.
- health and request success are tracked separately.
- warm endpoint preference is advisory, not a source of truth.
- failover should update provider operational state before trying the next token.
- endpoint execution now returns a typed payload that separates:
  - endpoint identity
  - live health payload
  - provider response payload
  - request metadata and latency
- runtime traces now carry structured `events` so failover and execution diagnostics do not depend on free-form logs
- endpoint execution tracing must never depend on the upstream provider returning its own trace identifier

## Relationship To Persistence Runtime

`modal_runtime` does not own durable storage itself.

It depends on `packages/persistence_runtime` for:

- provider configuration persistence
- provider status persistence
- durable operational metadata

That dependency is deliberate. Modal pool logic stays reusable while persistence remains provider-oriented and swappable.
