# RC38 bounded canon qualification

Date: 2026-08-13

Status: **not promotable**

## Scope

- Source: `The Cruel Prince.epub`
- Run: `qualification-ae8d57c35f`
- Series: `qualification-series-ae8d57c35f`
- Project: `qualification-project-rc38-canon-bounded-20260813`
- Stages: analysis foundation and canon extraction only
- Hard limits: 300 seconds per run/stage and 40 persisted Mistral requests

## Baseline

RC37 issued 172 Mistral requests: 75 event, 85 entity, and 12 relationship requests before cancellation. It used 241,838 input tokens, 46,031 output tokens, and an estimated $0.0639. The minimum request count of the three independent passes was 129.

## Implementation

- Replaced the active three-pass graph with one structured canon request per chapter followed by deterministic materialization and timeline construction.
- Added durable chapter checkpoints and resume behavior.
- Required `project_id` at orchestration boundaries and propagated it into jobs, lineage, usage, and deliverable provenance.
- Added fail-closed per-stage/provider request limits seeded from persisted charge rows, so retries cannot reset a run budget.
- Reduced default canon concurrency from four to three and raised the provider-request timeout from 60 to 180 seconds.
- Made queue retry backoff explicit and preserved it across requeue operations.
- Allowed missing model-supplied `entity_type` at ingress because deterministic normalization already classifies grounded entities before persistence.

## Test evidence

- Focused gate: 88 passed.
- Post-budget gate: 79 passed.
- Targeted remediation gate: 2 passed.
- Full repository gate: inconclusive; stopped at the planned 180-second ceiling with no failure output.

## Live evidence

- Analysis foundation completed in 181.3 seconds. The Modal identity call used 103.0 compute seconds.
- The first bounded execution terminated in 268.0 seconds rather than hanging.
- The corrected resume terminated in 88.2 seconds on a schema-validity issue.
- Total attributed usage: 1 Modal request and 17 Mistral requests.
- Mistral usage: 105,320 input tokens, 50,622 output tokens, estimated $0.0461712.
- Modal usage: estimated $0.03153024.
- Unpriced charges: 0. Empty project IDs: 0.
- Durable partial output: 11 chapter checkpoints, 85 events, 226 entities, and 77 relationships.
- Raw event scene-reference validity: 82/85 (96.5%).
- Raw entity/relationship scene-reference validity: 327/337 (97.0%). Invalid references would be removed by deterministic materialization, but the stage did not reach final materialization.

## Failure analysis

The initial four-way burst produced SDK failures, and the queue retried after the previously persisted five-second backoff. The corrected three-way run progressed, then chapter 12 omitted `entity_type` for nine otherwise grounded entities. Strict ingress validation rejected the complete chapter payload before deterministic classification could run. Both defects are fixed in code and covered by focused tests.

## Decision

Do not promote RC38 yet. The request fan-out, attribution, persistent budget, checkpointing, retry backoff, and identified schema defect are addressed, but no complete real-book canon result exists. A later bounded qualification must start from the 11 checkpoints, remain at or below 40 total Mistral requests, complete within five minutes of canon execution, and audit final materialized identity/entity/event/relationship evidence before promotion.
