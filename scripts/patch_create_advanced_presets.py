from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


def write(path, text):
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding='utf-8')


def replace_once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f'missing replacement target: {label}')
    if text.count(old) != 1:
        raise RuntimeError(f'expected one replacement target for {label}, got {text.count(old)}')
    return text.replace(old, new, 1)


# Canonical UI-side production presets. These mirror api/_workflows.js.
write('apps/studio/src/features/create/model-presets.js', """export const MODEL_ADVANCED_PRESETS = Object.freeze({
  'flux2-klein-9b': Object.freeze({
    modelId: 'flux2-klein-9b',
    modelLabel: 'FLUX.2 Klein 9B · DarkBeast V2 BFS',
    workflowId: 'flux2-klein-image-edit',
    workflowLabel: 'Klein Multi-Reference Edit',
    seed: '42',
    steps: 4,
    cfg: 1.0,
    stepsEditable: true,
    stepsDetail: '4 sampling iterations',
  }),
  'ltx25-redgraft': Object.freeze({
    modelId: 'ltx25-redgraft',
    modelLabel: 'REDGraft LTX 2.5 · Sulphur2 INT8 ConvRot',
    workflowId: 'ltx25-redgraft-video',
    workflowLabel: 'LTX 2.5 two-stage video',
    seed: '42',
    steps: 11,
    cfg: 1.0,
    stepsEditable: false,
    stepsDetail: '11 total · 8 base + 3 refine',
  }),
});

export function advancedPresetForMode(mode) {
  if (mode === 'Edit') return MODEL_ADVANCED_PRESETS['flux2-klein-9b'];
  if (mode === 'Video') return MODEL_ADVANCED_PRESETS['ltx25-redgraft'];
  return null;
}
""")

# Create wrapper: keep video aspect/FPS state, but move their controls into Advanced.
write('apps/studio/src/features/create/CreateWorkspace.jsx', """import React, { useCallback, useEffect, useMemo, useState } from 'react';
import LegacyCreateWorkspace from '../../create-controls.jsx';
import {
  VideoGenerationProgress,
  referenceAspect,
} from './VideoGenerationControls.jsx';

const VIDEO_OUTPUT_STORAGE_KEY = 'saga-studio:video-output:v2';

function loadVideoOutputSettings() {
  if (typeof window === 'undefined') return { autoAspect: true, manualAspect: '16:9', frameRate: 24 };
  try {
    const saved = JSON.parse(window.localStorage.getItem(VIDEO_OUTPUT_STORAGE_KEY) || '{}');
    return {
      autoAspect: saved.autoAspect !== false,
      manualAspect: typeof saved.manualAspect === 'string' ? saved.manualAspect : '16:9',
      frameRate: [24, 25, 30].includes(Number(saved.frameRate)) ? Number(saved.frameRate) : 24,
    };
  } catch {
    return { autoAspect: true, manualAspect: '16:9', frameRate: 24 };
  }
}

export default function CreateWorkspace(props) {
  const { mode, references = [], busy, jobStatus, workerStatus, activeJob, cancelBusy, onGenerate, onViewJob, onCancelJob } = props;
  const initial = useMemo(loadVideoOutputSettings, []);
  const [autoAspect, setAutoAspect] = useState(initial.autoAspect);
  const [manualAspect, setManualAspect] = useState(initial.manualAspect);
  const [frameRate, setFrameRate] = useState(initial.frameRate);
  const referenceInfo = useMemo(() => referenceAspect(references[0]), [references]);
  const effectiveAspect = autoAspect ? referenceInfo.value : manualAspect;

  useEffect(() => {
    try {
      window.localStorage.setItem(VIDEO_OUTPUT_STORAGE_KEY, JSON.stringify({ autoAspect, manualAspect, frameRate }));
    } catch {
      // Storage can be unavailable in hardened browser contexts; controls still work for the session.
    }
  }, [autoAspect, manualAspect, frameRate]);

  const handleGenerate = useCallback((legacyOptions = {}) => onGenerate({
    ...legacyOptions,
    videoAspect: effectiveAspect,
    videoAspectMode: autoAspect ? 'auto' : 'manual',
    videoFrameRate: frameRate,
  }), [onGenerate, effectiveAspect, autoAspect, frameRate]);

  const composerStatusSlot = mode === 'Video' || mode === 'Edit' ? (
    <VideoGenerationProgress
      busy={busy}
      status={jobStatus}
      workerStatus={workerStatus}
      activeJob={activeJob}
      cancelBusy={cancelBusy}
      onViewJob={onViewJob}
      onCancelJob={onCancelJob}
      kind={mode === 'Video' ? 'video' : 'image'}
    />
  ) : null;

  return (
    <LegacyCreateWorkspace
      {...props}
      videoAspect={effectiveAspect}
      videoAutoAspect={autoAspect}
      setVideoAutoAspect={setAutoAspect}
      videoManualAspect={manualAspect}
      setVideoManualAspect={setManualAspect}
      videoReferenceInfo={referenceInfo}
      videoFrameRate={frameRate}
      setVideoFrameRate={setFrameRate}
      onGenerate={handleGenerate}
      composerStatusSlot={composerStatusSlot}
    />
  );
}
""")

