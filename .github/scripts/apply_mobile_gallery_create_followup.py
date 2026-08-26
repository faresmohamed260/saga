from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


def write(path, text):
    (ROOT / path).write_text(text, encoding='utf-8')


def replace_once(path, old, new):
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{path}: expected one exact match, found {count}: {old[:120]!r}')
    write(path, text.replace(old, new, 1))


def regex_once(path, pattern, replacement, flags=0):
    text = read(path)
    next_text, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f'{path}: regex expected one match, found {count}: {pattern[:120]!r}')
    write(path, next_text)


# Gallery sort is a direct toggle, never a select menu.
replace_once(
    'apps/studio/src/features/library/GalleryView.jsx',
    '''          <label className="gallery-sort gallery-inline-select"><ArrowDownUp size={16}/><span className="sr-only">Sort gallery</span><select value={sort} onChange={(event) => onSortChange(event.target.value)} aria-label="Sort gallery"><option value="newest">Newest</option><option value="oldest">Oldest</option></select></label>''',
    '''          <button type="button" className="gallery-sort-toggle" aria-label={`Sort gallery, ${sort === 'newest' ? 'newest first' : 'oldest first'}`} title={`Showing ${sort === 'newest' ? 'newest' : 'oldest'} first`} onClick={() => onSortChange(sort === 'newest' ? 'oldest' : 'newest')}><ArrowDownUp size={16}/><span>{sort === 'newest' ? 'Newest' : 'Oldest'}</span></button>''',
)
replace_once(
    'apps/studio/src/features/library/GalleryView.jsx',
    '''        <label className="gallery-mobile-select"><ArrowDownUp size={19}/><span>Sort</span><select value={sort} onChange={(event) => onSortChange(event.target.value)} aria-label="Mobile sort"><option value="newest">Newest</option><option value="oldest">Oldest</option></select></label>''',
    '''        <button type="button" className="gallery-sort-toggle" aria-label={`Sort gallery, ${sort === 'newest' ? 'newest first' : 'oldest first'}`} onClick={() => onSortChange(sort === 'newest' ? 'oldest' : 'newest')}><ArrowDownUp size={19}/><span>{sort === 'newest' ? 'Newest' : 'Oldest'}</span></button>''',
)

# Uploads sort follows the same toggle behavior.
replace_once(
    'apps/studio/src/features/library/UploadsView.jsx',
    '''          <label><ArrowDownUp size={15}/><span className="sr-only">Sort uploads</span><select aria-label="Sort uploads" value={sort} onChange={(event) => setSort(event.target.value)}><option value="newest">Newest</option><option value="oldest">Oldest</option></select></label>''',
    '''          <button type="button" className="uploads-sort-toggle" aria-label={`Sort uploads, ${sort === 'newest' ? 'newest first' : 'oldest first'}`} onClick={() => setSort((value) => value === 'newest' ? 'oldest' : 'newest')}><ArrowDownUp size={15}/><span>{sort === 'newest' ? 'Newest' : 'Oldest'}</span></button>''',
)
replace_once(
    'apps/studio/src/features/library/UploadsView.jsx',
    '''        <label><ArrowDownUp size={19}/><span>Sort</span><select aria-label="Mobile upload sort" value={sort} onChange={(event) => setSort(event.target.value)}><option value="newest">Newest</option><option value="oldest">Oldest</option></select></label>''',
    '''        <button type="button" className="uploads-sort-toggle" aria-label={`Sort uploads, ${sort === 'newest' ? 'newest first' : 'oldest first'}`} onClick={() => setSort((value) => value === 'newest' ? 'oldest' : 'newest')}><ArrowDownUp size={19}/><span>{sort === 'newest' ? 'Newest' : 'Oldest'}</span></button>''',
)

# Card footer no longer repeats image resolution / megapixel metadata already shown by the badge.
replace_once(
    'apps/studio/src/components/MediaCard.jsx',
    '''  const conciseMeta = [
    item.resolution || (item.kind === 'video' ? 'Video' : 'Image'),
    item.aspectRatio || null,
    item.frameRate ? `${item.frameRate}fps` : null,
  ].filter(Boolean).join(' · ');''',
    '''  const conciseMeta = [
    item.aspectRatio || null,
    item.frameRate ? `${item.frameRate}fps` : null,
  ].filter(Boolean).join(' · ');''',
)
replace_once(
    'apps/studio/src/components/MediaCard.jsx',
    '''          <div className="history-meta">
            <span>{conciseMeta || (item.kind === 'video' ? 'Video' : 'Image')}</span>
          </div>''',
    '''          {conciseMeta && <div className="history-meta"><span>{conciseMeta}</span></div>}''',
)

# Mobile gallery filters must stay inside the viewport and use the full available value column.
path = 'apps/studio/src/gallery-library-redesign.css'
text = read(path)
text = text.replace('.gallery-mobile-controls>button,.gallery-mobile-select{', '.gallery-mobile-controls>button{')
text = text.replace('.gallery-mobile-controls>button:hover,.gallery-mobile-controls>button.active,.gallery-mobile-select:focus-within{', '.gallery-mobile-controls>button:hover,.gallery-mobile-controls>button.active{')
text = re.sub(r'\n\s*\.gallery-mobile-select select\{[^}]+\}', '', text, count=1)
text = text.replace(
    '''  .gallery-mobile-filter-panel{
    display:grid;
    gap:9px;
    margin:0 0 12px;
    padding:12px;''',
    '''  .gallery-mobile-filter-panel{
    display:grid;
    gap:9px;
    margin:0 0 12px;
    padding:12px;
    overflow:hidden;''',
)
text = text.replace(
    '''  .gallery-mobile-filter-panel>label{
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:12px;''',
    '''  .gallery-mobile-filter-panel>label:not(.gallery-mobile-favorite){
    display:grid;
    grid-template-columns:minmax(68px,.72fr) minmax(0,1.28fr);
    align-items:center;
    gap:10px;''',
)
text = text.replace(
    '''  .gallery-mobile-filter-panel select{
    min-width:155px;
    max-width:66%;''',
    '''  .gallery-mobile-filter-panel select{
    width:100%;
    min-width:0;
    max-width:none;''',
)
text = text.replace('  .gallery-mobile-filter-panel .gallery-model-filter select{width:auto;min-width:155px;max-width:66%}', '  .gallery-mobile-filter-panel .gallery-model-filter select{width:100%;min-width:0;max-width:none}')
if 'grid-template-columns:minmax(68px,.72fr) minmax(0,1.28fr)' not in text:
    raise RuntimeError('gallery mobile filter CSS replacement failed')
write(path, text)

