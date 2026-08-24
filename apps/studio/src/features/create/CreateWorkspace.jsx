import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import LegacyCreateWorkspace from '../../create-controls.jsx';
import {
  VideoGenerationProgress,
  VideoOutputControls,
  referenceAspect,
} from './VideoGenerationControls.jsx';

const VIDEO_OUTPUT_STORAGE_KEY = 'saga-studio:video-output:v1';

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
  const { mode, references = [], busy, jobStatus, onGenerate } = props;
  const initial = useMemo(loadVideoOutputSettings, []);
  const [autoAspect, setAutoAspect] = useState(initial.autoAspect);
  const [manualAspect, setManualAspect] = useState(initial.manualAspect);
  const [frameRate, setFrameRate] = useState(initial.frameRate);
  const [toolbarHost, setToolbarHost] = useState(null);
  const [composerHost, setComposerHost] = useState(null);
  const referenceInfo = useMemo(() => referenceAspect(references[0]), [references]);
  const effectiveAspect = autoAspect ? referenceInfo.value : manualAspect;

  useEffect(() => {
    if (mode !== 'Video') {
      setToolbarHost(null);
      setComposerHost(null);
      return;
    }
    const frame = window.requestAnimationFrame(() => {
      setToolbarHost(document.querySelector('.saga-composer.is-video .saga-toolbar-left'));
      setComposerHost(document.querySelector('.saga-composer.is-video'));
    });
    return () => window.cancelAnimationFrame(frame);
  }, [mode]);

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

  return (
    <>
      <LegacyCreateWorkspace {...props} videoAspect={effectiveAspect} onGenerate={handleGenerate} />
      {mode === 'Video' && toolbarHost && createPortal(
        <VideoOutputControls
          autoAspect={autoAspect}
          setAutoAspect={setAutoAspect}
          manualAspect={manualAspect}
          setManualAspect={setManualAspect}
          effectiveAspect={effectiveAspect}
          referenceInfo={referenceInfo}
          frameRate={frameRate}
          setFrameRate={setFrameRate}
        />,
        toolbarHost,
      )}
      {mode === 'Video' && composerHost && createPortal(
        <VideoGenerationProgress busy={busy} status={jobStatus} />,
        composerHost,
      )}
    </>
  );
}
