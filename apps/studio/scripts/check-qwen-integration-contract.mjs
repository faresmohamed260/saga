import { readFile } from 'node:fs/promises';

const root = new URL('../', import.meta.url);
const [ecosystemsRaw, workflows, presets, workspace, controls, controller, client, runtime, gateway, registry, civitaiPrefetch] = await Promise.all([
  readFile(new URL('../../config/modal-worker-ecosystems.json', root), 'utf8'),
  readFile(new URL('api/_workflows.js', root), 'utf8'),
  readFile(new URL('src/features/create/model-presets.js', root), 'utf8'),
  readFile(new URL('src/features/create/CreateWorkspace.jsx', root), 'utf8'),
  readFile(new URL('src/create-controls.jsx', root), 'utf8'),
  readFile(new URL('src/hooks/useGenerationController.js', root), 'utf8'),
  readFile(new URL('src/features/create/qwen-generation-client.js', root), 'utf8'),
  readFile(new URL('../../integrations/qwen/qwen_image_edit_2511_app.py', root), 'utf8'),
  readFile(new URL('../../integrations/qwen/qwen_image_edit_2511_gateway.py', root), 'utf8'),
  readFile(new URL('api/_worker-registry.js', root), 'utf8'),
  readFile(new URL('../../integrations/qwen/qwen_civitai_prefetch.py', root), 'utf8'),
]);

