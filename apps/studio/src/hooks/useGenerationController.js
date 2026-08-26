import React from 'react';
import { runImageEdit, runVideoGeneration } from '../generation-client.js';
import { runQwenImageEdit } from '../features/create/qwen-generation-client.js';
import { runJobAction } from '../api/studioApi.js';

export default function useGenerationController({ mode, isEdit, prompt, references, seed, steps, cfg, negativePrompt, autoEditInfo, section, setItems, loadGallery, setError, setSection, setJobsFilter }) {
  const [busy, setBusy] = React.useState(false);
  const [jobStatus, setJobStatus] = React.useState('');
  const [workerStatus, setWorkerStatus] = React.useState(null);
  const [activeJob, setActiveJob] = React.useState(null);
  const [cancelBusy, setCancelBusy] = React.useState(false);
  const generationAbortRef = React.useRef(null);

  const runImageModelEdit = async (imageModel = 'flux2-klein-9b') => {
    if (!references.length) throw new Error('Add at least one reference image before running an edit.');
    if (!prompt.trim()) throw new Error('Describe the edit you want to make.');
    const effectiveSeed = Number(seed) || 42;
    setJobStatus('queued');
    const runner = imageModel === 'qwen-image-edit-2511' ? runQwenImageEdit : runImageEdit;
    const modelLabel = imageModel === 'qwen-image-edit-2511'
      ? 'Qwen Image Edit 2511 · Official BF16'
      : 'FLUX.2 Klein 9B · DarkBeast V2 BFS';
    const { job, result } = await runner({ sourceFiles: references.map((reference) => reference.file), prompt: prompt.trim(), negativePrompt, resolution: autoEditInfo.detail, seed: effectiveSeed, steps, cfg, megapixels: autoEditInfo.megapixels }, { onStatus: setJobStatus, onWorkerStatus: setWorkerStatus, onJob: setActiveJob, signal: generationAbortRef.current?.signal });
    setJobStatus('completed');
    setItems((current) => [{ id: result.generationId || job.id, title: prompt.trim(), url: result.thumbnailUrl || result.mediaUrl, originalUrl: result.mediaUrl, thumbnailUrl: result.thumbnailUrl || null, generated: true, model: modelLabel, resolution: autoEditInfo.detail, seed: effectiveSeed, kind: 'image', mode: 'edit', persisted: true }, ...current]);
    if (section === 'Gallery') loadGallery({ append: false });
  };

  const runLtxVideo = async (videoOptions = {}) => {
    if (!prompt.trim()) throw new Error('Describe the video you want to generate.');
    const effectiveSeed = Number(seed) || 42;
    const videoResolution = String(videoOptions.videoResolution || '480p');
    const videoDuration = Math.max(5, Math.min(30, Math.round(Number(videoOptions.videoDuration) || 5)));
    const videoAudio = videoOptions.videoAudio !== false;
    const videoAspect = String(videoOptions.videoAspect || '16:9');
    const requestedFrameRate = Number(videoOptions.videoFrameRate);
    const videoFrameRate = [24, 25, 30].includes(requestedFrameRate) ? requestedFrameRate : 24;
    const sourceFile = references[0]?.file || null;
    setJobStatus(sourceFile ? 'uploading' : 'queued');
    const { job, result } = await runVideoGeneration({ sourceFile, prompt: prompt.trim(), negativePrompt, resolution: videoResolution, durationSeconds: videoDuration, audioEnabled: videoAudio, aspectRatio: videoAspect, frameRate: videoFrameRate, seed: effectiveSeed, steps, cfg }, { onStatus: setJobStatus, onWorkerStatus: setWorkerStatus, onJob: setActiveJob, signal: generationAbortRef.current?.signal });
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
      else if (mode === 'Image') throw new Error('Original image generation is not connected to a production workflow yet. The new presets are ready for that backend.');
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