# Legacy Create surface: production-aware Advanced panel and no inline video aspect/FPS controls.
path = 'apps/studio/src/create-controls.jsx'
text = read(path)
text = replace_once(
    text,
    "} from './features/create/ResolutionPresets.js';\nimport './create-workspace-v2.css';",
    "} from './features/create/ResolutionPresets.js';\nimport { advancedPresetForMode } from './features/create/model-presets.js';\nimport './create-workspace-v2.css';",
    'create preset import',
)
text = text.replace("const STORAGE_KEY = 'saga-studio:create-settings:v5';", "const STORAGE_KEY = 'saga-studio:create-settings:v6';")

advanced_start = text.index('function AdvancedSettings({')
advanced_end = text.index('\nfunction MediaModeToggle', advanced_start)
new_advanced = r'''function AdvancedSettings({
  open, onClose, anchorRef, mode, outputs, setOutputs, seed, setSeed, steps, setSteps,
  cfg, setCfg, workflowId, setWorkflowId, modelId, setModelId,
  videoAutoAspect, setVideoAutoAspect, videoManualAspect, setVideoManualAspect,
  videoAspect, videoReferenceInfo, videoFrameRate, setVideoFrameRate,
}) {
  const panelRef = useRef(null);
  const position = useAnchoredPosition(open, anchorRef, 450, 690);
  useOutsideDismiss(open, [anchorRef, panelRef], onClose, anchorRef, true);
  if (!open) return null;
  const isEdit = mode === 'Edit';
  const isVideo = mode === 'Video';
  const preset = advancedPresetForMode(mode);

  return (
    <div ref={panelRef} className="saga-advanced-panel" style={position || { visibility: 'hidden' }} role="dialog" aria-label="Advanced settings">
      <header>
        <div>
          <span>GENERATION CONTROLS</span>
          <h2>Advanced</h2>
          <p>{preset ? 'Model-aware defaults with controls that reach the production worker.' : 'Advanced controls appear only for connected production workflows.'}</p>
        </div>
        <button type="button" aria-label="Close advanced settings" onClick={onClose}><X size={17} /></button>
      </header>

      <div className="saga-advanced-body">
        {preset ? (
          <>
            <div className="saga-advanced-runtime" aria-label="Active production model">
              <div><span>MODEL</span><strong>{preset.modelLabel}</strong></div>
              <div><span>WORKFLOW</span><strong>{preset.workflowLabel}</strong></div>
            </div>

            <section className="saga-advanced-card">
              <div className="saga-card-title"><strong>Sampling</strong><small>Defaults are tuned per production model.</small></div>
              <div className="saga-seed-row">
                <div><strong>Seed</strong><small>Reuse a seed to reproduce a result.</small></div>
                <div className="saga-seed-input">
                  <input aria-label="Seed" inputMode="numeric" value={seed} onChange={(event) => setSeed(event.target.value.replace(/[^0-9-]/g, ''))} />
                  <button type="button" aria-label="Random seed" title="Random seed" onClick={() => setSeed(String(Math.floor(Math.random() * 2147483647)))}><Dice5 size={15} /></button>
                </div>
              </div>
              {preset.stepsEditable ? (
                <RangeField label="Steps" help="Sampling iterations" value={steps} onChange={setSteps} min={1} max={50} step={1} />
              ) : (
                <div className="saga-fixed-setting" data-ltx-fixed-steps="11">
                  <div><strong>Steps</strong><small>Fixed distilled two-stage schedule</small></div>
                  <span>11 <small>8 + 3</small></span>
                </div>
              )}
              <RangeField label="CFG" help={isVideo ? 'Distilled default is 1.0' : 'Prompt guidance strength'} value={cfg} onChange={setCfg} min={0} max={20} step={0.1} decimals={1} />
            </section>

            {isVideo && (
              <section className="saga-advanced-card saga-video-advanced-output">
                <div className="saga-card-title"><strong>Video output</strong><small>Canvas and timing controls sent to LTX.</small></div>
                <div className="saga-advanced-control-field">
                  <span>ASPECT RATIO</span>
                  <AspectPicker
                    ariaLabel="Video aspect"
                    triggerPrefix="Aspect"
                    value={videoManualAspect}
                    onValueChange={(value) => {
                      setVideoManualAspect(value);
                      setVideoAutoAspect(false);
                    }}
                    autoSelected={videoAutoAspect}
                    onAutoChoose={() => setVideoAutoAspect(true)}
                    effectiveValue={videoAspect}
                    effectiveRatio={videoReferenceInfo?.ratio || undefined}
                    autoDetail={videoReferenceInfo?.fromReference
                      ? `${videoReferenceInfo.value} · From reference`
                      : '16:9 · Follows reference when attached'}
                    fromReference={videoAutoAspect && Boolean(videoReferenceInfo?.fromReference)}
                  />
                </div>
                <label className="saga-advanced-control-field">
                  <span>FRAME RATE</span>
                  <FancySelect
                    label="Video frame rate"
                    value={videoFrameRate}
                    options={[24, 25, 30].map((fps) => ({ value: fps, label: `${fps} fps` }))}
                    onChange={(value) => setVideoFrameRate(Number(value))}
                  />
                </label>
              </section>
            )}

            <button
              type="button"
              className="saga-reset"
              onClick={() => {
                setSeed(preset.seed);
                setSteps(preset.steps);
                setCfg(preset.cfg);
                setWorkflowId(preset.workflowId);
                setModelId(preset.modelId);
                if (isEdit) setOutputs(1);
                if (isVideo) {
                  setVideoAutoAspect(true);
                  setVideoManualAspect('16:9');
                  setVideoFrameRate(24);
                }
              }}
            >
              <RotateCcw size={16} /> Reset to {isVideo ? 'LTX' : 'FLUX'} defaults
            </button>
          </>
        ) : (
          <section className="saga-advanced-card saga-advanced-unavailable">
            <div className="saga-card-title"><strong>No production image workflow connected</strong></div>
            <p>Original image generation is not live yet, so Studio does not expose sampling controls that would have no backend effect. Add a reference image to use FLUX.2 Klein editing, or switch to Video for LTX.</p>
          </section>
        )}
      </div>
    </div>
  );
}
'''
text = text[:advanced_start] + new_advanced + text[advanced_end:]

