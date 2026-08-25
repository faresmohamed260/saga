# Qwen Image Edit 2511 worker deployment gates

Deployment uses the existing S.A.G.A. Modal fleet contract and does not reuse FLUX or LTX accounts.

1. Inventory the configured Modal roster and select two accounts that pass the compute probe.
2. Deploy `qwen-primary-01` and `qwen-standby-01` as separate ecosystem workers.
3. Prefetch the official `Qwen/Qwen-Image-Edit-2511` checkpoint into each worker's persistent cache volume before registering it.
4. Verify each gateway `/health` response reports `qwen-image-edit-2511`, `official-bfloat16`, and the assigned worker id.
5. Register only verified gateway URLs in `apps/studio/api/_worker-registry.generated.js`.
6. Run a real end-to-end Qwen edit through Studio, including persisted output and Gallery visibility, before merge.

A Qwen workflow has no legacy FLUX fallback. If no Qwen fleet is registered, Studio must report the worker as unavailable rather than cross-routing to another ecosystem.
