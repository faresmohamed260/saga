# Qwen Image Edit 2511 integration

Qwen Image Edit 2511 is retained as a S.A.G.A. visual-generation provider ecosystem. It is not tied to the retired `apps/studio/` product surface.

## Model

- Runtime pipeline: `QwenImageEditPlusPipeline`
- Component skeleton: `Qwen/Qwen-Image-Edit-2511`
- Production checkpoint: Civitai `Qwn-Image-Edit-abliterated`
- Model/version/file IDs: `2246542` / `2553500` / `2443737`
- Checkpoint SHA256: `bbd4901121f4590c82217895faec91d9f496cce924434d776f0b2c8a795ca6a`
- Precision: BF16 (`civitai-bfloat16`)
- Acceleration: Qwen Image Edit Lightning 4-step BF16 LoRA
- Default inference recipe: 4 steps, true CFG 1.0
- Production GPU profile: 4× A10

The runtime loads the Civitai transformer on CPU, assembles the pipeline, loads the Lightning adapter, fuses it into the transformer, unloads the LoRA weights, and only then explicitly dispatches the pipeline. The transformer is split across GPUs 0 and 2, the text encoder uses GPU 1, and the VAE uses GPU 3. This avoids the cross-device CPU/`cuda:1` failure that occurred with the earlier balanced device-map approach.

## Runtime contract

The Qwen gateway implements the asynchronous image-edit contract: health reporting, multi-reference uploads, submit, polling, cancellation, real worker lifecycle states, and failover-compatible availability/credit errors.

The fleet remains ecosystem-affine: Qwen jobs are routed only to workers registered under `qwen-image-edit-2511` and never fall back to a FLUX worker.

Current non-secret worker routing metadata is owned by `config/modal-worker-registry.json`; ecosystem/runtime definitions are owned by `config/modal-worker-ecosystems.json` and the provider implementation under `integrations/qwen/`.

The recorded primary worker is `qwen-primary-01` on `modal-42`; the recorded standby is `qwen-standby-01` on `modal-43`. Both gateways report the pinned Civitai version and Lightning profile in the recorded validated deployment.

## S.A.G.A. consumption boundary

S.A.G.A. may use Qwen through its own stage-7 visual-generation/provider contracts for narrative-driven image creation or editing. Generic image-edit product UI, gallery, job-management, and media-library behavior belong to the separate RenderLab project and must not be reconstructed in S.A.G.A.

Any future direct S.A.G.A. integration should be implemented through the owning visual/provider runtime rather than by restoring the former Studio API or React surface.