text = replace_once(
    text,
    "  videoAspect = '16:9', videoToolbarSlot = null, composerStatusSlot = null,\n}) {",
    "  videoAspect = '16:9', composerStatusSlot = null,\n  videoAutoAspect = true, setVideoAutoAspect = () => {}, videoManualAspect = '16:9', setVideoManualAspect = () => {},\n  videoReferenceInfo = null, videoFrameRate = 24, setVideoFrameRate = () => {},\n}) {",
    'legacy video advanced props',
)
text = text.replace("\n              {isVideo && videoToolbarSlot}\n", "\n")
text = replace_once(
    text,
    "          modelId={modelId}\n          setModelId={setModelId}\n        />",
    "          modelId={modelId}\n          setModelId={setModelId}\n          videoAutoAspect={videoAutoAspect}\n          setVideoAutoAspect={setVideoAutoAspect}\n          videoManualAspect={videoManualAspect}\n          setVideoManualAspect={setVideoManualAspect}\n          videoAspect={videoAspect}\n          videoReferenceInfo={videoReferenceInfo}\n          videoFrameRate={videoFrameRate}\n          setVideoFrameRate={setVideoFrameRate}\n        />",
    'advanced video props',
)
write(path, text)

# Advanced UI styling for static runtime info and moved video controls.
path = 'apps/studio/src/create-workspace-v2.css'
text = read(path)
text += r'''

/* Model-aware Advanced settings */
.workspace .saga-advanced-runtime{
  display:grid;grid-template-columns:1fr 1fr;gap:8px;
}
.workspace .saga-advanced-runtime>div{
  min-width:0;padding:10px 11px;border:1px solid #2b313b;border-radius:11px;background:#12161c;
}
.workspace .saga-advanced-runtime span,
.workspace .saga-advanced-control-field>span{
  display:block;margin-bottom:5px;color:#697587;font-size:9px;font-weight:800;letter-spacing:.09em;
}
.workspace .saga-advanced-runtime strong{
  display:block;color:#e9ebef;font-size:11px;line-height:1.35;white-space:normal;
}
.workspace .saga-fixed-setting{
  display:flex;align-items:center;justify-content:space-between;gap:12px;padding:9px 0;
}
.workspace .saga-fixed-setting>div{display:flex;flex-direction:column;gap:2px}
.workspace .saga-fixed-setting>div strong{font-size:12px;color:#e8eaf0}
.workspace .saga-fixed-setting>div small{font-size:9px;color:#727d8d}
.workspace .saga-fixed-setting>span{
  min-width:88px;padding:7px 9px;border:1px solid #323846;border-radius:9px;background:#171b22;color:#f1efff;font-size:12px;font-weight:800;text-align:center;
}
.workspace .saga-fixed-setting>span small{color:#8c94a2;font-size:9px;font-weight:700}
.workspace .saga-video-advanced-output{overflow:visible}
.workspace .saga-advanced-control-field{display:block;margin-top:10px}
.workspace .saga-advanced-control-field .saga-shared-aspect-root,
.workspace .saga-advanced-control-field .saga-fancy-select{width:100%}
.workspace .saga-advanced-control-field .saga-control-pill,
.workspace .saga-advanced-control-field .saga-fancy-select>button{width:100%;justify-content:space-between}
.workspace .saga-advanced-unavailable p{margin:0;color:#8490a2;font-size:11px;line-height:1.55}
@media(max-width:720px){
  .workspace .saga-advanced-runtime{grid-template-columns:1fr}
}
'''
write(path, text)

