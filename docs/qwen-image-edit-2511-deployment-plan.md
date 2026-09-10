# Qwen Image Edit 2511 worker deployment gates

Deployment uses the S.A.G.A. Modal fleet contract and a dedicated Qwen ecosystem; it does not reuse FLUX or LTX workers.

1. **Fleet allocation — passed.** `qwen-primary-01` is on `modal-42` and `qwen-standby-01` is on `modal-43`.
2. **Pinned model — passed.** Workers use Civitai model/version/file `2246542` / `2553500` / `2443737`, SHA256 `bbd4901121f4590c82217895faec91d9f496cce924434d776f0b2c8a795ca6a`, at BF16 precision.
3. **Acceleration — passed.** Qwen Image Edit Lightning BF16 is fused before explicit 4×A10 dispatch; default sampling is 4 steps with true CFG 1.0.
4. **Health/registration — passed for the recorded deployment.** Both gateways report `qwen-image-edit-2511`. Current non-secret routing metadata is owned by `config/modal-worker-registry.json`.
5. **Live generation — passed historically.** Run `32913997676` completed real primary and standby edits.
6. **Routing/failover — passed historically.** Run `32916056920` verified ecosystem affinity, both live workers, and standby submit/cancel behavior.
7. **Persistence evidence — historical Studio evidence only.** Run `32917454087` generated a real Qwen image and proved the retired Studio prototype could persist/read it through Cloudflare R2 and Supabase. This does not define current S.A.G.A. product persistence behavior.

The Qwen workflow has no FLUX fallback. If no Qwen fleet is available, S.A.G.A. must report the Qwen provider path as unavailable rather than cross-routing to another ecosystem.

The former `apps/studio/` registry and product integration are retired. Future qualification must use S.A.G.A.-owned runtime/configuration paths and bind evidence to the exact current commit.
