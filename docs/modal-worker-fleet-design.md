# SAGA Modal Ecosystem Worker Fleet

This document is the product and runtime contract for SAGA's Modal worker fleet. It exists so worker orchestration and user-facing lifecycle feedback are implemented from one deliberate design rather than as unrelated loading indicators.

## Architecture

A **Modal account is a credentials, quota, and billing boundary**. A **worker is one deployed model ecosystem inside an account**. Studio routes generation by ecosystem, never by account label.

Current fleet-v1 assignment:

| Ecosystem | Primary | Standby |
| --- | --- | --- |
| FLUX.2 Klein 9B | `flux-primary-01` | `flux-standby-01` |
| REDGraft LTX 2.5 | `ltx-primary-01` | `ltx-standby-01` |

The account labels backing those workers are operational metadata and must never be exposed with credentials. The generated server-side registry contains worker IDs, ecosystem IDs, gateway URLs, role/order, and display names only.

## Provisioning contract

A newly assigned worker account is reconciled from a clean state before its ecosystem is installed:

1. inventory and confirm the account can execute compute;
2. stop every app returned by Modal's app inventory (running, deployed, or recently stopped);
3. delete all named Volumes and worker-state Dicts in that dedicated account;
4. deploy exactly one ecosystem runtime and its gateway;
5. prefetch and verify the ecosystem's model assets into its persistent cache Volume;
6. verify the gateway without invoking the GPU worker;
7. publish only non-secret routing metadata to Studio.

The account is dedicated after assignment. Routine code upgrades do not delete its model cache; destructive cleanup is reserved for initial assignment or an explicit reprovision operation.

## Resource policy

Each ecosystem worker has:

- `min_containers = 0` so GPU compute scales to zero;
- `max_containers = 1` and `max_inputs = 1` so one worker does not thrash GPU memory between concurrent model loads;
- an idle scale-down window;
- a persistent Modal Volume for model/checkpoint assets;
- a lightweight Modal Dict for worker lifecycle state.

A cold start should therefore pay container startup plus loading cached weights into RAM/VRAM, not repeated multi-gigabyte model downloads.

## Job routing and credit exhaustion

Submission tries workers in primary/standby order. Explicit credit/quota/budget failures and explicit worker-unavailable failures are eligible for standby routing. The accepted provider job ID is pinned to the worker that accepted it.

Credit handling has two separate safety rules:

- **Before a job is accepted:** retryable credit/unavailable failures may move to another worker immediately.
- **After a job is accepted:** reassignment is allowed only when the provider gives strong evidence that execution did not proceed (`credit_exhausted` or an explicit safe unavailable state). Generic network errors, 5xx responses, and rate-limit responses must not duplicate an accepted generation.

If every configured worker for an ecosystem is out of credit, Studio returns `ALL_WORKERS_CREDIT_EXHAUSTED`; it must not fall back to the historical `modal-01` gateway or spin indefinitely.

## Real worker states

The backend owns the state machine. The UI does not invent percentages or fake stages.

| State | Meaning | User-facing intent |
| --- | --- | --- |
| `queued` | accepted while the ecosystem worker is occupied | “Waiting for worker” |
| `waking` | a job was accepted while compute was scaled to zero | “Starting worker” |
| `loading` | container is starting and cached ecosystem assets are loading | “Loading model” |
| `ready` | worker is warm and ready | “Worker ready” |
| `generating` | model execution is active | “Generating image/video” |
| `finalizing` | model output exists and is being packaged/persisted | “Finalizing result” |
| `sleeping` | no GPU container is active | shown as idle status only; an accepted job converts this to `waking` |
| `credit_exhausted` | worker/account cannot spend more | switch to standby when one exists; otherwise explicit terminal error |
| `unavailable` | explicit provider/workspace unavailability | switch to standby when safe |
| `failed` | terminal generation failure | explicit failure state |

## Production UI contract

The Create composer uses one compact lifecycle surface beneath the controls. It contains:

- an explicit state title;
- an ecosystem/worker name when known;
- elapsed time while work is active;
- an indeterminate activity track for real but non-quantified work;
- explicit copy when a standby is being selected because the previous worker exhausted credits or became unavailable;
- an explicit terminal “workers out of credits” message if no worker in that ecosystem can run the request.

The surface is text-first and therefore does not rely on color alone. Settings may still be changed during a running job, but broader “changes apply to the next generation” behavior remains checklist Item 12 and is not part of this blocker.

## Validation gate

This blocker is complete only after all of the following are true:

1. all 47 configured Modal accounts are inventoried without exposing credentials;
2. credit-exhausted accounts are detected and excluded from assignment;
3. primary + standby workers for both current ecosystems are cleanly provisioned;
4. generated Studio worker registry contains the four provisioned workers and no credentials;
5. deterministic routing tests cover credit exhaustion, unavailable workers, worker pinning, no legacy fallback, and safe poll-time reassignment;
6. real FLUX and LTX generations succeed through the worker-aware Studio provider path;
7. generated outputs pass delivery checks and Studio R2/Supabase persistence smoke;
8. a controlled primary-credit failure proves standby routing without deliberately exhausting a real account;
9. gateway health checks do not wake GPU compute and workers return to sleeping after their idle windows;
10. desktop/mobile lifecycle screenshots are inspected professionally.

Only after this gate passes may the normal UI polish checklist resume at Item 12.
