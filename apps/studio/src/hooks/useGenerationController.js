import React from 'react';
import { createTextGenerationSource, runFluxImageGeneration, runImageEdit, runVideoGeneration } from '../generation-client.js';
import { runQwenImageEdit } from '../features/create/qwen-generation-client.js';
import { runJobAction } from '../api/studioApi.js';

export default function useGenerationController({ mode, isEdit, prompt, references, seed, setSeed, randomizeSeed, steps, cfg, negativePrompt, autoEditInfo, aspect, imageResolution, section, setItems, loadGallery, setError, setSection, setJobsFilter }) {
  const [busy, setBusy] = React.useState(false);
  const [jobStatus, setJobStatus] = React.useState('');
  const [workerStatus, setWorkerStatus] = React.useState(null);
  const [activeJob, setActiveJob] = React.useState(null);
  const [cancelBusy, setCancelBusy] = React.useState(false);
  const generationAbortRef = React.useRef(null);

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

  const runImageModelEdit = async (imageModel = 'flux2-klein-9b') => {
    if (!references.length) throw new Error('Add at least one reference image before running an edit.');
    if (!prompt.trim()) throw new Error('Describe the edit you want to make.');
    const effectiveSeed = effectiveSeedForGeneration();
    setJobStatus('queued');
    const runner = imageModel === 'qwen-image-edit-2511' ? runQwenImageEdit : runImageEdit;
    const modelLabel = imageModel === 'qwen-image-edit-2511'
      ? 'Qwen Image Edit 2511 · Official BF16'
      : 'FLUX.2 Klein 9B · DarkBeast V2 BFS';
    const sourceKeys = await resolveReferenceKeys(references);
    const reusableKeys = sourceKeys.every(Boolean) ? sourceKeys : [];
    const { job, result } = await runner({ sourceFiles: references.map((reference) => reference.file), sourceKeys: reusableKeys, prompt: prompt.trim(), negativePrompt, resolution: autoEditInfo.detail, seed: effectiveSeed, steps, cfg, megapixels: autoEditInfo.megapixels }, { onStatus: setJobStatus, onWorkerStatus: setWorkerStatus, onJob: setActiveJob, signal: generationAbortRef.current?.signal });
    setJobStatus('completed');
    setItems((current) => [{ id: result.generationId || job.id, title: prompt.trim(), url: result.thumbnailUrl || result.mediaUrl, originalUrl: result.mediaUrl, thumbnailUrl: result.thumbnailUrl || null, generated: true, model: modelLabel, resolution: autoEditInfo.detail, seed: effectiveSeed, kind: 'image', mode: 'edit', persisted: true }, ...current]);
    if (section === 'Gallery') loadGallery({ append: false });
  };

  const runTextImage = async (generationOptions = {}) => {
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

  const runLtxVideo = async (videoOptions = {}) => {
    if (!prompt.trim()) throw new Error('Describe the video you want to generate.');
    const effectiveSeed = effectiveSeedForGeneration();
    const videoResolution = String(videoOptions.videoResolution || '480p');
    const videoDuration = Math.max(5, Math.min(30, Math.round(Number(videoOptions.videoDuration) || 5)));
    const videoAudio = videoOptions.videoAudio !== false;
    const videoAspect = String(videoOptions.videoAspect || '16:9');
    const requestedFrameRate = Number(videoOptions.videoFrameRate);
    const videoFrameRate = [24, 25, 30].includes(requestedFrameRate) ? requestedFrameRate : 24;
    const sourceFile = references[0]?.file || null;
    const sourceKeys = sourceFile ? await resolveReferenceKeys([references[0]]) : [];
    const sourceKey = sourceKeys[0] || '';
    setJobStatus(sourceFile ? 'uploading' : 'queued');
    const { job, result } = await runVideoGeneration({ sourceFile, sourceKey, prompt: prompt.trim(), negativePrompt, resolution: videoResolution, durationSeconds: videoDuration, audioEnabled: videoAudio, aspectRatio: videoAspect, frameRate: videoFrameRate, seed: effectiveSeed, steps, cfg }, { onStatus: setJobStatus, onWorkerStatus: setWorkerStatus, onJob: setActiveJob, signal: generationAbortRef.current?.signal });
    setJobStatus('completed');
    setItems((current) => [{ id: result.generationId || job.id, title: prompt.trim(), url: result.thumbnailUrl || result.mediaUrl, originalUrl: result.mediaUrl, thumbnailUrl: result.thumbnailUrl || null, generated: true, model: 'REDGraft LTX 2.5 · Sulphur2 INT8 ConvRot', resolution: videoResolution, seed: effectiveSeed, kind: 'video', mode: sourceFile ? 'image-to-video' : 'video', persisted: true, durationSeconds: videoDuration, audioEnabled: videoAudio, aspectRatio: videoAspect, frameRate: videoFrameRate, steps: Number(steps), cfg: Number(cfg) }, ...current]);
    if (section === 'Gallery') loadGallery({ append: false });
  };

  const generate = async (generationOptions = {}) => {
    if (busy) return;
    const controller = new AbortController(); generationAbortRef.current = controller;
    setBusy(true); setError(''); setJobStatus(''); setWorkerStatus(null); setActiveJob(null); setCancelBusy(false);
    try {
      if (isEdit) await runImageModelEdit(generationOptions.imageModel || 'flux2-klein-9b');
      else if (mode === 'Image') await runTextImage(generationOptions);
      else if (mode === 'Video') await runLtxVideo(generationOptions);
      else throw new Error('Choose Image, Video, or Edit to generate media.');
    } catch (err) {
      if (err?.name === 'AbortError') { setJobStatus('cancelled'); setWorkerStatus((current) => ({ ...(current || {}), state: 'cancelled' })); setError(''); }
      else { setJobStatus('failed'); const terminalWorkerState = ['credit_exhausted', 'unavailable'].includes(String(err?.workerState || '')) ? String(err.workerState) : 'failed'; setWorkerStatus((current) => ({ ...(current || {}), ...(err?.worker || {}), state: terminalWorkerState, errorCode: err?.errorCode || null })); setError(err instanceof Error ? err.message : 'Generation failed.'); }
    } finally { if (generationAbortRef.current === controller) generationAbortRef.current = null; setBusy(false); setCancelBusy(false); }
  };

  const viewActiveJob = () => { setJobsFilter('all'); setSection('Jobs'); };
  const cancelActiveJob = async () => {
    if (!busy || !activeJob?.id || cancelBusy) return;
    if (!window.confirm('Cancel this generation? The provider job will be stopped if it is still running.')) return;
    setCancelBusy(true); setError('');
    try { const payload = await runJobAction(activeJob.id, 'cancel'); setActiveJob(payload?.job || activeJob); setJobStatus('cancelled'); setWorkerStatus((current) => ({ ...(current || {}), state: 'cancelled' })); generationAbortRef.current?.abort(); }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to cancel generation.'); setCancelBusy(false); }
  };
  return { busy, jobStatus, workerStatus, activeJob, cancelBusy, generate, viewActiveJob, cancelActiveJob };
}