# App: production presets on mode changes, and real Favorites instead of remote placeholder faces.
path = 'apps/studio/src/app/App.jsx'
text = read(path)
text = replace_once(
    text,
    "import useMediaActions from '../hooks/useMediaActions.js';",
    "import useMediaActions from '../hooks/useMediaActions.js';\nimport { advancedPresetForMode } from '../features/create/model-presets.js';",
    'App preset import',
)
text = re.sub(r"\nconst samples = \[.*?\n\];\n", "\n", text, count=1, flags=re.S)
text = text.replace("  const [items, setItems] = useState(samples);", "  const [items, setItems] = useState([]);")
text = text.replace("  const [steps, setSteps] = useState(30);", "  const [steps, setSteps] = useState(4);")
text = text.replace("  const [cfg, setCfg] = useState(7);", "  const [cfg, setCfg] = useState(1.0);")
text = text.replace("  const visibleItems = useMemo(() => items.slice(0, mode === 'Edit' ? 4 : outputs), [items, outputs, mode]);\n", "")

library_marker = "  const { favorites, setFavorites, favoriteItems, setFavoriteItems, galleryItems, setGalleryItems, galleryLoading, galleryAppending, galleryError, galleryKind, setGalleryKind, galleryModel, setGalleryModel, gallerySearch, setGallerySearch, gallerySort, setGallerySort, galleryDate, setGalleryDate, galleryFavoritesOnly, setGalleryFavoritesOnly, galleryModels, galleryPage, libraryLoading, libraryError, setLibraryError, collections, setCollections, selectedCollection, setSelectedCollection, collectionItems, setCollectionItems, loadGallery, loadFavorites, loadCollections, loadCollectionItems } = library;\n"
insert = library_marker + """  const visibleItems = useMemo(() => {
    const accepts = (item) => mode === 'Video' ? item?.kind === 'video' : item?.kind !== 'video';
    const sessionItems = items.filter(accepts);
    const seen = new Set(sessionItems.map((item) => String(item.id)));
    const favoriteFallback = favoriteItems.filter((item) => accepts(item) && !seen.has(String(item.id)));
    return [...sessionItems, ...favoriteFallback].slice(0, mode === 'Edit' ? 4 : outputs);
  }, [items, favoriteItems, mode, outputs]);

  const setCreateMode = (nextMode) => {
    setMode(nextMode);
    setError('');
    const preset = advancedPresetForMode(nextMode);
    if (preset) {
      setSeed(preset.seed);
      setSteps(preset.steps);
      setCfg(preset.cfg);
      setWorkflowId(preset.workflowId);
      setModelId(preset.modelId);
      return;
    }
    if (nextMode === 'Image') {
      setWorkflowId('default-image');
      setModelId('saga-image-auto');
    }
  };
"""
text = replace_once(text, library_marker, insert, 'App create favorites and mode presets')

