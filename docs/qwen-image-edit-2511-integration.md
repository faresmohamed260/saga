# Qwen Image Edit 2511 integration

S.A.G.A. Studio treats Qwen Image Edit 2511 as a first-class image-edit ecosystem alongside FLUX.2 Klein and the LTX video ecosystem.

## Model

- Official checkpoint: `Qwen/Qwen-Image-Edit-2511`
- Precision: official BF16 weights; no quantized or community checkpoint
- Runtime pipeline: `QwenImageEditPlusPipeline`
- Default inference recipe: 40 steps, true CFG 4.0, guidance scale 1.0
- Production worker profile: A10 with 96 GB host RAM and Diffusers sequential CPU offload
- The offload strategy does not quantize or cast the checkpoint; official BF16 weights remain intact while active modules move to GPU on demand

H100, A100-80GB, and L40S were evaluated first, but the current credit-only Modal accounts require a payment method for those GPU tiers. A10 is the highest production tier the current accounts can allocate, so sequential CPU offload is used to preserve full BF16 precision within the available 24 GB VRAM.

## Runtime contract

The Qwen gateway mirrors the existing asynchronous image-edit contract: health reporting, multi-reference uploads, submit, polling, cancellation, real worker lifecycle states, and failover-compatible availability/credit errors. The fleet remains ecosystem-affine: Qwen jobs are routed only to workers registered under `qwen-image-edit-2511` and never fall back to a FLUX worker.

The primary worker is `qwen-primary-01` on `modal-42`; the standby is `qwen-standby-01` on `modal-43`. Each worker has its own persistent model cache and gateway registration.

## Studio behavior

Image and Edit surfaces expose an explicit FLUX/Qwen model choice. Changing the selected model updates its Advanced defaults. Upload, drag/drop, references, progress, Jobs, cancellation, persisted output, and Gallery behavior remain shared with the existing image-edit experience.