# Upload sort button inherits the existing button treatment on desktop/mobile.
path = 'apps/studio/src/uploads-library.css'
text = read(path)
text = text.replace('.uploads-mobile-controls>button,.uploads-mobile-controls>label{', '.uploads-mobile-controls>button{')
text = text.replace('.uploads-mobile-controls>button:hover,.uploads-mobile-controls>button.active,.uploads-mobile-controls>label:focus-within{', '.uploads-mobile-controls>button:hover,.uploads-mobile-controls>button.active{')
text = re.sub(r'\n\s*\.uploads-mobile-controls label select\{[^}]+\}', '', text, count=1)
write(path, text)

# Generation source uploads can be promoted directly into reusable Gallery uploads.
path = 'apps/studio/src/generation-client.js'
text = read(path)
text = text.replace('export async function uploadSourceFile(sourceFile) {', "export async function uploadSourceFile(sourceFile, { purpose = 'generation-source', dimensions = null } = {}) {")
text = text.replace("      purpose: 'generation-source',", '      purpose,')
text = text.replace(
    '''  if (!uploadResponse.ok) throw new Error(`Direct source upload failed (${uploadResponse.status})`);
  return { key: ticket.key, contentType: ticket.contentType || sourceFile.type || 'application/octet-stream', filename: sourceFile.name || 'input.png' };
}''',
    '''  if (!uploadResponse.ok) throw new Error(`Direct source upload failed (${uploadResponse.status})`);
  const uploaded = { key: ticket.key, contentType: ticket.contentType || sourceFile.type || 'application/octet-stream', filename: sourceFile.name || 'input.png' };
  if (purpose !== 'library-upload') return uploaded;

  const completeResponse = await fetch('/api/uploads', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      phase: 'complete',
      key: ticket.key,
      filename: sourceFile.name || 'input.png',
      displayName: String(sourceFile.name || 'input').replace(/\\.[^.]+$/, ''),
      contentType: ticket.contentType || sourceFile.type || 'image/png',
      size: sourceFile.size,
      width: Number(dimensions?.width) || null,
      height: Number(dimensions?.height) || null,
    }),
  });
  if (!completeResponse.ok) throw new Error(await responseError(completeResponse, 'Could not save reusable upload'));
  const completePayload = await completeResponse.json();
  return { ...uploaded, asset: completePayload?.item || null };
}

export function uploadLibraryReference(sourceFile, dimensions = {}) {
  return uploadSourceFile(sourceFile, { purpose: 'library-upload', dimensions });
}''',
)
text = text.replace(
    '''export async function submitImageEdit({ sourceFile, sourceFiles, sourceKey, sourceKeys, prompt, negativePrompt = '', resolution, seed, steps = 4, cfg = 1.0, megapixels = 1.0 }) {''',
    '''export async function submitImageEdit({ sourceFile, sourceFiles, sourceKey, sourceKeys, workflowId = 'flux2-klein-image-edit', prompt, negativePrompt = '', resolution, seed, steps = 4, cfg = 1.0, megapixels = 1.0 }) {''',
)
text = text.replace("      workflowId: 'flux2-klein-image-edit',", '      workflowId,')
text = text.replace(
    '''async function applyEditSizing(input) {
  if (editSizingPreference.mode !== 'manual') return input;''',
    '''async function applyEditSizing(input) {
  if (editSizingPreference.mode !== 'manual') return input;''',
)
text = text.replace(
    '''  return {
    ...input,
    sourceFile: files[0] || input.sourceFile,
    sourceFiles: files.length ? files : input.sourceFiles,
    resolution: `${dimensions.width} × ${dimensions.height} · Manual`,
    megapixels,
  };''',
    '''  return {
    ...input,
    sourceFile: files[0] || input.sourceFile,
    sourceFiles: files.length ? files : input.sourceFiles,
    sourceKey: '',
    sourceKeys: [],
    resolution: `${dimensions.width} × ${dimensions.height} · Manual`,
    megapixels,
  };''',
)
insert_after = '''function manualDimensions(aspect, longEdge) {
  const ratio = parseAspect(aspect);
  const edge = Math.max(512, Math.min(2048, Number(longEdge) || 1024));
  if (ratio >= 1) return { width: round64(edge), height: round64(edge / ratio) };
  return { width: round64(edge * ratio), height: round64(edge) };
}
'''
if insert_after not in text:
    raise RuntimeError('generation-client manualDimensions anchor missing')
text = text.replace(insert_after, insert_after + '''
export async function createTextGenerationSource(aspect = '1:1', resolution = 1080) {
  if (typeof document === 'undefined') throw new Error('Text image generation requires a browser canvas.');
  const dimensions = manualDimensions(aspect, resolution);
  const canvas = document.createElement('canvas');
  canvas.width = dimensions.width;
  canvas.height = dimensions.height;
  const context = canvas.getContext('2d', { alpha: false });
  if (!context) throw new Error('Could not prepare the text-generation canvas.');
  context.fillStyle = '#808080';
  context.fillRect(0, 0, dimensions.width, dimensions.height);
  const blob = await new Promise((resolve, reject) => canvas.toBlob((value) => value ? resolve(value) : reject(new Error('Could not encode the text-generation canvas.')), 'image/webp', 0.9));
  return {
    file: new File([blob], 'saga-text-generation-canvas.webp', { type: 'image/webp', lastModified: Date.now() }),
    width: dimensions.width,
    height: dimensions.height,
    megapixels: Math.max(0.25, Math.min(4, (dimensions.width * dimensions.height) / 1_000_000)),
    detail: `${dimensions.width} × ${dimensions.height} · Text generation`,
  };
}
''', 1)
run_image_anchor = '''export async function runImageEdit(input, options = {}) {
  if (options.onStatus) options.onStatus(editSizingPreference.mode === 'manual' ? 'preparing' : 'uploading');
  const effectiveInput = await applyEditSizing(input);
  if (options.onStatus) options.onStatus('uploading');
  const submitted = await submitImageEdit(effectiveInput);
  if (options.onJob) options.onJob(submitted.job);
  if (options.onWorkerStatus && submitted.worker) options.onWorkerStatus(submitted.worker);
  if (options.onStatus) options.onStatus('running');
  const result = await waitForGeneration(submitted.job.id, options);
  return { job: submitted.job, result };
}
'''
if run_image_anchor not in text:
    raise RuntimeError('generation-client runImageEdit anchor missing')
