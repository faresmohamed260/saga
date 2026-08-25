import React, { useCallback, useEffect, useMemo, useState } from 'react';
import LegacyCreateWorkspace from '../../create-controls.jsx';
import {
  VideoGenerationProgress,
  referenceAspect,
} from './VideoGenerationControls.jsx';
import { MODEL_ADVANCED_PRESETS, setActiveImageModel } from './model-presets.js';
import './create-advanced-mobile.css';
import './image-model-selector.css';

const VIDEO_OUTPUT_STORAGE_KEY = 'saga-studio:video-output:v2';
const IMAGE_MODEL_STORAGE_KEY = 'saga-studio:image-model:v1';

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

function loadImageModel() {
  if (typeof window === 'undefined') return 'flux2-klein-9b';
  try {
    const saved = window.localStorage.getItem(IMAGE_MODEL_STORAGE_KEY);
    return saved === 'qwen-image-edit-2511' ? saved : 'flux2-klein-9b';
  } catch {
    return 'flux2-klein-9b';
  }
}

export default function CreateWorkspace(props) {
  const { mode, references = [], busy, jobStatus, workerStatus, activeJob, cancelBusy, onGenerate, onViewJob, onCancelJob, setSteps, setCfg, setNegativePrompt } = props;
  const initial = useMemo(loadVideoOutputSettings, []);
  const [autoAspect, setAutoAspect] = useState(initial.autoAspect);
  const [manualAspect, setManualAspect] = useState(initial.manualAspect);
  const [frameRate, setFrameRate] = useState(initial.frameRate);
  const [imageModel, setImageModel] = useState(loadImageModel);
  const referenceInfo = useMemo(() => referenceAspect(references[0]), [references]);
  const effectiveAspect = autoAspect ? referenceInfo.value : manualAspect;

  setActiveImageModel(imageModel);

  useEffect(() => {
    try {
      window.localStorage.setItem(VIDEO_OUTPUT_STORAGE_KEY, JSON.stringify({ autoAspect, manualAspect, frameRate }));
    } catch {
      // Storage can be unavailable in hardened browser contexts; controls still work for the session.
    }
  }, [autoAspect, manualAspect, frameRate]);

  useEffect(() => {
    try { window.localStorage.setItem(IMAGE_MODEL_STORAGE_KEY, imageModel); } catch {}
  }, [imageModel]);

  const chooseImageModel = useCallback((nextModel) => {
    if (!MODEL_ADVANCED_PRESETS[nextModel] || nextModel === 'ltx25-redgraft') return;
    setActiveImageModel(nextModel);
    setImageModel(nextModel);
    const preset = MODEL_ADVANCED_PRESETS[nextModel];
    setSteps?.(preset.steps);
    setCfg?.(preset.cfg);
    setNegativePrompt?.(preset.negativePrompt || '');
  }, [setSteps, setCfg, setNegativePrompt]);

  const handleGenerate = useCallback((legacyOptions = {}) => onGenerate({
    ...legacyOptions,
    imageModel,
    videoAspect: effectiveAspect,
    videoAspectMode: autoAspect ? 'auto' : 'manual',
    videoFrameRate: frameRate,
  }), [onGenerate, imageModel, effectiveAspect, autoAspect, frameRate]);

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
    <div className="saga-create-workspace-shell">
      {mode !== 'Video' && (
        <div className="saga-image-model-row" aria-label="Image model selection">
          <span className="saga-image-model-label">Image model</span>
          <div className="saga-image-model-switch" role="group" aria-label="Image model">
            <button type="button" aria-pressed={imageModel === 'flux2-klein-9b'} className={imageModel === 'flux2-klein-9b' ? 'selected' : ''} onClick={() => chooseImageModel('flux2-klein-9b')}>FLUX</button>
            <button type="button" aria-pressed={imageModel === 'qwen-image-edit-2511'} className={imageModel === 'qwen-image-edit-2511' ? 'selected' : ''} onClick={() => chooseImageModel('qwen-image-edit-2511')}>Qwen</button>
          </div>
          <small>{MODEL_ADVANCED_PRESETS[imageModel].modelLabel}</small>
        </div>
      )}
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
    </div>
  );
}
