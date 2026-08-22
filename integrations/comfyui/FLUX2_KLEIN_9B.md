# FLUX.2 Klein 9B Studio editor

This integration adds an isolated Modal/ComfyUI image-edit runtime for SAGA Studio.

- Modal app: `saga-flux2-klein-9b`
- Initial target: `modal-01`
- Checkpoint: CivitAI model version `2740209`, file `2626634`
- Runtime checkpoint name: `darkBeast_dbkleinv2BFS.safetensors`
- Text encoder: `qwen_3_8b_fp8mixed.safetensors`
- VAE: `full_encoder_small_decoder.safetensors`
- Default inference: 4 steps, CFG 1.0, Euler sampler
- API workflow: `workflows/flux2_klein_9b_image_edit_api.json`

The CivitAI credential is intentionally not stored in the repository. The downloader supports an optional `CIVITAI_API_TOKEN` runtime environment variable and otherwise uses the public download URL.

The first deployment is deliberately isolated from the legacy `saga-image-runtime` so that the existing SAGA image backend remains unchanged while the Studio editor is validated.
