# Agent Framework

S.A.G.A. now standardizes on **LangGraph** as the agent workflow framework.

## Current Direction

- `packages/agent_runtime` is the shared LangGraph-backed execution surface.
- `packages/reasoning_runtime` is used directly as the planner/decision runtime.
- Runtime packages expose **native LangGraph-compatible tools** through `as_langgraph_tools()`.

## Native Tool Support

The following runtime packages now expose LangGraph-native tools without a SAGA-side adapter layer:

- `packages/reasoning_runtime`
- `packages/persistence_runtime`
- `packages/retrieval_runtime`
- `packages/web_search_runtime`
- `packages/modal_runtime` for provider operational lifecycle, though not as an agent tool surface

The intent is that reusable runtime packages remain the source of truth for framework compatibility. S.A.G.A. should compose those packages, not re-wrap them into parallel integration layers.

## Execution Model

`packages/agent_runtime.graph.AgentGraphRuntime` provides:

- LangGraph state graph orchestration
- a reasoning-driven planner loop
- native tool invocation through LangGraph tools
- checkpoint-ready execution with thread ids
- durable checkpoint persistence by default through `SqlCheckpointSaver`
- shared `run_id` / `trace_id` propagation into runtime tool calls
- planner coercion for near-valid model outputs such as:
  - `action=run` normalized to `action=tool`
  - stringified JSON `tool_input`
  - single-tool or query-tool name recovery
  - context hydration for retrieval `index_ref`
  - normalization of nullable optional tool fields into schema-safe defaults
- deterministic fallback responses from the latest successful tool output when a later planner turn fails
- repeated-tool protection that converts identical successful tool replays into a final response instead of looping
- retrieval-response grounding that reanchors a weak planner answer to the highest-ranked retrieval result when the response drifts away from the ranking
- typed tool history records that store `RuntimeToolEnvelope` and `RuntimeTrace` objects rather than free-form dictionaries
- explicit planner response-schema enforcement via `json_schema` response formatting on the reasoning runtime path
- typed planner-history records so orchestration diagnostics cover reasoning turns as well as tool turns
- optional required-tool execution policy through agent context so specific runtime tool sequences can be enforced without ad hoc agent-side wrappers
- required-tool synthesis for common runtime operations so the graph can continue a mandated tool chain when the planner answers prematurely
- required-tool policies are enforced in sequence order, not just as a loose set of allowed tools
- planner-output validation is enforced inside `agent_runtime` even when the underlying reasoning provider/client does not enforce the supplied validator itself
- web-search driven required flows now hydrate a minimum candidate count and use query-aware result selection before document fetch
- persistence-backed artifact serving can now rely on runtime object metadata instead of filename-only media-type guessing
- required runtime sequences now short-circuit to the latest grounded runtime evidence instead of looping back into already successful tools

This is the foundation to migrate existing S.A.G.A. agents incrementally onto LangGraph.

For the current system-level breakdown of analysis agents, generation agents, progress status, and recommended implementation order, see [docs/system_agent_roadmap.md](B:\Documents\PyCharm\graduationProject\docs\system_agent_roadmap.md).

## Durable Checkpointing

The active agent runtime no longer treats in-memory checkpointing as an acceptable default.

Production agent execution should provide one of:

- `checkpoint_engine=...`
- `checkpoint_database_url=...`
- `SAGA_AGENT_RUNTIME_DB_URL`

If none of those are supplied, `AgentGraphRuntime` fails fast instead of silently using process memory.

`allow_in_memory_checkpointer=True` exists only for explicit test/debug scenarios and must not be used in production execution paths.

## Tool Contract

Active runtime packages should return the same envelope shape from LangGraph tools:

- `ok`
- `data`
- `trace`
- `error`

This keeps agent orchestration decoupled from package-specific payload quirks and makes cross-runtime observability consistent.

Typed runtime payloads now exist for key high-churn agent boundaries:

