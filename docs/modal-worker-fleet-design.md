# S.A.G.A. Modal Ecosystem Worker Fleet

This document defines S.A.G.A.'s retained Modal worker-fleet contract for visual-generation providers. It is infrastructure for S.A.G.A.'s narrative-to-media pipeline, not a generic image/video product contract.

The former `apps/studio/` product prototype has been retired from S.A.G.A.; its standalone successor is RenderLab. Worker infrastructure remains here only where S.A.G.A. itself consumes or qualifies it.

## Ownership

A **Modal account** is a credentials, quota, and billing boundary. A **worker** is one deployed model ecosystem inside an account.

Machine-readable ownership is split deliberately:

- `config/modal-worker-ecosystems.json` — model ecosystem/runtime definitions;
- `config/modal-worker-registry.json` — non-secret active routing metadata;
- `scripts/modal_worker_fleet.py` — inventory/reset/deploy operations;
- `scripts/modal_worker_maintenance.py` — non-destructive worker maintenance;
- provider implementations under `integrations/comfyui/` and `integrations/qwen/`.

The public registry contains worker IDs, ecosystem IDs, gateway URLs, account labels, role/order, display names, enabled state, and deployment-version labels only. It must never contain credentials.

## Current retained fleet

| Ecosystem | Primary | Standby |
| --- | --- | --- |
| FLUX.2 Klein 9B | `flux-primary-01` (`modal-44`) | `flux-standby-01` (`modal-45`) |
| REDGraft LTX 2.5 | `ltx-primary-01` (`modal-46`) | `ltx-standby-01` (`modal-47`) |
| Qwen Image Edit 2511 | `qwen-primary-01` (`modal-42`) | `qwen-standby-01` (`modal-43`) |

Exact gateway URLs and deployment labels are owned by `config/modal-worker-registry.json` so operational workflows do not depend on an application-specific generated JavaScript file.

## Provisioning contract

A newly assigned dedicated worker account is reconciled before its ecosystem is installed:

1. inventory and confirm the account can execute compute;
2. stop existing apps only when an explicit reprovision operation authorizes destructive reconciliation;
3. delete old Volumes/Dicts only when that same explicit reprovision authorizes it;
4. deploy exactly the intended ecosystem runtime and gateway;
5. prefetch and verify the ecosystem's model assets into its persistent cache Volume;
6. verify the gateway without unnecessarily waking GPU compute;
7. publish non-secret routing metadata as workflow evidence;
8. update `config/modal-worker-registry.json` through normal reviewed repository change when routing metadata changes.

Provisioning workflows must not bot-push generated registry changes directly to protected `main`. They may produce an updated registry artifact for review.

Routine code upgrades do not delete model caches. Destructive cleanup is reserved for explicit reprovision operations.

## Resource policy

Each ecosystem worker should preserve the provider-specific validated runtime policy while generally following:

- scale to zero when idle where supported;
- bounded per-worker concurrency to avoid model-memory thrash;
- an idle scale-down window;
- a persistent Modal Volume for model/checkpoint assets;
- a lightweight Modal Dict for worker lifecycle state.

A cold start should pay container startup plus loading cached weights into RAM/VRAM, not repeated multi-gigabyte model downloads.

Legacy cache directory names that contain `studio` may be retained temporarily when renaming them would invalidate an existing persistent cache. A legacy storage path name does not make the worker a Studio product dependency; any cache-path migration must be explicit and non-destructive.

## Routing and credit exhaustion

Routing is ecosystem-affine. A Qwen request must not silently become a FLUX request, and an LTX request must not silently become another ecosystem merely because a worker is unavailable.

Submission tries enabled workers in primary/standby order. Explicit credit/quota/budget failures and explicit worker-unavailable failures may be eligible for standby routing. The accepted provider job ID must remain pinned to the worker that accepted it.

Safety rules:

- **Before a job is accepted:** retryable credit/unavailable failures may move to another worker.
- **After a job is accepted:** reassignment is allowed only when the provider gives strong evidence that execution did not proceed. Generic network errors, 5xx responses, and rate-limit responses must not duplicate an accepted generation.

If every configured worker for an ecosystem is unavailable or out of credit, the runtime must fail explicitly rather than silently using an unrelated historical gateway.

## Worker states

The backend owns the state machine. Consumer UIs must not invent fake progress percentages.

| State | Meaning |
| --- | --- |
| `queued` | accepted while worker capacity is occupied |
| `waking` | accepted while compute is scaled to zero |
| `loading` | container/model assets are loading |
| `ready` | worker is warm and ready |
| `generating` | model execution is active |
| `finalizing` | output exists and is being packaged/persisted |
| `sleeping` | no GPU container is active |
| `credit_exhausted` | account cannot spend more |
| `unavailable` | explicit provider/workspace unavailability |
| `failed` | terminal generation failure |

## Provider sampling facts retained from the prototype

These are worker/runtime contracts, not Studio UI requirements:

- FLUX.2 Klein image editing: default 4 steps, CFG 1.0.
- Qwen Image Edit 2511: default 4 steps, true CFG 1.0.
- REDGraft LTX 2.5: fixed 11 denoise transitions (8 base + 3 refine), CFG 1.0.

Any change to these values requires provider/runtime validation.

## GitHub Actions policy

Worker operations are remote-capable through GitHub Actions, but live compute operations are intentionally cost/secret gated.

- deterministic repository CI must not require live Modal credentials;
- inventory, maintenance, provisioning, and real generation smoke tests are manual/bounded operational workflows unless a current phase explicitly promotes one to a required gate;
- workflows must use the S.A.G.A. ecosystem/registry files, not `apps/studio/` paths or retired Studio branches;
- workflow artifacts may contain public routing metadata but never credentials.

## Validation gate

For a fleet state to be called validated:

1. ecosystem definitions and registry entries agree;
2. each expected primary/standby pair reports the correct worker ID and ecosystem;
3. gateway health checks succeed without exposing credentials;
4. real generation is exercised when the phase requires live evidence;
5. standby submit/cancel or failover behavior is exercised where required;
6. S.A.G.A.'s stage-7 visual runtime remains independently tested through its package-level tests;
7. evidence is bound to an exact repository/configuration state.

Historical Studio persistence/UI evidence may remain useful as dated evidence, but it does not define the current S.A.G.A. product contract.
