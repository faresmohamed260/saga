# S.A.G.A. v2 Modal Project Isolation Contract

Status: **Planning gate / implementation pending**  
Tracker: #218  
Planning baseline: `10a959dc17296a3f01c78309d4638ffea479e0e9`

## Goal

Make S.A.G.A.'s Modal ownership explicit and enforceable so historical v1 fleet tooling cannot mutate the Modal credentials/workspaces now owned by RenderLab during parallel development.

This is a bounded cross-cutting infrastructure/governance corrective. It does not adopt Modal as the S.A.G.A. v2 textual-analysis runtime and does not reopen D-027: v2 narrative/text analysis remains local-first/CPU-first and Modal remains reserved for future image/media workloads.

## Verified starting state

S.A.G.A. currently has an omnibus `SAGA_MODAL_TOKENS_JSON` roster containing 47 account credentials. Historical but runnable workflow and script surfaces can select entries from that roster and export them as `MODAL_TOKEN_ID` / `MODAL_TOKEN_SECRET`.

Read-only Modal metadata audits on 2026-09-13 proved that the currently RenderLab-dependent media fleet occupies the following account labels:

- `modal-01` — recovered RenderLab LTX primary (`https://faresmohamed260--saga-ltx25-gateway-web.modal.run`);
- `modal-02` — recovered RenderLab LTX standby (`https://bplay2086--saga-ltx25-gateway-web.modal.run`);
- `modal-42` / `modal-43` — Qwen primary/standby consumed by RenderLab;
- `modal-44` / `modal-45` — FLUX historical primary / active standby consumed by RenderLab;
- `modal-46` / `modal-47` — historical LTX identities retained by RenderLab for durable job reconciliation;
- `modal-45` additionally hosts the RenderLab-owned `renderlab-image-upscale` app.

Current S.A.G.A. files still capable of mutating some of those accounts include `scripts/modal_worker_fleet.py`, `scripts/modal_worker_maintenance.py`, `.github/workflows/modal-worker-maintenance.yml`, `.github/workflows/modal-worker-provision.yml`, `.github/workflows/deploy-flux2-klein-modal01.yml`, and `.github/workflows/deploy-flux2-klein-gateway.yml`.

This is a real project-boundary defect even though those surfaces are historical to v2.

## Ownership decision

### S.A.G.A.-owned Modal accounts

`modal-03` through `modal-41` inclusive.

Only S.A.G.A. infrastructure operations may deploy, stop, reset, prefetch, rename, replace, or otherwise mutate resources in those accounts unless the owner explicitly changes the allocation in both repositories.

### RenderLab-owned Modal accounts

`modal-01`, `modal-02`, `modal-42`, `modal-43`, `modal-44`, `modal-45`, `modal-46`, `modal-47`.

S.A.G.A. mutation tooling must reject those accounts even if their credentials remain physically present in an omnibus repository secret.

Possession of a credential is not authorization to use it.

## Required implementation

1. Add a checked-in S.A.G.A. Modal ownership manifest containing `modal-03`–`modal-41` and no credentials.
2. Centralize ownership validation in the existing Modal account loader so every mutable helper fails closed before exporting Modal credentials for a non-S.A.G.A. account.
3. Ensure `reset`, `deploy`, maintenance and any future Modal mutation path use that centralized guard.
4. Retire, remove, or explicitly fail-close historical mutable workflows whose hard-coded targets are RenderLab-owned (`modal-01`, `modal-42`–`modal-47`). Git history remains the historical record; runnable workflow-dispatch surfaces must not remain an accidental control plane for RenderLab.
5. Scope the ordinary Modal inventory workflow to S.A.G.A.-owned accounts and its expected count to 39. A cross-project inventory, if ever needed, must be a separately authorized read-only audit rather than the default S.A.G.A. operation.
6. Audit historical live-smoke/qualification workflows that call the RenderLab-owned public worker fleet without credentials. Disable or remove any workflow that would spend against or mutate RenderLab-owned media capacity as part of ordinary S.A.G.A. development.
7. Add static/CI verification that rejects hard-coded RenderLab-owned account labels in active S.A.G.A. mutation workflows and verifies the central ownership guard cannot select them from a 47-entry roster.
8. Record the allocation as a durable v2 decision in `docs/DECISIONS.md`, reference it from relevant project/governance documentation, and add an explicit AI/session rule in `AGENTS.md`.
9. Do not deploy, stop, reset, or prefetch any Modal resource merely to implement this isolation boundary.

## Reciprocal RenderLab dependency

RenderLab must independently merge the inverse ownership manifest/guard for `modal-01`, `modal-02`, and `modal-42`–`modal-47` and document those accounts as RenderLab-owned.

Isolation is complete only after both repositories enforce reciprocal, non-overlapping account sets.

## Credential policy and hard isolation

No raw Modal token ID or token secret may be committed, logged, placed in an artifact, issue, or documentation.

The repository-level guard is designed to remain safe even while `SAGA_MODAL_TOKENS_JSON` temporarily contains all 47 credentials. It prevents accidental/project-policy-invalid selection by normal scripts and workflows.

It does not provide cryptographic isolation from a maintainer who can both edit workflow code and access an omnibus secret. The strongest follow-up state is to replace the omnibus secret with S.A.G.A.-scoped secret material containing only `modal-03`–`modal-41` (or an equivalently scoped GitHub Environment). Secret-value mutation is an owner/operations action and is not implied complete by repository guards.

## Validation matrix

Implementation acceptance requires:

- ownership-manifest tests proving all and only `modal-03`–`modal-41` are accepted;
- negative tests proving `modal-01`, `modal-02`, and `modal-42`–`modal-47` are rejected even when present in the input roster;
- tests proving mutable commands cannot construct a Modal environment for a rejected account;
- repository scan proving active mutation workflows contain no RenderLab-owned account targets or bypass path;
- audit of public-gateway live-smoke workflows so ordinary S.A.G.A. CI cannot consume RenderLab-owned media capacity;
- standard S.A.G.A. v2 CI remains green;
- reciprocal RenderLab guard merged and verified;
- no credential value exposed.

## Out of scope

- rotating/revoking Modal credentials;
- editing GitHub secret values;
- moving/deploying/redeploying existing Modal apps;
- changing S.A.G.A. v2 textual-analysis architecture;
- adopting RenderLab workers as S.A.G.A. v2 media infrastructure;
- changing RenderLab worker routing or application code;
- deleting historical Git evidence.

## Exit criteria

This corrective is complete only when:

1. S.A.G.A.'s manifest, central guard, workflow retirement/blocking, CI verification and authoritative docs are merged and verified;
2. reciprocal RenderLab isolation is merged and verified;
3. active S.A.G.A. code cannot accidentally select or mutate RenderLab-owned Modal accounts through the shared roster;
4. ordinary S.A.G.A. CI no longer consumes RenderLab-owned generation capacity;
5. any remaining secret-store split is explicitly tracked as an operational hardening follow-up;
6. no Modal resource was mutated in order to establish the boundary.