old_upload_modes = """    if (targetMode === 'Video') {
      setMode('Video');
      setWorkflowId('video-planned');
      setModelId('saga-video-auto');
    } else {
      setMode('Edit');
      setWorkflowId('flux2-klein-image-edit');
      setModelId('flux2-klein-9b');
    }
"""
new_upload_modes = """    if (targetMode === 'Video') {
      setCreateMode('Video');
    } else {
      setCreateMode('Edit');
    }
"""
text = replace_once(text, old_upload_modes, new_upload_modes, 'upload reuse production presets')
text = replace_once(
    text,
    "              mode={mode} setMode={(nextMode) => { setMode(nextMode); setError(''); if (nextMode === 'Edit') { setWorkflowId('flux2-klein-image-edit'); setModelId('flux2-klein-9b'); } else if (nextMode === 'Video') { setWorkflowId('video-planned'); setModelId('saga-video-auto'); } else if (nextMode === 'Image') { setWorkflowId('default-image'); setModelId('saga-image-auto'); } }}",
    "              mode={mode} setMode={setCreateMode}",
    'CreateWorkspace mode preset handler',
)
write(path, text)

# Favorites are now Create's live visual fallback, so load/refresh them while Create is visible.
path = 'apps/studio/src/hooks/useLibraryController.js'
text = read(path)
text = text.replace("if (!['Gallery', 'Favorites', 'Collections'].includes(section)) return undefined;", "if (!['Create', 'Gallery', 'Favorites', 'Collections'].includes(section)) return undefined;")
text = replace_once(
    text,
    "        } else if (section === 'Favorites') {\n          await loadFavorites({ silent: !initial });",
    "        } else if (section === 'Create' || section === 'Favorites') {\n          await loadFavorites({ silent: !initial });",
    'Create favorites refresh',
)
write(path, text)

# Video sampling values now travel from Advanced to the API.
path = 'apps/studio/src/hooks/useGenerationController.js'
text = read(path)
text = replace_once(
    text,
    "aspectRatio: videoAspect, frameRate: videoFrameRate, seed: effectiveSeed },",
    "aspectRatio: videoAspect, frameRate: videoFrameRate, seed: effectiveSeed, steps, cfg },",
    'video controller steps cfg',
)
text = replace_once(
    text,
    "frameRate: videoFrameRate }, ...current]);",
    "frameRate: videoFrameRate, steps: Number(steps), cfg: Number(cfg) }, ...current]);",
    'video result metadata steps cfg',
)
write(path, text)

path = 'apps/studio/src/generation-client.js'
text = read(path)
text = replace_once(
    text,
    "  frameRate = 24,\n  seed = 42,\n}) {",
    "  frameRate = 24,\n  seed = 42,\n  steps = 11,\n  cfg = 1.0,\n}) {",
    'video client sampling args',
)
text = replace_once(
    text,
    "      frameRate,\n      seed,\n    }),",
    "      frameRate,\n      seed,\n      steps,\n      cfg,\n    }),",
    'video client body sampling',
)
write(path, text)