text = text.replace(run_image_anchor, run_image_anchor + '''
export async function runFluxImageGeneration(input, options = {}) {
  if (options.onStatus) options.onStatus('preparing');
  const source = await createTextGenerationSource(input.aspect, input.imageResolution);
  if (options.onStatus) options.onStatus('uploading');
  const submitted = await submitImageEdit({
    ...input,
    workflowId: 'flux2-klein-image-generate',
    sourceFile: source.file,
    sourceFiles: [source.file],
    resolution: source.detail,
    megapixels: source.megapixels,
  });
  if (options.onJob) options.onJob(submitted.job);
  if (options.onWorkerStatus && submitted.worker) options.onWorkerStatus(submitted.worker);
  if (options.onStatus) options.onStatus('running');
  const result = await waitForGeneration(submitted.job.id, options);
  return { job: submitted.job, result, source };
}
''', 1)
write(path, text)

# Qwen can reuse already-uploaded source keys and use a text-generation workflow id.
path = 'apps/studio/src/features/create/qwen-generation-client.js'
text = read(path)
text = text.replace(
    '''  const files = Array.from(input?.sourceFiles || []).filter(Boolean);
  if (!files.length) throw new Error('At least one reference image is required.');
  if (options.onStatus) options.onStatus('uploading');
  const uploaded = await uploadSourceFiles(files);''',
    '''  const files = Array.from(input?.sourceFiles || []).filter(Boolean);
  const sourceKeys = Array.from(input?.sourceKeys || []).filter(Boolean);
  if (!files.length && !sourceKeys.length) throw new Error('At least one source image is required.');
  if (options.onStatus) options.onStatus('uploading');
  const uploaded = sourceKeys.length
    ? sourceKeys.map((key, index) => ({ key, contentType: files[index]?.type || 'image/png', filename: files[index]?.name || `input-${index + 1}.png` }))
    : await uploadSourceFiles(files);''',
)
text = text.replace("      workflowId: 'qwen-image-edit-2511',", "      workflowId: input.workflowId || 'qwen-image-edit-2511',")
write(path, text)

# Backend workflow registry differentiates text generation from edits while using the same production ecosystems.
path = 'apps/studio/api/_workflows.js'
text = read(path)
flux_anchor = "const workflowRegistry = {\n"
if flux_anchor not in text:
    raise RuntimeError('workflow registry anchor missing')
flux_generate = '''  'flux2-klein-image-generate': {
    id: 'flux2-klein-image-generate',
    kind: 'image',
    mode: 'image',
    model: 'FLUX.2 Klein 9B · DarkBeast V2 BFS',
    provider: 'modal-flux2-klein',
    ecosystem: 'flux2-klein-9b',
    requiresSourceImage: true,
    supportsMultipleReferences: false,
    automaticOutputSize: true,
    outputMimeType: 'image/png',
    defaults: { negativePrompt: '', seed: 42, steps: 4, cfg: 1.0, megapixels: 1.0 },
    limits: { maxSourceBytes: 25 * 1024 * 1024, minMegapixels: 0.25, maxMegapixels: 4.0 },
  },
'''
text = text.replace(flux_anchor, flux_anchor + flux_generate, 1)
qwen_edit_anchor = "  'qwen-image-edit-2511': {\n"
if qwen_edit_anchor not in text:
    raise RuntimeError('qwen workflow anchor missing')
qwen_generate = '''  'qwen-image-generate-2511': {
    id: 'qwen-image-generate-2511',
    kind: 'image',
    mode: 'image',
    model: 'Qwen Image Edit 2511 · Abliterated BF16 + Lightning',
    provider: 'modal-flux2-klein',
    ecosystem: 'qwen-image-edit-2511',
    requiresSourceImage: true,
    supportsMultipleReferences: false,
    automaticOutputSize: true,
    outputMimeType: 'image/png',
    defaults: { negativePrompt: '', seed: 42, steps: 4, cfg: 1.0, megapixels: 1.0 },
    limits: { maxSourceBytes: 25 * 1024 * 1024, minMegapixels: 0.25, maxMegapixels: 4.0, minSteps: 4, maxSteps: 4 },
  },
'''
text = text.replace(qwen_edit_anchor, qwen_generate + qwen_edit_anchor, 1)
write(path, text)

# Controller: prompt-only gate, random-per-generation seed mode, reuse immediate uploads, and text-only image generation.
path = 'apps/studio/src/hooks/useGenerationController.js'
text = read(path)
text = text.replace("import { runImageEdit, runVideoGeneration } from '../generation-client.js';", "import { createTextGenerationSource, runFluxImageGeneration, runImageEdit, runVideoGeneration } from '../generation-client.js';")
text = text.replace(
    '''export default function useGenerationController({ mode, isEdit, prompt, references, seed, steps, cfg, negativePrompt, autoEditInfo, section, setItems, loadGallery, setError, setSection, setJobsFilter }) {''',
    '''export default function useGenerationController({ mode, isEdit, prompt, references, seed, setSeed, randomizeSeed, steps, cfg, negativePrompt, autoEditInfo, aspect, imageResolution, section, setItems, loadGallery, setError, setSection, setJobsFilter }) {''',
)
marker = '''  const generationAbortRef = React.useRef(null);
'''
helper = '''  const generationAbortRef = React.useRef(null);

  const effectiveSeedForGeneration = () => {
    const value = randomizeSeed ? Math.floor(Math.random() * 2147483647) : (Number(seed) || 42);
    if (randomizeSeed) setSeed?.(String(value));
    return value;
  };

  const resolveReferenceKeys = async (selectedReferences) => {
    const resolved = [];
    for (const reference of selectedReferences) {
      if (reference?.sourceKey) {
        resolved.push(reference.sourceKey);
        continue;
      }
      if (reference?.uploadPromise) {
        const result = await reference.uploadPromise;
        if (result?.error) throw result.error;
        if (result?.key) {
          resolved.push(result.key);
          continue;
        }
      }
      resolved.push('');
    }
    return resolved;
  };
'''
if marker not in text:
    raise RuntimeError('controller generationAbort marker missing')
