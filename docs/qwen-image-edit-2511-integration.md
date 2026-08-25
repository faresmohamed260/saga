# Qwen Image Edit 2511 integration

S.A.G.A. Studio treats Qwen Image Edit 2511 as a first-class image-edit ecosystem alongside FLUX.2 Klein and the LTX video ecosystem.

## Model

- Official checkpoint: `Qwen/Qwen-Image-Edit-2511`
- Precision: official BF16 weights; no quantized or community checkpoint
- Runtime pipeline: `QwenImageEditPlusPipeline`
- Default inference recipe: 40 steps, true CFG 4.0, guidance scale 1.0
- Default worker GPU profile: H100, independently configurable through `MODAL_QWEN_IMAGE_EDIT_GPU`

## Runtime contract

The Qwen gateway mirrors the existing asynchronous image-edit contract: health reporting, multi-reference uploads, submit, polling, cancellation, real worker lifecycle states, and failover-compatible availability/credit errors. The fleet remains ecosystem-affine: Qwen jobs are routed only to workers registered under `qwen-image-edit-2511` and never fall back to a FLUX worker.

## Studio behavior

Image and Edit surfaces expose an explicit FLUX/Qwen model choice. Changing the selected model updates its Advanced defaults. Upload, drag/drop, references, progress, Jobs, cancellation, persisted output, and Gallery behavior remain shared with the existing image-edit experience.