# Backend canonical LTX preset is 11 total (8 base + 3 refine), CFG 1.0.
path = 'apps/studio/api/_workflows.js'
text = read(path)
text = replace_once(text, "      steps: 8,\n      cfg: 1.0,", "      steps: 11,\n      cfg: 1.0,", 'LTX workflow defaults')
write(path, text)

path = 'apps/studio/api/_providers.js'
text = read(path)
text = replace_once(
    text,
    "  form.append('seed', String(input.seed));\n  form.append('resolution', input.resolution);",
    "  form.append('seed', String(input.seed));\n  form.append('steps', String(input.steps));\n  form.append('cfg', String(input.cfg));\n  form.append('resolution', input.resolution);",
    'LTX provider form sampling',
)
write(path, text)

# Modal gateway accepts and validates the fixed 11-step recipe + live CFG.
path = 'integrations/comfyui/ltx23_gateway.py'
text = read(path)
text = replace_once(
    text,
    "        seed: int = Form(42),\n        resolution: str = Form(\"480p\"),",
    "        seed: int = Form(42),\n        steps: int = Form(11),\n        cfg: float = Form(1.0),\n        resolution: str = Form(\"480p\"),",
    'LTX gateway form sampling',
)
text = replace_once(
    text,
    "        if resolution not in {\"480p\", \"720p\", \"1080p\", \"2K\", \"4K\"}:",
    "        if int(steps) != 11:\n            raise HTTPException(status_code=400, detail=\"REDGraft LTX uses a fixed 11-step two-stage recipe (8 base + 3 refine)\")\n        if not 0.0 <= float(cfg) <= 20.0:\n            raise HTTPException(status_code=400, detail=\"cfg must be between 0 and 20\")\n        if resolution not in {\"480p\", \"720p\", \"1080p\", \"2K\", \"4K\"}:",
    'LTX gateway sampling validation',
)
text = replace_once(
    text,
    "                seed=int(seed),\n                resolution=resolution,",
    "                seed=int(seed),\n                steps=int(steps),\n                cfg=float(cfg),\n                resolution=resolution,",
    'LTX gateway spawn sampling',
)
text = replace_once(
    text,
    "                \"resolution\": resolution,\n                \"aspect_ratio\": normalized_aspect,",
    "                \"resolution\": resolution,\n                \"steps\": int(steps),\n                \"cfg\": float(cfg),\n                \"aspect_ratio\": normalized_aspect,",
    'LTX gateway response sampling',
)
write(path, text)

# LTX runtime: no separate distill LoRA is introduced; current fixed sigmas are 8+3.
path = 'integrations/comfyui/ltx23_app.py'
text = read(path)
text = replace_once(
    text,
    'DEFAULT_FPS = 24\nFRAME_RATES = {24, 25, 30}',
    'DEFAULT_FPS = 24\nDEFAULT_TOTAL_STEPS = 11\nLOW_STAGE_STEPS = 8\nHIGH_STAGE_STEPS = 3\nFRAME_RATES = {24, 25, 30}',
    'LTX step constants',
)
text = replace_once(
    text,
    "    seed: int,\n    resolution: str,",
    "    seed: int,\n    cfg: float,\n    resolution: str,",
    'LTX workflow cfg signature',
)
text = text.replace('"inputs": {"model": ["1", 0], "positive": ["8", 0], "negative": ["8", 1], "cfg": 1.0}', '"inputs": {"model": ["1", 0], "positive": ["8", 0], "negative": ["8", 1], "cfg": float(cfg)}', 1)
text = text.replace('"inputs": {"model": ["1", 0], "positive": ["19", 0], "negative": ["19", 1], "cfg": 1.0}', '"inputs": {"model": ["1", 0], "positive": ["19", 0], "negative": ["19", 1], "cfg": float(cfg)}', 1)

