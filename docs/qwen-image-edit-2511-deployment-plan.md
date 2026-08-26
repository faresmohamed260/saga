# Qwen Image Edit 2511 worker deployment gates

Deployment uses the existing S.A.G.A. Modal fleet contract and a dedicated Qwen ecosystem; it does not reuse FLUX or LTX workers.

1. **Fleet allocation — passed.** `qwen-primary-01` is on `modal-42` and `qwen-standby-01` is on `modal-43`.
2. **Pinned model — passed.** Workers use Civitai model/version/file `2246542` / `2553500` / `2443737`, SHA256 `bbd4901121f4590c82217895faec91d9f496cce924434d776f0b2c8a795ca6a`, at BF16 precision.
3. **Acceleration — passed.** Qwen Image Edit Lightning BF16 is fused before explicit 4×A10 dispatch; default sampling is 4 steps with true CFG 1.0.
4. **Health/registration — passed.** Both gateways report `qwen-image-edit-2511` and are registered in `apps/studio/api/_worker-registry.generated.js`.
5. **Live generation — passed.** Run `32913997676` completed real primary and standby edits.
6. **Routing/failover — passed.** Run `32916056920` verified ecosystem affinity, both live workers, and standby submit/cancel behavior.
7. **Persistence — passed.** Run `32917454087` generated a real Qwen image, persisted it through Studio to Cloudflare R2 and Supabase history, and read the stored media back successfully.

A Qwen workflow has no legacy FLUX fallback. If no Qwen fleet is available, Studio reports the Qwen worker path as unavailable rather than cross-routing to another ecosystem.