text = text.replace(marker, helper, 1)
text = text.replace('    const effectiveSeed = Number(seed) || 42;', '    const effectiveSeed = effectiveSeedForGeneration();', 1)
text = text.replace(
    '''    const { job, result } = await runner({ sourceFiles: references.map((reference) => reference.file), prompt: prompt.trim(), negativePrompt, resolution: autoEditInfo.detail, seed: effectiveSeed, steps, cfg, megapixels: autoEditInfo.megapixels }, { onStatus: setJobStatus, onWorkerStatus: setWorkerStatus, onJob: setActiveJob, signal: generationAbortRef.current?.signal });''',
    '''    const sourceKeys = await resolveReferenceKeys(references);
    const reusableKeys = sourceKeys.every(Boolean) ? sourceKeys : [];
    const { job, result } = await runner({ sourceFiles: references.map((reference) => reference.file), sourceKeys: reusableKeys, prompt: prompt.trim(), negativePrompt, resolution: autoEditInfo.detail, seed: effectiveSeed, steps, cfg, megapixels: autoEditInfo.megapixels }, { onStatus: setJobStatus, onWorkerStatus: setWorkerStatus, onJob: setActiveJob, signal: generationAbortRef.current?.signal });''',
)
# video effective seed is the second previous occurrence
text = text.replace('    const effectiveSeed = Number(seed) || 42;', '    const effectiveSeed = effectiveSeedForGeneration();', 1)
text = text.replace(
    '''    const sourceFile = references[0]?.file || null;
    setJobStatus(sourceFile ? 'uploading' : 'queued');
    const { job, result } = await runVideoGeneration({ sourceFile, prompt: prompt.trim(), negativePrompt, resolution: videoResolution, durationSeconds: videoDuration, audioEnabled: videoAudio, aspectRatio: videoAspect, frameRate: videoFrameRate, seed: effectiveSeed, steps, cfg }, { onStatus: setJobStatus, onWorkerStatus: setWorkerStatus, onJob: setActiveJob, signal: generationAbortRef.current?.signal });''',
    '''    const sourceFile = references[0]?.file || null;
    const sourceKeys = sourceFile ? await resolveReferenceKeys([references[0]]) : [];
    const sourceKey = sourceKeys[0] || '';
    setJobStatus(sourceFile ? 'uploading' : 'queued');
    const { job, result } = await runVideoGeneration({ sourceFile, sourceKey, prompt: prompt.trim(), negativePrompt, resolution: videoResolution, durationSeconds: videoDuration, audioEnabled: videoAudio, aspectRatio: videoAspect, frameRate: videoFrameRate, seed: effectiveSeed, steps, cfg }, { onStatus: setJobStatus, onWorkerStatus: setWorkerStatus, onJob: setActiveJob, signal: generationAbortRef.current?.signal });''',
)
insert_before_video = '''  const runLtxVideo = async (videoOptions = {}) => {'''
image_fn = '''  const runTextImage = async (generationOptions = {}) => {
    if (!prompt.trim()) throw new Error('Describe the image you want to generate.');
    const effectiveSeed = effectiveSeedForGeneration();
    const imageModel = generationOptions.imageModel || 'flux2-klein-9b';
    const requestedAspect = generationOptions.imageAspect || aspect || '1:1';
    const requestedResolution = Number(generationOptions.imageResolution || imageResolution || 1080);
    setJobStatus('preparing');
    let job;
    let result;
    if (imageModel === 'qwen-image-edit-2511') {
      const source = await createTextGenerationSource(requestedAspect, requestedResolution);
      ({ job, result } = await runQwenImageEdit({
        workflowId: 'qwen-image-generate-2511',
        sourceFiles: [source.file],
        prompt: prompt.trim(),
        negativePrompt,
        resolution: source.detail,
        seed: effectiveSeed,
        steps,
        cfg,
        megapixels: source.megapixels,
      }, { onStatus: setJobStatus, onWorkerStatus: setWorkerStatus, onJob: setActiveJob, signal: generationAbortRef.current?.signal }));
    } else {
      ({ job, result } = await runFluxImageGeneration({
        prompt: prompt.trim(), negativePrompt, seed: effectiveSeed, steps, cfg,
        aspect: requestedAspect, imageResolution: requestedResolution,
      }, { onStatus: setJobStatus, onWorkerStatus: setWorkerStatus, onJob: setActiveJob, signal: generationAbortRef.current?.signal }));
    }
    setJobStatus('completed');
    const modelLabel = imageModel === 'qwen-image-edit-2511'
      ? 'Qwen Image Edit 2511 · Official BF16'
      : 'FLUX.2 Klein 9B · DarkBeast V2 BFS';
    setItems((current) => [{ id: result.generationId || job.id, title: prompt.trim(), url: result.thumbnailUrl || result.mediaUrl, originalUrl: result.mediaUrl, thumbnailUrl: result.thumbnailUrl || null, generated: true, model: modelLabel, resolution: String(requestedResolution), seed: effectiveSeed, kind: 'image', mode: 'image', persisted: true, aspectRatio: requestedAspect }, ...current]);
    if (section === 'Gallery') loadGallery({ append: false });
  };

'''
if insert_before_video not in text:
    raise RuntimeError('controller video anchor missing')
text = text.replace(insert_before_video, image_fn + insert_before_video, 1)
text = text.replace("      else if (mode === 'Image') throw new Error('Original image generation is not connected to a production workflow yet. The new presets are ready for that backend.');", "      else if (mode === 'Image') await runTextImage(generationOptions);")
write(path, text)

# App: immediate reusable uploads, upload status, random seed mode plumbing.
path = 'apps/studio/src/app/App.jsx'
text = read(path)
text = text.replace("import { advancedPresetForMode } from '../features/create/model-presets.js';", "import { advancedPresetForMode } from '../features/create/model-presets.js';\nimport { uploadLibraryReference } from '../generation-client.js';")
text = text.replace("  const [seed, setSeed] = useState('42');", "  const [seed, setSeed] = useState('42');\n  const [randomizeSeed, setRandomizeSeed] = useState(false);")
text = text.replace(
    '''  const { busy, jobStatus, workerStatus, activeJob, cancelBusy, generate, viewActiveJob, cancelActiveJob } = useGenerationController({ mode, isEdit, prompt, references, seed, steps, cfg, negativePrompt, autoEditInfo, section, setItems, loadGallery, setError, setSection, setJobsFilter });''',
    '''  const { busy, jobStatus, workerStatus, activeJob, cancelBusy, generate, viewActiveJob, cancelActiveJob } = useGenerationController({ mode, isEdit, prompt, references, seed, setSeed, randomizeSeed, steps, cfg, negativePrompt, autoEditInfo, aspect, imageResolution, section, setItems, loadGallery, setError, setSection, setJobsFilter });''',
)
old_add = '''  const addReferences = async (files) => {
    const valid = [];
    for (const file of files) {
      if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) { setError('References must be PNG, JPEG, or WebP images.'); continue; }
      if (file.size > 25 * 1024 * 1024) { setError(`${file.name} is larger than 25 MB.`); continue; }
      const dimensions = await imageDimensions(file);
      valid.push({ id: `${Date.now()}-${Math.random().toString(36).slice(2)}`, file, preview: URL.createObjectURL(file), ...dimensions });
    }
    if (valid.length) {
      if (mode === 'Video') {
        const next = valid[0];
        setReferences((current) => {
          current.forEach((reference) => reference.preview && URL.revokeObjectURL(reference.preview));
          return next ? [next] : [];
        });
        if (valid.length > 1) valid.slice(1).forEach((reference) => reference.preview && URL.revokeObjectURL(reference.preview));
      } else {
        setReferences((current) => [...current, ...valid]);
        setCreateMode('Edit');
      }
      setError('');
    }
  };'''