# Both _generate_impl and public generate receive sampling values.
text = text.replace(
    '        seed: int = 42,\n        resolution: str = "480p",',
    '        seed: int = 42,\n        steps: int = DEFAULT_TOTAL_STEPS,\n        cfg: float = 1.0,\n        resolution: str = "480p",',
)
text = replace_once(
    text,
    "        if resolution not in RESOLUTIONS:\n            raise ValueError(f\"unsupported resolution: {resolution}\")",
    "        if int(steps) != DEFAULT_TOTAL_STEPS:\n            raise ValueError(f\"REDGraft LTX uses {DEFAULT_TOTAL_STEPS} total steps ({LOW_STAGE_STEPS} base + {HIGH_STAGE_STEPS} refine)\")\n        if not 0.0 <= float(cfg) <= 20.0:\n            raise ValueError(\"cfg must be between 0 and 20\")\n        if resolution not in RESOLUTIONS:\n            raise ValueError(f\"unsupported resolution: {resolution}\")",
    'LTX runtime sampling validation',
)
text = replace_once(
    text,
    "            prompt=prompt,\n            seed=int(seed),\n            resolution=resolution,",
    "            prompt=prompt,\n            seed=int(seed),\n            cfg=float(cfg),\n            resolution=resolution,",
    'LTX workflow live cfg',
)
text = replace_once(
    text,
    '                "cfg": 1.0,\n                "sampler": "euler",',
    '                "cfg": 1.0,\n                "steps_total": DEFAULT_TOTAL_STEPS,\n                "stage_1_steps": LOW_STAGE_STEPS,\n                "stage_2_steps": HIGH_STAGE_STEPS,\n                "separate_distill_lora": False,\n                "sampler": "euler",',
    'LTX health recipe sampling metadata',
)
# Public generate forwards the added values into _generate_impl.
text = replace_once(
    text,
    "                seed=seed,\n                resolution=resolution,",
    "                seed=seed,\n                steps=steps,\n                cfg=cfg,\n                resolution=resolution,",
    'LTX public generate sampling forwarding',
)
write(path, text)

# Keep only the circular audio control. Retain the state tooltip and focus ring.
path = 'apps/studio/src/features/create/audio-control.css'
text = read(path)
text = text.replace('  margin-right: 68px;\n', '')
text = re.sub(r"\n\.workspace \.saga-toolbar \.saga-audio-toggle::after \{.*?\n\}\n\n\.workspace \.saga-toolbar \.saga-audio-toggle\[aria-pressed='false'\]::after \{.*?\n\}\n", "\n", text, count=1, flags=re.S)
text = text.replace('    margin-right: 32px;\n', '')
text = re.sub(r"\n  \.workspace \.saga-toolbar \.saga-audio-toggle::after \{.*?\n  \}\n\n  \.workspace \.saga-toolbar \.saga-audio-toggle\[aria-pressed='false'\]::after \{.*?\n  \}\n", "\n", text, count=1, flags=re.S)
write(path, text)

path = 'apps/studio/scripts/check-audio-control-contract.mjs'
text = read(path)
text = re.sub(r"expect\(css\.includes\(\"content: 'Audio On';\"\).*?expect\(css\.includes\(\"content: 'Off';\"\), 'Compact mobile Audio Off text is missing'\);\n", "expect(!css.includes('.saga-audio-toggle::after'), 'Audio control must not render a duplicate text button beside the circular control');\n", text, count=1, flags=re.S)
text = text.replace("console.log('Audio control contract passed: explicit On/Off text, explanatory tooltip copy, aria-pressed state, focus treatment, and compact mobile behavior are wired.');", "console.log('Audio control contract passed: one circular control, explanatory tooltip copy, aria-pressed state, and focus treatment are wired.');")
write(path, text)

