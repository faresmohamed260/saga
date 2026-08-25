import React, { useCallback, useEffect, useMemo, useState } from 'react';
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