new_add = '''  const addReferences = async (files) => {
    const candidates = mode === 'Video' ? Array.from(files || []).slice(0, 1) : Array.from(files || []);
    const valid = [];
    for (const file of candidates) {
      if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) { setError('References must be PNG, JPEG, or WebP images.'); continue; }
      if (file.size > 25 * 1024 * 1024) { setError(`${file.name} is larger than 25 MB.`); continue; }
      const dimensions = await imageDimensions(file);
      const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
      const uploadPromise = uploadLibraryReference(file, dimensions)
        .then((result) => {
          setReferences((current) => current.map((reference) => reference.id === id ? { ...reference, uploadStatus: 'ready', sourceKey: result.key, uploadId: result.asset?.id || null } : reference));
          return result;
        })
        .catch((uploadError) => {
          setReferences((current) => current.map((reference) => reference.id === id ? { ...reference, uploadStatus: 'error', uploadError: uploadError?.message || 'Upload failed' } : reference));
          return { error: uploadError };
        });
      valid.push({ id, file, preview: URL.createObjectURL(file), ...dimensions, uploadStatus: 'uploading', uploadPromise });
    }
    if (valid.length) {
      if (mode === 'Video') {
        const next = valid[0];
        setReferences((current) => {
          current.forEach((reference) => reference.preview && URL.revokeObjectURL(reference.preview));
          return next ? [next] : [];
        });
      } else {
        setReferences((current) => [...current, ...valid]);
        setCreateMode('Edit');
      }
      setError('');
    }
  };'''
if old_add not in text:
    raise RuntimeError('App addReferences block missing')
text = text.replace(old_add, new_add, 1)
text = text.replace(
    '''      uploadId: asset.id,
      ...dimensions,''',
    '''      uploadId: asset.id,
      sourceKey: asset.key,
      uploadStatus: 'ready',
      uploadPromise: Promise.resolve({ key: asset.key, asset }),
      ...dimensions,''',
)
text = text.replace(
    '''              seed={seed} setSeed={setSeed} steps={steps} setSteps={setSteps} cfg={cfg} setCfg={setCfg} negativePrompt={negativePrompt} setNegativePrompt={setNegativePrompt}''',
    '''              seed={seed} setSeed={setSeed} randomizeSeed={randomizeSeed} setRandomizeSeed={setRandomizeSeed} steps={steps} setSteps={setSteps} cfg={cfg} setCfg={setCfg} negativePrompt={negativePrompt} setNegativePrompt={setNegativePrompt}''',
)
write(path, text)

# Advanced/Create controls: 3D die toggle, draft numeric inputs, no model/workflow duplicate cards, prompt-only submit gate.
path = 'apps/studio/src/create-controls.jsx'
text = read(path)
text = text.replace('ArrowUp, Check, ChevronDown, Clock3, Dice5, Image as ImageIcon, Plus,', 'ArrowUp, Check, ChevronDown, Clock3, Image as ImageIcon, LoaderCircle, Plus,')
ref_thumb = '''            <span className="saga-reference-thumb" style={{ backgroundImage: `url(${reference.preview})` }}>
              <b>{index + 1}</b>
            </span>'''
ref_thumb_new = '''            <span className="saga-reference-thumb" style={{ backgroundImage: `url(${reference.preview})` }}>
              <b>{index + 1}</b>
              {reference.uploadStatus === 'uploading' && <span className="saga-reference-upload-state" title="Uploading reference"><LoaderCircle className="spin" size={18}/></span>}
              {reference.uploadStatus === 'error' && <span className="saga-reference-upload-state error" title={reference.uploadError || 'Upload failed'}><X size={17}/></span>}
            </span>'''
if ref_thumb not in text:
    raise RuntimeError('reference thumb block missing')
text = text.replace(ref_thumb, ref_thumb_new, 1)
range_pattern = r'''function RangeField\(\{ label, help, value, onChange, min, max, step, decimals = 0 \}\) \{[\s\S]*?\n\}\n\nfunction AdvancedSettings'''
range_replacement = '''function RangeField({ label, help, value, onChange, min, max, step, decimals = 0 }) {
  const safe = Number.isFinite(Number(value)) ? Number(value) : min;
  const [draft, setDraft] = useState(String(safe));
  const focusedRef = useRef(false);
  useEffect(() => {
    if (!focusedRef.current) setDraft(String(Number.isFinite(Number(value)) ? Number(value) : min));
  }, [value, min]);
  const commit = () => {
    const parsed = Number(draft);
    const fallback = Number.isFinite(Number(value)) ? Number(value) : min;
    const next = Math.max(min, Math.min(max, Number.isFinite(parsed) && draft.trim() !== '' ? parsed : fallback));
    const rounded = Number(next.toFixed(decimals));
    setDraft(String(rounded));
    onChange(rounded);
  };
  const updateDraft = (raw) => {
    const valid = decimals > 0 ? /^\\d*(?:\\.\\d*)?$/.test(raw) : /^\\d*$/.test(raw);
    if (valid) setDraft(raw);
  };
  const rangeValue = Number.isFinite(Number(draft)) && draft.trim() !== '' ? Math.max(min, Math.min(max, Number(draft))) : safe;
  return (
    <div className="saga-advanced-range">
      <div className="saga-advanced-range-head">
        <div><strong>{label}</strong><small>{help}</small></div>
        <input aria-label={`${label} value`} inputMode={decimals > 0 ? 'decimal' : 'numeric'} type="text" value={draft} onFocus={() => { focusedRef.current = true; }} onChange={(event) => updateDraft(event.target.value)} onBlur={() => { focusedRef.current = false; commit(); }} onKeyDown={(event) => { if (event.key === 'Enter') event.currentTarget.blur(); }} />
      </div>
      <input aria-label={label} type="range" min={min} max={max} step={step} value={rangeValue} onChange={(event) => { const next = Number(event.target.value); setDraft(String(next)); onChange(Number(next.toFixed(decimals))); }} />
      <div className="saga-range-scale"><span>{min}</span><span>{max}</span></div>
    </div>
  );
}

function Dice3DIcon({ size = 17 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M4.5 7.2 11.9 3l7.6 4.3-7.4 4.2L4.5 7.2Z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round"/>
      <path d="m4.5 7.2.1 8.7 7.5 4.2v-8.6L4.5 7.2Z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round"/>
      <path d="m19.5 7.3-.1 8.6-7.3 4.2v-8.6l7.4-4.2Z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round"/>
      <circle cx="9.3" cy="7.2" r="1" fill="currentColor"/><circle cx="14.8" cy="7.3" r="1" fill="currentColor"/>
      <circle cx="8.1" cy="13.3" r="1" fill="currentColor"/><circle cx="8.1" cy="17" r="1" fill="currentColor"/>
      <circle cx="16.1" cy="12.7" r="1" fill="currentColor"/><circle cx="14.2" cy="16.4" r="1" fill="currentColor"/>
    </svg>
  );
}

function AdvancedSettings'''
next_text, count = re.subn(range_pattern, range_replacement, text, count=1)
if count != 1:
    raise RuntimeError(f'RangeField replacement failed: {count}')
