import { readFile, writeFile } from 'node:fs/promises';

function replaceOnce(source, from, to, label) {
  if (source.includes(to)) return source;
  if (!source.includes(from)) throw new Error(`Missing ${label}`);
  return source.replace(from, to);
}

let main = await readFile('src/main.jsx', 'utf8');
main = replaceOnce(
  main,
  "import { runImageEdit } from './generation-client.js';",
  "import { runImageEdit, runVideoGeneration } from './generation-client.js';",
  'generation client import',
);
main = replaceOnce(
  main,
  "    if (valid.length) { setReferences((current) => [...current, ...valid]); setMode('Edit'); setError(''); }",
  "    if (valid.length) {\n      if (mode === 'Video') {\n        const next = valid[0];\n        setReferences((current) => {\n          current.forEach((reference) => reference.preview && URL.revokeObjectURL(reference.preview));\n          return next ? [next] : [];\n        });\n        if (valid.length > 1) valid.slice(1).forEach((reference) => reference.preview && URL.revokeObjectURL(reference.preview));\n      } else {\n        setReferences((current) => [...current, ...valid]);\n        setMode('Edit');\n      }\n      setError('');\n    }",
  'reference mode handling',
);

const generationAnchor = "  const generate = async () => {\n";
if (!main.includes('const runLtxVideo = async')) {
  const videoFunction = `  const runLtxVideo = async (videoOptions = {}) => {\n    if (!prompt.trim()) throw new Error('Describe the video you want to generate.');\n    const effectiveSeed = Number(seed) || 42;\n    const videoResolution = String(videoOptions.videoResolution || '480p');\n    const videoDuration = Math.max(5, Math.min(30, Math.round(Number(videoOptions.videoDuration) || 5)));\n    const videoAudio = videoOptions.videoAudio !== false;\n    const sourceFile = references[0]?.file || null;\n    setJobStatus(sourceFile ? 'uploading' : 'queued');\n\n    const { job, result } = await runVideoGeneration({\n      sourceFile,\n      prompt: prompt.trim(),\n      resolution: videoResolution,\n      durationSeconds: videoDuration,\n      audioEnabled: videoAudio,\n      seed: effectiveSeed,\n    }, { onStatus: setJobStatus });\n\n    setJobStatus('completed');\n    const item = {\n      id: result.generationId || job.id,\n      title: prompt.trim(),\n      url: result.thumbnailUrl || result.mediaUrl,\n      originalUrl: result.mediaUrl,\n      thumbnailUrl: result.thumbnailUrl || null,\n      generated: true,\n      model: 'LTX-Video 2.3 · 22B Distilled',\n      resolution: videoResolution,\n      seed: effectiveSeed,\n      kind: 'video',\n      mode: sourceFile ? 'image-to-video' : 'video',\n      persisted: true,\n      durationSeconds: videoDuration,\n      audioEnabled: videoAudio,\n    };\n    setItems((current) => [item, ...current]);\n    if (section === 'History') loadHistory({ append: false });\n  };\n\n`;
  main = replaceOnce(main, generationAnchor, videoFunction + "  const generate = async (generationOptions = {}) => {\n", 'generate function');
}
main = replaceOnce(
  main,
  "      else if (mode === 'Video') throw new Error('Video generation is the next workflow milestone and is not connected yet.');",
  "      else if (mode === 'Video') await runLtxVideo(generationOptions);",
  'video generation branch',
);

// Render persisted video media as a real video element instead of a background image.
main = replaceOnce(
  main,
  "      <div className={`media-frame ${!item.url ? 'media-frame-empty' : ''}`} style={item.url ? { backgroundImage: `url(${item.url})` } : undefined} onClick={() => openMedia(item)} role=\"button\" tabIndex={0}>\n        {!item.url && <div className=\"media-placeholder\"><Video size={28}/><span>Video preview</span></div>}",
  "      <div className={`media-frame ${!item.url ? 'media-frame-empty' : ''}`} style={item.url && item.kind !== 'video' ? { backgroundImage: `url(${item.url})` } : undefined} onClick={() => openMedia(item)} role=\"button\" tabIndex={0}>\n        {item.kind === 'video' && item.url ? <video className=\"media-video-preview\" src={item.originalUrl || item.url} muted playsInline preload=\"metadata\" /> : null}\n        {!item.url && <div className=\"media-placeholder\"><Video size={28}/><span>Video preview</span></div>}",
  'video card media',
);
await writeFile('src/main.jsx', main);

let controls = await readFile('src/create-controls.jsx', 'utf8');
controls = replaceOnce(
  controls,
  '                onClick={onGenerate}',
  '                onClick={() => onGenerate({ videoResolution, videoDuration, videoAudio })}',
  'composer generate payload',
);
controls = replaceOnce(
  controls,
  "          {isEdit && (\n            <ReferenceStrip\n              references={references}\n              onRemove={onRemoveReference}\n              onInsert={(index) => promptRef.current?.insertReference(index)}\n            />\n          )}",
  "          {(isEdit || (isVideo && references.length > 0)) && (\n            <ReferenceStrip\n              references={references}\n              onRemove={onRemoveReference}\n              onInsert={isEdit ? (index) => promptRef.current?.insertReference(index) : undefined}\n            />\n          )}",
  'video reference strip',
);
controls = replaceOnce(
  controls,
  "function ReferenceStrip({ references, onRemove, onInsert }) {",
  "function ReferenceStrip({ references, onRemove, onInsert }) {",
  'reference strip signature',
);
controls = replaceOnce(
  controls,
  "            title={`Insert Image ${index + 1} at cursor`}\n            onMouseDown={(event) => event.preventDefault()}\n            onClick={() => onInsert(index)}",
  "            title={onInsert ? `Insert Image ${index + 1} at cursor` : `Image ${index + 1} video reference`}\n            onMouseDown={(event) => event.preventDefault()}\n            onClick={() => onInsert?.(index)}\n            disabled={!onInsert}",
  'reference click behavior',
);
await writeFile('src/create-controls.jsx', controls);

let css = await readFile('src/create-workspace-v2.css', 'utf8');
if (!css.includes('.media-video-preview')) {
  css += `\n.workspace .media-video-preview{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:block}\n`;
}
await writeFile('src/create-workspace-v2.css', css);
