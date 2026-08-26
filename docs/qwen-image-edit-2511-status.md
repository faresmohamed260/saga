# Qwen Image Edit 2511 status

Deployment readiness: **passed** for PR #127.

## Production model

- Ecosystem: `qwen-image-edit-2511`
- Runtime: `QwenImageEditPlusPipeline`
- Checkpoint source: Civitai, model `Qwn-Image-Edit-abliterated`
- Civitai model ID: `2246542`
- Civitai version ID: `2553500`
- Civitai file ID: `2443737`
- Pinned SHA256: `bbd4901121f4590c82217895faec91d9f496cce924434d776f0b2c8a795ca6a`
- Precision: BF16 (`civitai-bfloat16`)
- Acceleration: Qwen Image Edit Lightning BF16 LoRA, fused before device dispatch
- Default sampling: 4 steps, true CFG `1.0`
- GPU profile: 4× A10 with explicit transformer/text-encoder/VAE sharding

The explicit sharding replaced the earlier balanced device-map path that could leave tensors split between CPU and `cuda:1`. Lightning is fused and unloaded before the pipeline is dispatched across the four GPUs.

## Fleet

- Primary: `qwen-primary-01` (`modal-42`)
- Standby: `qwen-standby-01` (`modal-43`)
- Provision run: `32913577794`
- Both workers are registered under the Qwen ecosystem only; there is no FLUX fallback.

## Release evidence

- Live inference smoke: run `32913997676` — primary and standby both completed real Qwen edits with the pinned Civitai checkpoint and 4-step Lightning profile.
- Fleet/failover gate: run `32916056920` — static routing contract, both live worker health checks, and a direct standby submit/cancel all passed.
- Live Studio persistence proof: run `32917454087`, job `98024036360` — `qwen-primary-01` generated a valid 108,238-byte PNG, Studio persisted it to Cloudflare R2, inserted generation history, and read the persisted media back successfully. Generation ID: `dd197cc8-2541-467b-aeb2-fb2745237841`.
- Studio build/contracts verify the Qwen workflow, model selector, pinned runtime metadata, worker registry, persistence hooks, and Gallery/Jobs integration.

The Vercel branch preview is protected by Vercel Authentication, so unauthenticated GitHub Actions cannot POST through the preview API. That protection was not weakened for testing. The live worker path and the production R2/Supabase persistence layer were instead verified independently, while the branch Studio API wiring is covered by its build and integration contracts.