text = next_text
text = text.replace(
    '''  open, onClose, anchorRef, mode, imageModel = 'flux2-klein-9b', onImageModelChange = () => {}, imageModelName = 'FLUX', seed, setSeed, steps, setSteps,
  cfg, setCfg, negativePrompt, setNegativePrompt,''',
    '''  open, onClose, anchorRef, mode, imageModel = 'flux2-klein-9b', onImageModelChange = () => {}, imageModelName = 'FLUX', seed, setSeed, randomizeSeed, setRandomizeSeed, steps, setSteps,
  cfg, setCfg, negativePrompt, setNegativePrompt,''',
)
runtime_block = '''            <div className="saga-advanced-runtime" aria-label="Active production model">
              <div><span>MODEL</span><strong>{preset.modelLabel}</strong></div>
              <div><span>WORKFLOW</span><strong>{preset.workflowLabel}</strong></div>
            </div>

'''
if runtime_block not in text:
    raise RuntimeError('advanced runtime duplicate cards block missing')
text = text.replace(runtime_block, '', 1)
seed_old = '''                  <input aria-label="Seed" inputMode="numeric" value={seed} onChange={(event) => setSeed(event.target.value.replace(/[^0-9-]/g, ''))} />
                  <button type="button" aria-label="Random seed" title="Random seed" onClick={() => setSeed(String(Math.floor(Math.random() * 2147483647)))}><Dice5 size={15} /></button>'''
seed_new = '''                  <input aria-label="Seed" inputMode="numeric" value={seed} onChange={(event) => setSeed(event.target.value.replace(/[^0-9-]/g, ''))} />
                  <button type="button" className={`saga-seed-random-toggle ${randomizeSeed ? 'active' : ''}`} aria-label={randomizeSeed ? 'Use fixed seed' : 'Randomize seed every generation'} aria-pressed={Boolean(randomizeSeed)} title={randomizeSeed ? 'Random seed on every generation' : 'Keep this seed fixed'} onClick={() => setRandomizeSeed(!randomizeSeed)}><Dice3DIcon size={17}/></button>'''
if seed_old not in text:
    raise RuntimeError('seed button block missing')
text = text.replace(seed_old, seed_new, 1)
text = text.replace(
    '''  seed, setSeed, steps, setSteps, cfg, setCfg, negativePrompt, setNegativePrompt,''',
    '''  seed, setSeed, randomizeSeed = false, setRandomizeSeed = () => {}, steps, setSteps, cfg, setCfg, negativePrompt, setNegativePrompt,''',
    1,
)
text = text.replace("  const heading = isEdit ? 'Transform your references' : isVideo ? 'Create motion' : 'Create from a reference';", "  const heading = isEdit ? 'Transform your references' : isVideo ? 'Create motion' : 'Create an image';")
text = text.replace("placeholder={isVideo ? 'Describe the scene, motion, and camera movement…' : 'Describe the change you want to make…'}", "placeholder={isVideo ? 'Describe the scene, motion, and camera movement…' : 'Describe the image you want to create…'}")
text = text.replace(" : `Add an image, describe the change, and generate with the live ${imageModelName} edit model.`}", " : `Describe an image and generate it with ${imageModelName}. References are optional.`}")
text = text.replace(
    '''                title={isVideo ? 'Generate video' : references.length ? 'Generate image' : 'Add a reference image to generate'}
                aria-label={isVideo ? 'Generate video' : 'Generate image'}
                onClick={() => onGenerate({ videoResolution, videoDuration, videoAudio })}
                disabled={busy || (!isVideo && references.length === 0)}''',
    '''                title={!prompt.trim() ? 'Enter a prompt to generate' : isVideo ? 'Generate video' : 'Generate image'}
                aria-label={isVideo ? 'Generate video' : 'Generate image'}
                onClick={() => onGenerate({ videoResolution, videoDuration, videoAudio, imageAspect: aspect, imageResolution: Number(imageResolution) })}
                disabled={busy || !prompt.trim()}''',
)
text = text.replace(
    '''          seed={seed}
          setSeed={setSeed}
          steps={steps}''',
    '''          seed={seed}
          setSeed={setSeed}
          randomizeSeed={randomizeSeed}
          setRandomizeSeed={setRandomizeSeed}
          steps={steps}''',
)
# persist random seed preference
text = text.replace("      if (saved.seed != null) setSeed(String(saved.seed));", "      if (saved.seed != null) setSeed(String(saved.seed));\n      if (typeof saved.randomizeSeed === 'boolean') setRandomizeSeed(saved.randomizeSeed);")
text = text.replace('      seed,\n      steps: Number(steps),', '      seed,\n      randomizeSeed,\n      steps: Number(steps),')
text = text.replace('    preferencesReady, mode, isEdit, aspect, imageResolution, seed, steps, cfg, negativePrompt,', '    preferencesReady, mode, isEdit, aspect, imageResolution, seed, randomizeSeed, steps, cfg, negativePrompt,')
write(path, text)

# Create wrapper starts a best-effort worker warmup as soon as a model/mode is selected.
path = 'apps/studio/src/features/create/CreateWorkspace.jsx'
text = read(path)
insert = "const IMAGE_MODEL_STORAGE_KEY = 'saga-studio:image-model:v1';\n"
if insert not in text:
    raise RuntimeError('CreateWorkspace storage anchor missing')