- shared runtime request metadata
- reasoning request metadata
- reasoning text/json tool payloads
- retrieval index references
- retrieval index/query tool payloads
- retrieval indexed documents
- retrieval query results, including `excerpt`
- web search request metadata
- web search search/document payloads
- modal endpoint execution payloads and metadata

Within the reasoning runtime, JSON tool results now expose lightweight payload diagnostics and optional top-level key validation. Agent callers can rely on:

- `payload_kind`
- `payload_keys`
- `field_count`

and can require specific top-level keys through the native `reasoning_generate_json` tool surface instead of treating every JSON result as an unvalidated blob.

Within the web-search runtime, search-result metadata and fetched-document metadata are now typed contract surfaces rather than arbitrary dictionaries. Agent callers should rely on stable fields such as:

- `page_title`
- `page_id`
- `source_type`
- `categories`
- `status_code`

Within the retrieval runtime, indexed-document and query-result metadata now expose typed stable fields instead of arbitrary dictionaries. Agent callers should prefer:

- `characters`
- `attributes`

For agent-facing runtime payloads, request-scoped operational metadata should now be exposed under one stable field name:

- `request_metadata`

This applies to reasoning, retrieval, and web-search runtime payloads. Domain/business metadata should stay in domain fields such as:

- `metadata` for document/object attributes
- `trace.metadata` for runtime trace annotations

Agents and services in the active architecture should not infer request diagnostics from package-specific payload keys when `request_metadata` exists.

Persistence provider-lifecycle payloads now use the same pattern for:

- `persistence_get_provider_config`
- `persistence_list_provider_statuses`
- `persistence_get_provider_operational_state`

Reasoning metadata now also captures:

- `request_kind`
- `json_mode`
- `response_format_type`
- `tool_mode`

Runtime tools are now built through the shared `packages.runtime_common.build_structured_runtime_tool()` path. That means:

- common `ok/data/trace/error` envelopes
- shared error categorization
- shared retryability semantics
- consistent trace metadata across reasoning, persistence, retrieval, and web search
- shared structured runtime events under `trace.events`

`trace.events` is now the canonical structured event trail for agent-visible runtime diagnostics. Active code should rely on these typed events rather than ad hoc print/debug output when diagnosing multi-runtime execution.

Runtime configuration models now fail fast on invalid construction for the active runtimes. Invalid URLs, empty required identifiers, or obviously unsafe runtime settings should be rejected before agent execution begins.

For reasoning-driven planning, the active runtime now distinguishes:

- text requests
- strict JSON requests
- schema-guided JSON requests
- tool-calling requests

through request metadata so planner failures can be diagnosed by request type rather than by raw logs alone.

The planner path now passes an explicit response schema for `AgentPlannerDecision`. That means the active architecture no longer relies only on “please return JSON” prompting for orchestration decisions.

`AgentExecutionResult` now carries:

- `planner_history`
- `tool_history`
- `last_decision`
- `summary`

so post-run diagnostics can distinguish planner failures from tool failures without reconstructing state from logs.

`summary` is the normalized agent-facing execution health surface. It now reports:

- `run_id`
- `thread_id`
- `status`
- planner/tool step counts
- successful vs failed tool counts
- latest tool identity/trace id
- required-tool completion counts
- `remaining_required_tools`

Callers should prefer `summary` for orchestration health/status checks rather than inferring execution state from raw history arrays and free-form error strings.

`AgentExecutionResult` also now exposes `to_report_payload()`, which returns a typed `agent_execution_report` payload suitable for durable persistence through the active persistence runtime, for example as a `runtime_report` artifact.

## What Must Not Be Bypassed

Active agents and services should not:

- read or write persistence tables directly when a runtime surface exists
- persist provider operational state outside `packages.modal_runtime.state`
- call storage backends directly when `persistence_runtime.objects` or `persistence_runtime.artifacts` exists
- invent agent-local tool contracts that diverge from runtime-native tool contracts
- rely on per-agent tracing hacks instead of shared runtime trace envelopes
- bypass the canonical runtime tool builder with ad hoc tool-envelope logic