# Dedicated end-to-end source contract for the Advanced changes.
write('apps/studio/scripts/check-create-advanced-contract.mjs', r'''import { readFile } from 'node:fs/promises';

const root = new URL('../', import.meta.url);
const [presets, controls, wrapper, app, library, controller, client, workflows, providers, gateway, runtime, audioCss] = await Promise.all([
  readFile(new URL('src/features/create/model-presets.js', root), 'utf8'),
  readFile(new URL('src/create-controls.jsx', root), 'utf8'),
  readFile(new URL('src/features/create/CreateWorkspace.jsx', root), 'utf8'),
  readFile(new URL('src/app/App.jsx', root), 'utf8'),
  readFile(new URL('src/hooks/useLibraryController.js', root), 'utf8'),
  readFile(new URL('src/hooks/useGenerationController.js', root), 'utf8'),
  readFile(new URL('src/generation-client.js', root), 'utf8'),
  readFile(new URL('api/_workflows.js', root), 'utf8'),
  readFile(new URL('api/_providers.js', root), 'utf8'),
  readFile(new URL('../../integrations/comfyui/ltx23_gateway.py', root), 'utf8'),
  readFile(new URL('../../integrations/comfyui/ltx23_app.py', root), 'utf8'),
  readFile(new URL('src/features/create/audio-control.css', root), 'utf8'),
]);

function expect(condition, message) {
  if (!condition) throw new Error(message);
}

expect(/'flux2-klein-9b'[\s\S]*?steps:\s*4[\s\S]*?cfg:\s*1\.0/.test(presets), 'FLUX preset must be 4 steps / CFG 1.0');
expect(/'ltx25-redgraft'[\s\S]*?steps:\s*11[\s\S]*?cfg:\s*1\.0/.test(presets), 'LTX preset must be 11 total steps / CFG 1.0');
expect(controls.includes('data-ltx-fixed-steps="11"'), 'LTX fixed 8+3 step recipe must be explicit in Advanced');
expect(controls.includes('ariaLabel="Video aspect"'), 'Video aspect must live in Advanced');
expect(controls.includes('label="Video frame rate"'), 'Video frame rate must live in Advanced');
expect(!controls.includes('{isVideo && videoToolbarSlot}'), 'Video aspect/FPS must not remain in the prompt toolbar');
expect(!wrapper.includes('<VideoOutputControls'), 'Wrapper must not inject duplicate inline video output controls');
expect(controller.includes('seed: effectiveSeed, steps, cfg'), 'Video controller must forward steps and CFG');
expect(client.includes('steps = 11') && client.includes('cfg = 1.0'), 'Video client defaults must mirror LTX preset');
expect(/frameRate,[\s\S]*?seed,[\s\S]*?steps,[\s\S]*?cfg/.test(client), 'Video request body must include steps and CFG');
expect(/'ltx25-redgraft-video'[\s\S]*?steps:\s*11,[\s\S]*?cfg:\s*1\.0/.test(workflows), 'Backend LTX defaults must be 11 / 1.0');
expect(providers.includes("form.append('steps', String(input.steps))") && providers.includes("form.append('cfg', String(input.cfg))"), 'Provider must forward LTX sampling values');
expect(gateway.includes('steps: int = Form(11)') && gateway.includes('cfg: float = Form(1.0)'), 'LTX gateway must accept sampling values');
expect(runtime.includes('DEFAULT_TOTAL_STEPS = 11') && runtime.includes('LOW_STAGE_STEPS = 8') && runtime.includes('HIGH_STAGE_STEPS = 3'), 'LTX runtime must describe the fixed 8+3 recipe');
expect(runtime.match(/"cfg": float\(cfg\)/g)?.length === 2, 'LTX CFG must drive both stage guiders');
expect(runtime.includes('"separate_distill_lora": False'), 'LTX health contract must state that no separate distill LoRA is loaded');
expect(!app.includes('const samples = ['), 'Create must not ship stock face/scene placeholders');
expect(app.includes('favoriteItems.filter'), 'Create output wall must draw from Favorites');
expect(library.includes("['Create', 'Gallery', 'Favorites', 'Collections']"), 'Favorites must refresh while Create is visible');
expect(!audioCss.includes('.saga-audio-toggle::after'), 'Audio must render only the circular button');

console.log('Create Advanced contract passed: production presets, live LTX CFG transport, fixed 8+3 recipe, moved video controls, single audio button, and Favorites-backed Create wall are wired.');
''')

path = 'apps/studio/package.json'
text = read(path)
text = replace_once(
    text,
    'node scripts/check-audio-control-contract.mjs && node scripts/check-generation-lifecycle-contract.mjs',
    'node scripts/check-audio-control-contract.mjs && node scripts/check-create-advanced-contract.mjs && node scripts/check-generation-lifecycle-contract.mjs',
    'Advanced contract build gate',
)
write(path, text)

print('Create Advanced preset patch applied successfully.')