text = text.replace(insert, insert + "const warmedWorkflows = new Set();\n", 1)
warm_effect_anchor = '''  useEffect(() => {
    try { window.localStorage.setItem(IMAGE_MODEL_STORAGE_KEY, imageModel); } catch {}
  }, [imageModel]);
'''
warm_effect = warm_effect_anchor + '''
  useEffect(() => {
    const workflowId = mode === 'Video'
      ? 'ltx25-redgraft-video'
      : imageModel === 'qwen-image-edit-2511' ? 'qwen-image-edit-2511' : 'flux2-klein-image-edit';
    if (warmedWorkflows.has(workflowId)) return;
    warmedWorkflows.add(workflowId);
    fetch('/api/warmup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workflowId }),
      keepalive: true,
    }).catch(() => { warmedWorkflows.delete(workflowId); });
  }, [mode, imageModel]);
'''
if warm_effect_anchor not in text:
    raise RuntimeError('CreateWorkspace image model effect anchor missing')
text = text.replace(warm_effect_anchor, warm_effect, 1)
write(path, text)

# Best-effort Vercel API that asks the selected Modal gateway to wake its GPU runtime.
warmup = '''import { getWorkflow } from './_workflows.js';
import { workersForWorkflow } from './_worker-registry.js';

export const config = { maxDuration: 10 };

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return res.status(405).json({ error: 'Method not allowed' });
  }
  const workflow = getWorkflow(req.body?.workflowId);
  if (!workflow) return res.status(404).json({ error: 'Unknown generation workflow' });
  const worker = workersForWorkflow(workflow)[0];
  if (!worker) return res.status(202).json({ status: 'unavailable', ecosystem: workflow.ecosystem });
  try {
    const response = await fetch(`${worker.gatewayUrl}/warm`, {
      method: 'POST',
      headers: { Accept: 'application/json' },
      signal: AbortSignal.timeout(4500),
    });
    return res.status(202).json({ status: response.ok ? 'waking' : 'requested', ecosystem: workflow.ecosystem, workerId: worker.id });
  } catch {
    return res.status(202).json({ status: 'requested', ecosystem: workflow.ecosystem, workerId: worker.id });
  }
}
'''
write('apps/studio/api/warmup.js', warmup)

# Modal gateways expose a non-blocking warm endpoint. The runtime methods trigger @modal.enter model loading.
path = 'integrations/comfyui/flux2_klein_gateway.py'
text = read(path)
health_block = '''    @api.get("/health")
    async def health():
        return {
            "ready": True,
            "gateway": APP_NAME,
            "runtime_app": RUNTIME_APP_NAME,
            "runtime_class": RUNTIME_CLASS_NAME,
            "async_jobs": True,
            "cancel_jobs": True,
            "multiple_references": True,
            "worker": _state(),
        }
'''
if health_block not in text:
    raise RuntimeError('flux gateway health block missing')
text = text.replace(health_block, health_block + '''
    @api.post("/warm")
    async def warm():
        try:
            worker_cls = modal.Cls.from_name(RUNTIME_APP_NAME, RUNTIME_CLASS_NAME)
            call = worker_cls().status.spawn()
            return {"status": "waking", "call_id": call.object_id, "worker_id": WORKER_ID, "ecosystem": ECOSYSTEM_ID}
        except Exception as exc:  # noqa: BLE001
            status_code, error_code, state, detail = _failure_payload(exc)
            return JSONResponse(status_code=status_code, content={"error": detail, "errorCode": error_code, "workerState": state, "worker_id": WORKER_ID, "ecosystem": ECOSYSTEM_ID})
''', 1)
write(path, text)

path = 'integrations/qwen/qwen_image_edit_2511_app.py'
text = read(path)
edit_anchor = '''    @modal.method()
    def edit(
'''
if edit_anchor not in text:
    raise RuntimeError('qwen runtime edit anchor missing')
text = text.replace(edit_anchor, '''    @modal.method()
    def warm(self) -> dict[str, Any]:
        return {"ready": True, "model": MODEL_REPO, "worker_id": WORKER_ID, "ecosystem": ECOSYSTEM_ID}

''' + edit_anchor, 1)
write(path, text)

path = 'integrations/qwen/qwen_image_edit_2511_gateway.py'
text = read(path)
qwen_health_end = '''            "worker": _state(),
        }

    @api.post("/jobs/edit")'''
if qwen_health_end not in text:
    raise RuntimeError('qwen gateway health end anchor missing')
text = text.replace(qwen_health_end, '''            "worker": _state(),
        }

    @api.post("/warm")
    async def warm():
        try:
            worker_cls = modal.Cls.from_name(RUNTIME_APP_NAME, RUNTIME_CLASS_NAME)
            call = worker_cls().warm.spawn()
            return {"status": "waking", "call_id": call.object_id, "worker_id": WORKER_ID, "ecosystem": ECOSYSTEM_ID}
        except Exception as exc:  # noqa: BLE001
            status_code, error_code, state, detail = _failure_payload(exc)
            return JSONResponse(status_code=status_code, content={"error": detail, "errorCode": error_code, "workerState": state, "worker_id": WORKER_ID, "ecosystem": ECOSYSTEM_ID})

    @api.post("/jobs/edit")''', 1)
write(path, text)

path = 'integrations/comfyui/ltx23_gateway.py'
text = read(path)
runtime_health = '''    @api.get("/runtime-health")
    async def runtime_health():
        try:
            return _worker().health.remote()
        except Exception as exc:  # noqa: BLE001
            status_code, error_code, state, detail = _failure_payload(exc)
            return JSONResponse(status_code=status_code, content={"error": detail, "errorCode": error_code, "workerState": state, "build": GATEWAY_BUILD})
'''
if runtime_health not in text:
    raise RuntimeError('ltx runtime-health block missing')
text = text.replace(runtime_health, runtime_health + '''
    @api.post("/warm")
    async def warm():
        try:
            call = _worker().health.spawn()
            return {"status": "waking", "call_id": call.object_id, "worker_id": WORKER_ID, "ecosystem": ECOSYSTEM_ID}
        except Exception as exc:  # noqa: BLE001
            status_code, error_code, state, detail = _failure_payload(exc)
            return JSONResponse(status_code=status_code, content={"error": detail, "errorCode": error_code, "workerState": state, "worker_id": WORKER_ID, "ecosystem": ECOSYSTEM_ID})
''', 1)
write(path, text)