function expect(condition, message) { if (!condition) throw new Error(message); }
const ecosystems = JSON.parse(ecosystemsRaw).ecosystems || [];
const qwen = ecosystems.find((item) => item.id === 'qwen-image-edit-2511');
expect(qwen, 'Qwen Image Edit 2511 ecosystem must be registered');
expect(qwen.runtimeEntrypoint === 'integrations/qwen/qwen_image_edit_2511_app.py', 'Qwen runtime entrypoint must be explicit');
expect(qwen.gatewayEntrypoint === 'integrations/qwen/qwen_image_edit_2511_gateway.py', 'Qwen gateway entrypoint must be explicit');
expect(qwen.prefetchFunction === 'prefetch_qwen_image_edit_2511', 'Qwen prefetch function must be declared');
expect(workflows.includes("'qwen-image-edit-2511'") && workflows.includes("ecosystem: 'qwen-image-edit-2511'"), 'Studio workflow registry must expose Qwen');
expect(workflows.includes('steps: 4') && workflows.includes('cfg: 1.0'), 'Qwen workflow must retain the tuned four-step / CFG 1 defaults');
expect(workflows.includes('minSteps: 1') && workflows.includes('maxSteps: 50'), 'Qwen workflow must expose the editable 1–50 inference-step range');
expect(presets.includes("modelLabel: 'Qwen Image Edit 2511 · Abliterated BF16 + Lightning'") && presets.includes('stepsEditable: true') && presets.includes("stepsDetail: '4-step tuned default · editable 1–50'"), 'Qwen UI preset must expose editable steps while retaining the tuned four-step default');
expect(workspace.includes('imageModel={imageModel}') && workspace.includes('onImageModelChange={chooseImageModel}') && controls.includes('label="Image model"') && controls.includes("{ value: 'flux2-klein-9b', label: 'FLUX.2 Klein 9B' }") && controls.includes("{ value: 'qwen-image-edit-2511', label: 'Qwen Image Edit 2511' }"), 'Advanced Image/Edit UI must expose FLUX and Qwen in a model dropdown');
expect(workspace.includes('setActiveImageModel(nextModel)') && workspace.includes('imageModel,'), 'Selected image model must drive generation and Advanced settings');
expect(controller.includes('runQwenImageEdit') && controller.includes('generationOptions.imageModel'), 'Generation controller must route Qwen explicitly');
expect(client.includes("input.workflowId || 'qwen-image-edit-2511'") && client.includes('input.steps ?? 4') && client.includes('input.cfg ?? 1.0'), 'Qwen client must submit user steps with four-step / CFG 1 defaults');
expect(runtime.includes('MODEL_REPO = "Qwen/Qwen-Image-Edit-2511"'), 'Qwen worker must retain the official Qwen 2511 pipeline configuration');
expect(runtime.includes('CIVITAI_VERSION_ID = 2553500') && runtime.includes('CIVITAI_FILE_ID = 2443737') && runtime.includes('qwnImageEdit_v16Bf16.safetensors'), 'Qwen worker must pin the requested Civitai BF16 version and exact file ID');
expect(runtime.includes('CIVITAI_EXPECTED_BYTES = 40861031560'), 'Qwen worker must pin the exact Civitai checkpoint byte size');
expect(runtime.includes('4F8CA1242C7FDBE6CFD1835833C66E9CDBCF23EA27C7B811B43BDA316F30A6DA'), 'Qwen worker must pin the Civitai checkpoint SHA256');
expect(runtime.includes('"fileId": CIVITAI_FILE_ID') && runtime.includes('"token": _civitai_token()'), 'Qwen runtime fallback must use the exact Civitai file route with secret-backed authentication');
expect(runtime.includes('downloaded != CIVITAI_EXPECTED_BYTES') && runtime.includes('actual != expected'), 'Qwen runtime fallback must verify exact size and SHA before accepting the checkpoint');
expect(civitaiPrefetch.includes('CIVITAI_FILE_ID = 2443737') && civitaiPrefetch.includes('CIVITAI_EXPECTED_BYTES = 40861031560'), 'Qwen staging helper must pin the same exact Civitai file and byte size');
expect(civitaiPrefetch.includes('"fileId": CIVITAI_FILE_ID') && civitaiPrefetch.includes('"token": _token_or_raise()'), 'Qwen staging helper must use the exact file-specific authenticated download route');
expect(civitaiPrefetch.includes('downloaded != CIVITAI_EXPECTED_BYTES') && civitaiPrefetch.includes('actual != expected'), 'Qwen staging helper must enforce exact size and SHA before committing the Modal volume');
expect(runtime.includes('QwenImageTransformer2DModel.from_single_file') && runtime.includes('torch_dtype=torch.bfloat16'), 'Qwen worker must load the Civitai BF16 transformer through the Qwen Diffusers pipeline');
expect(runtime.includes('"torch==2.7.1"') && runtime.includes('"torchvision==0.22.1"'), 'Qwen worker image must install the matched PyTorch/Torchvision runtime pair required by QwenImageEditPlusPipeline processors');
expect(runtime.includes('"peft==0.17.1"'), 'Qwen worker image must install the PEFT backend required for Diffusers LoRA loading');
expect(runtime.includes('LIGHTNING_REPO = "lightx2v/Qwen-Image-Edit-2511-Lightning"'), 'Qwen worker must use the Qwen 2511 Lightning LoRA repository');
expect(runtime.includes('Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors'), 'Qwen worker must use the BF16 four-step Lightning adapter as the tuned default acceleration adapter');
expect(runtime.includes('load_lora_weights') && runtime.includes('set_adapters("lightning_4step"'), 'Qwen worker must load and activate the four-step tuned Lightning adapter');
expect(!/int8|fp8|gguf/i.test(runtime), 'Qwen fallback benchmark must not silently use a quantized base checkpoint');
expect(runtime.includes('GPU_TYPE = os.environ.get("MODAL_QWEN_IMAGE_EDIT_GPU", "A10:4")'), 'Qwen worker must default to the four-A10 production tier');
expect(runtime.includes('_dispatch_civitai_pipeline') && runtime.includes('dispatch_model') && runtime.includes('fuse_lora') && runtime.includes('unload_lora_weights'), 'Qwen Civitai worker must fuse Lightning before deterministic four-GPU dispatch');
expect(runtime.includes('LIGHTNING_MIN_STEPS = 1') && runtime.includes('LIGHTNING_MAX_STEPS = 50') && runtime.includes('num_inference_steps=lightning_steps'), 'Qwen worker must honor user-selected inference steps from 1–50');
expect(gateway.includes('LIGHTNING_MIN_STEPS = 1') && gateway.includes('LIGHTNING_MAX_STEPS = 50') && gateway.includes('effective_steps = max(LIGHTNING_MIN_STEPS'), 'Qwen gateway must validate and forward user-selected inference steps');
expect(runtime.includes('CIVITAI_API_TOKEN') && civitaiPrefetch.includes('CIVITAI_API_TOKEN'), 'Qwen worker and staging helper must consume the repository Civitai secret without embedding credentials');
expect(runtime.includes('true_cfg_scale=LIGHTNING_TRUE_CFG_SCALE') && runtime.includes('guidance_scale=1.0'), 'Qwen worker must use Lightning CFG 1 guidance');
expect(gateway.includes('@api.post("/jobs/edit")') && gateway.includes('@api.get("/jobs/{call_id}")') && gateway.includes('@api.delete("/jobs/{call_id}")'), 'Qwen gateway must preserve async image-edit lifecycle behavior');
expect(gateway.includes('multiple_references') && gateway.includes('WORKER_CREDIT_EXHAUSTED'), 'Qwen gateway must preserve multi-reference and worker-failover behavior');
expect(gateway.includes('"source": "civitai"') && gateway.includes('CIVITAI_VERSION_ID = 2553500'), 'Qwen gateway health must identify the pinned fallback checkpoint');
expect(gateway.includes('"type": "lightning-lora"') && gateway.includes('LIGHTNING_DEFAULT_STEPS = 4'), 'Qwen gateway health must expose the Lightning acceleration metadata and tuned four-step default');
expect(registry.includes('workersForWorkflow'), 'Worker registry routing must remain ecosystem-aware');
console.log('Qwen Image Edit 2511 Civitai BF16 fallback integration contract passed.');

expect(workflows.includes("'qwen-image-generate-2511'"), 'Qwen text-generation adapter workflow must be registered');
expect(gateway.includes('@api.post("/warm")') && runtime.includes('def warm(self)'), 'Qwen worker must support non-blocking model warmup');
