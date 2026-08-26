# Qwen Image Edit 2511 integration

S.A.G.A. Studio treats Qwen Image Edit 2511 as a first-class image-edit ecosystem alongside FLUX.2 Klein and the LTX video ecosystem.

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

The Qwen gateway mirrors the existing asynchronous image-edit contract: health reporting, multi-reference uploads, submit, polling, cancellation, real worker lifecycle states, and failover-compatible availability/credit errors. The fleet remains ecosystem-affine: Qwen jobs are routed only to workers registered under `qwen-image-edit-2511` and never fall back to a FLUX worker.

The primary worker is `qwen-primary-01` on `modal-42`; the standby is `qwen-standby-01` on `modal-43`. Both gateways report the pinned Civitai version and Lightning profile.

## Studio behavior

Image and Edit surfaces expose an explicit FLUX/Qwen model choice. Changing the selected model updates its Advanced defaults. Qwen uses 4 steps and CFG 1.0 by default. Upload, drag/drop, multiple references, progress, Jobs, cancellation, persisted output, and Gallery behavior remain shared with the existing image-edit experience.