# Mobile composer: one compact row, rounder controls, plus upload-wheel/seed-toggle states.
path = 'apps/studio/src/create-workspace-v2.css'
text = read(path)
text += '''

/* Mobile follow-up: immediate reference upload feedback + compact one-line composer controls. */
.workspace .saga-reference-thumb{overflow:hidden}
.workspace .saga-reference-upload-state{position:absolute;inset:0;display:grid;place-items:center;border-radius:inherit;background:rgba(8,11,16,.64);color:#f4f5f8;backdrop-filter:blur(2px)}
.workspace .saga-reference-upload-state.error{background:rgba(72,18,28,.72);color:#ffb1bd}
.workspace .saga-seed-random-toggle.active{background:#6e58e8!important;border-color:#9e8eff!important;color:#fff!important;box-shadow:0 0 0 2px rgba(142,118,255,.14),0 6px 18px rgba(72,52,176,.25)}
.workspace .saga-seed-random-toggle svg{filter:drop-shadow(0 1px 0 rgba(0,0,0,.35))}

@media(max-width:720px){
  .workspace .saga-toolbar{align-items:center;gap:4px;padding:0 7px 8px;flex-wrap:nowrap}
  .workspace .saga-toolbar-left{gap:4px;flex-wrap:nowrap;min-width:0}
  .workspace .saga-toolbar-right{gap:4px;flex:0 0 auto;margin-left:auto}
  .workspace .saga-round-button{width:32px;height:32px;flex-basis:32px}
  .workspace .saga-media-toggle{height:32px;padding:2px;flex:0 0 auto}
  .workspace .saga-media-toggle button{height:28px;min-width:27px;padding:0 5px;gap:4px}
  .workspace .saga-media-toggle button.selected{min-width:54px}
  .workspace .saga-media-toggle button svg{width:14px;height:14px}
  .workspace .saga-control-pill,.workspace .saga-auto-toggle{height:30px;min-width:0!important;padding:0 7px;border-radius:999px;gap:4px;font-size:11px}
  .workspace .saga-control-pill svg,.workspace .saga-auto-toggle svg{width:13px;height:13px}
  .workspace .saga-audio-toggle{width:30px;height:30px;flex-basis:30px}
  .workspace .saga-audio-toggle svg{width:15px;height:15px}
  .workspace .saga-submit{width:32px;height:32px;min-width:32px;flex-basis:32px;border-radius:50%}
  .workspace .saga-submit svg{width:19px;height:19px}
}
@media(max-width:390px){
  .workspace .saga-toolbar{gap:3px;padding-left:6px;padding-right:6px}
  .workspace .saga-toolbar-left,.workspace .saga-toolbar-right{gap:3px}
  .workspace .saga-control-pill,.workspace .saga-auto-toggle{padding:0 5px;font-size:10px}
  .workspace .saga-media-toggle button.selected{min-width:49px}
}
'''
write(path, text)

# Contracts and browser assertions now enforce prompt-only generation and the compact mobile geometry.
path = 'apps/studio/scripts/check-generate-action-contract.mjs'
text = read(path)
text = text.replace("requireSource(css, 'width:36px;height:36px;min-width:36px;flex-basis:36px', 'compact mobile submit geometry');", "requireSource(css, 'width:32px;height:32px;min-width:32px;flex-basis:32px', 'compact mobile submit geometry');")
text += "\nrequireSource(controls, 'disabled={busy || !prompt.trim()}', 'prompt-only generation gate across all modes');\nrequireSource(controls, 'saga-reference-upload-state', 'immediate reference upload progress feedback');\n"
write(path, text)

path = 'apps/studio/scripts/check-ui-audit-contract.mjs'
text = read(path)
text = text.replace("expect(controls.includes('<span className=\"saga-submit-label\">Generate</span>') && controls.includes('disabled={busy || (!isVideo && references.length === 0)}'), 'Generate must remain a separate consistent action across Image/Edit/Video');", "expect(controls.includes('<span className=\"saga-submit-label\">Generate</span>') && controls.includes('disabled={busy || !prompt.trim()}'), 'Generate must remain a separate prompt-gated action across Image/Edit/Video');")
text += "\nexpect(!controls.includes('aria-label=\"Active production model\"'), 'Advanced must not duplicate MODEL/WORKFLOW detail cards below model selection');\nexpect(controls.includes('randomizeSeed') && controls.includes('Dice3DIcon'), 'Advanced seed must expose persistent/random per-generation mode');\n"
write(path, text)

path = 'apps/studio/scripts/capture-ui-preview.mjs'
text = read(path)
text = text.replace("  if (!(await imageGenerate.isDisabled())) throw new Error('Image setup Generate must remain disabled until a reference is attached');", "  if (!(await imageGenerate.isDisabled())) throw new Error('Image Generate must remain disabled until a prompt is entered');\n  await desktop.locator('.saga-prompt-shell textarea').fill('A cinematic studio portrait with soft window light');\n  if (await imageGenerate.isDisabled()) throw new Error('Image Generate must enable from prompt text without a reference');\n  await desktop.locator('.saga-prompt-shell textarea').fill('');")
text = text.replace("  await advanced.getByText('FLUX.2 Klein 9B · DarkBeast V2 BFS', { exact: true }).waitFor({ state: 'visible' });", "  if (await advanced.getByText('FLUX.2 Klein 9B · DarkBeast V2 BFS', { exact: true }).count()) throw new Error('Advanced must not repeat the selected model in a separate MODEL card');")
write(path, text)

# Qwen contract allows explicit workflow override for text generation and verifies warm support.
path = 'apps/studio/scripts/check-qwen-integration-contract.mjs'
text = read(path)
text = text.replace("expect(client.includes(\"workflowId: 'qwen-image-edit-2511'\") && client.includes('input.steps ?? 4') && client.includes('input.cfg ?? 1.0'), 'Qwen client must submit the four-step Lightning workflow defaults');", "expect(client.includes(\"input.workflowId || 'qwen-image-edit-2511'\") && client.includes('input.steps ?? 4') && client.includes('input.cfg ?? 1.0'), 'Qwen client must submit edit or text-generation workflow IDs with four-step Lightning defaults');")
text += "\nexpect(workflows.includes(\"'qwen-image-generate-2511'\"), 'Qwen text-generation adapter workflow must be registered');\nexpect(gateway.includes('@api.post(\"/warm\")') && runtime.includes('def warm(self)'), 'Qwen worker must support non-blocking model warmup');\n"
write(path, text)

# Create advanced contract verifies immediate reusable upload and warm API.
path = 'apps/studio/scripts/check-create-advanced-contract.mjs'
text = read(path)
text = text.replace("expect(app.includes(\"setCreateMode('Edit')\"), 'Uploading a reference must apply the FLUX preset when entering Edit');", "expect(app.includes(\"setCreateMode('Edit')\"), 'Uploading a reference must apply the selected image preset when entering Edit');\nexpect(app.includes('uploadLibraryReference') && client.includes(\"purpose: 'library-upload'\"), 'Create references must upload immediately into the reusable Uploads library');")
write(path, text)

print('Applied Studio mobile Gallery/Create follow-up patch.')
