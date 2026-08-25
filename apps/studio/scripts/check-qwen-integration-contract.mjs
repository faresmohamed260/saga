import { readFile } from 'node:fs/promises';

const root = new URL('../', import.meta.url);
const [ecosystemsRaw, workflows, presets, workspace, controller, client, runtime, gateway, registry] = await Promise.all([
  readFile(new URL('../../config/modal-worker-ecosystems.json', root), 'utf8'),
  readFile(new URL('api/_workflows.js', root), 'utf8'),
  readFile(new URL('src/features/create/model-presets.js', root), 'utf8'),
  readFile(new URL('src/features/create/CreateWorkspace.jsx', root), 'utf8'),
  readFile(new URL('src/hooks/useGenerationController.js', root), 'utf8'),
  readFile(new URL('src/features/create/qwen-generation-client.js', root), 'utf8'),
  readFile(new URL('../../integrations/qwen/qwen_image_edit_2511_app.py', root), 'utf8'),
  readFile(new URL('../../integrations/qwen/qwen_image_edit_2511_gateway.py', root), 'utf8'),
  readFile(new URL('api/_worker-registry.js', root), 'utf8'),
]);

function expect(condition, message) { if (!condition) throw new Error(message); }
const ecosystems = JSON.parse(ecosystemsRaw).ecosystems || [];
const qwen = ecosystems.find((item) => item.id === 'qwen-image-edit-2511');
expect(qwen, 'Qwen Image Edit 2511 ecosystem must be registered');
expect(qwen.runtimeEntrypoint === 'integrations/qwen/qwen_image_edit_2511_app.py', 'Qwen runtime entrypoint must be explicit');
expect(qwen.gatewayEntrypoint === 'integrations/qwen/qwen_image_edit_2511_gateway.py', 'Qwen gateway entrypoint must be explicit');
expect(qwen.prefetchFunction === 'prefetch_qwen_image_edit_2511', 'Qwen prefetch function must be declared');
expect(workflows.includes("'qwen-image-edit-2511'") && workflows.includes("ecosystem: 'qwen-image-edit-2511'"), 'Studio workflow registry must expose Qwen');
expect(workflows.includes('steps: 8') && workflows.includes('cfg: 1.0'), 'Qwen workflow must use Lightning 8-step / CFG 1 defaults');
expect(workflows.includes('minSteps: 6') && workflows.includes('maxSteps: 8'), 'Qwen workflow must constrain Lightning sampling to 6-8 steps');
expect(presets.includes("modelLabel: 'Qwen Image Edit 2511 · Official BF16 + Lightning'") && presets.includes("stepsDetail: '8-step BF16 Lightning LoRA'"), 'Qwen UI preset must identify the official BF16 base plus Lightning recipe');
expect(workspace.includes('aria-label="Image model"') && workspace.includes('>FLUX</button>') && workspace.includes('>Qwen</button>'), 'Image/Edit UI must expose FLUX and Qwen model selection');
expect(workspace.includes('setActiveImageModel(nextModel)') && workspace.includes('imageModel,'), 'Selected image model must drive generation and Advanced settings');
expect(controller.includes('runQwenImageEdit') && controller.includes('generationOptions.imageModel'), 'Generation controller must route Qwen explicitly');
expect(client.includes("workflowId: 'qwen-image-edit-2511'") && client.includes('input.steps ?? 8') && client.includes('input.cfg ?? 1.0'), 'Qwen client must submit the Lightning workflow defaults');
expect(runtime.includes('MODEL_REPO = "Qwen/Qwen-Image-Edit-2511"'), 'Qwen worker must use the official repository');
expect(runtime.includes('QwenImageEditPlusPipeline') && runtime.includes('torch_dtype=torch.bfloat16'), 'Qwen worker must load the official BF16 Diffusers pipeline');
expect(runtime.includes('LIGHTNING_REPO = "lightx2v/Qwen-Image-Edit-2511-Lightning"'), 'Qwen worker must use the Qwen 2511 Lightning LoRA repository');
expect(runtime.includes('Qwen-Image-Edit-2511-Lightning-8steps-V1.0-bf16.safetensors'), 'Qwen worker must use the BF16 8-step Lightning adapter');
expect(runtime.includes('load_lora_weights') && runtime.includes('set_adapters("lightning_8step"'), 'Qwen worker must load and activate the Lightning adapter');
expect(!/int8|fp8|gguf/i.test(runtime), 'Qwen runtime must not use a quantized base checkpoint');
expect(runtime.includes('GPU_TYPE = os.environ.get("MODAL_QWEN_IMAGE_EDIT_GPU", "A10:4")'), 'Qwen worker must default to the 4xA10 production tier');
expect(runtime.includes('device_map="balanced"'), 'Qwen full-BF16 worker must shard the pipeline across GPUs');
expect(runtime.includes('LIGHTNING_MIN_STEPS = 6') && runtime.includes('LIGHTNING_MAX_STEPS = 8'), 'Qwen worker must constrain Lightning inference to 6-8 steps');
expect(runtime.includes('true_cfg_scale=LIGHTNING_TRUE_CFG_SCALE') && runtime.includes('guidance_scale=1.0'), 'Qwen worker must use Lightning CFG 1 guidance');
expect(gateway.includes('@api.post("/jobs/edit")') && gateway.includes('@api.get("/jobs/{call_id}")') && gateway.includes('@api.delete("/jobs/{call_id}")'), 'Qwen gateway must preserve async image-edit lifecycle behavior');
expect(gateway.includes('multiple_references') && gateway.includes('WORKER_CREDIT_EXHAUSTED'), 'Qwen gateway must preserve multi-reference and worker-failover behavior');
expect(gateway.includes('"type": "lightning-lora"') && gateway.includes('LIGHTNING_DEFAULT_STEPS = 8'), 'Qwen gateway health must expose Lightning acceleration metadata');
expect(registry.includes('workersForWorkflow'), 'Worker registry routing must remain ecosystem-aware');
console.log('Qwen Image Edit 2511 Lightning integration contract passed.');
