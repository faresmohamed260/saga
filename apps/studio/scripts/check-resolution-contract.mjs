// Items 09 + 30 delivery contract: keep Studio terminology, runtime output math,
// LTX internal alignment, and exact delivered duration aligned without GPU generation.
import { spawnSync } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import {
  IMAGE_RESOLUTIONS,
  VIDEO_RESOLUTIONS,
  dimensionsForPreset,
  formatDimensions,
  videoDeliveryDimensions,
} from '../src/features/create/ResolutionPresets.js';

function expect(condition, message) {
  if (!condition) throw new Error(message);
}

function expectDimensions(actual, width, height, label) {
  expect(actual.width === width && actual.height === height, `${label}: expected ${width}×${height}, got ${formatDimensions(actual)}`);
}

function parseRatio(aspect) {
  const match = String(aspect || '').trim().match(/^(\d+(?:\.\d+)?):(\d+(?:\.\d+)?)$/);
  expect(match, `Invalid test aspect ratio: ${aspect}`);
  const width = Number(match[1]);
  const height = Number(match[2]);
  expect(width > 0 && height > 0, `Invalid test aspect ratio: ${aspect}`);
  return width / height;
}

const aspectSource = await readFile(new URL('../src/features/create/AspectPicker.jsx', import.meta.url), 'utf8');
const aspectPresetBlock = aspectSource.match(/export const ASPECT_PRESETS = \[(.*?)\];/s)?.[1] || '';
const supportedAspects = [...aspectPresetBlock.matchAll(/value:\s*'([^']+)'/g)].map((match) => match[1]);
const expectedAspects = ['1:1', '4:5', '3:4', '2:3', '9:16', '5:4', '4:3', '3:2', '16:10', '16:9', '21:9'];
expect(supportedAspects.join(',') === expectedAspects.join(','), `Aspect preset contract changed: ${supportedAspects.join(',')}`);

expect(IMAGE_RESOLUTIONS.map((item) => item.label).join(',') === '480 px,720 px,1080 px,2048 px,3840 px', 'Image resolution labels are not explicit pixel terminology');
expect(VIDEO_RESOLUTIONS.map((item) => item.value).join(',') === '480p,720p,1080p,2K', 'Video resolution capability list must match enabled production resolutions');
expect(!VIDEO_RESOLUTIONS.some((item) => item.value === '4K'), 'Video UI must not advertise disabled 4K generation');

expectDimensions(dimensionsForPreset('1:1', 1080), 1088, 1088, 'Image 1080 px at 1:1');
expectDimensions(dimensionsForPreset('16:9', 2048), 2048, 1152, 'Image 2048 px at 16:9');
expectDimensions(videoDeliveryDimensions('480p', '16:9'), 854, 480, '480p at 16:9');
expectDimensions(videoDeliveryDimensions('720p', '16:9'), 1280, 720, '720p at 16:9');
expectDimensions(videoDeliveryDimensions('1080p', '16:9'), 1920, 1080, '1080p at 16:9');
expectDimensions(videoDeliveryDimensions('1080p', '9:16'), 1080, 1920, '1080p at 9:16');
expectDimensions(videoDeliveryDimensions('1080p', '4:3'), 1440, 1080, '1080p at 4:3');
expectDimensions(videoDeliveryDimensions('2K', '16:9'), 2048, 1152, '2K at 16:9');

const runtimeUrl = new URL('../../../integrations/comfyui/ltx23_app.py', import.meta.url);
const runtimePath = fileURLToPath(runtimeUrl);
const runtimeSource = await readFile(runtimeUrl, 'utf8');
expect(runtimeSource.includes('ENABLED_RESOLUTIONS = {"480p", "720p", "1080p", "2K"}'), 'Runtime enabled-resolution contract changed');
expect(runtimeSource.includes('RESOLUTION_SHORT_EDGES = {"480p": 480, "720p": 720, "1080p": 1080, "2K": 1152, "4K": 2160}'), 'Runtime short-edge contract changed');
expect(runtimeSource.includes('FRAME_RATES = {24, 25, 30}'), 'Runtime frame-rate contract changed');
expect(runtimeSource.includes('target_width, target_height = _internal_dimensions(resolution, aspect_ratio)'), 'Runtime workflow no longer uses 64-aligned internal dimensions');
expect(runtimeSource.includes('delivery_width, delivery_height = _delivery_dimensions(resolution, aspect_ratio)'), 'Runtime no longer finalizes against delivery dimensions');
expect(runtimeSource.includes('target_frames = int(duration_seconds) * int(frame_rate)'), 'Runtime finalizer no longer clamps to exact requested frame count');
expect(runtimeSource.includes('"-frames:v", str(target_frames)'), 'Runtime ffmpeg finalizer no longer enforces exact delivered video frames');
expect(runtimeSource.includes('"-r", str(int(frame_rate))'), 'Runtime ffmpeg finalizer no longer enforces requested frame rate');
expect(runtimeSource.includes('atrim=duration={float(duration_seconds):.3f},asetpts=PTS-STARTPTS'), 'Runtime ffmpeg finalizer no longer trims audio to requested duration');

const workflowSource = await readFile(new URL('../api/_workflows.js', import.meta.url), 'utf8');
expect(workflowSource.includes("resolutions: ['480p', '720p', '1080p', '2K']"), 'Studio workflow capability list changed');
expect(workflowSource.includes('frameRates: [24, 25, 30]'), 'Studio workflow frame-rate capability list changed');

const createSource = await readFile(new URL('../src/create-controls.jsx', import.meta.url), 'utf8');
expect(!createSource.includes("label: 'Full HD'"), 'Create controls still use Full HD marketing terminology');
expect(createSource.includes('videoDeliveryDimensions(videoResolution, videoAspect)'), 'Video resolution trigger is not using delivery dimensions');

// Exercise the worker's exact pure delivery functions by parsing only the safe
// constants/functions from ltx23_app.py. This imports no Modal code and starts no GPU.
const oddReferenceAspects = ['1179:2556', '2556:1179', '1001:777', '777:1001', '481:480', '480:481'];
const matrixAspects = [...supportedAspects, ...oddReferenceAspects];
const frameRates = [24, 25, 30];
const durations = Array.from({ length: 26 }, (_, index) => index + 5);
const matrixCases = VIDEO_RESOLUTIONS.flatMap((resolution) => matrixAspects.flatMap((aspect) => frameRates.map((frameRate) => ({
  resolution: resolution.value,
  aspect,
  frameRate,
  duration: 5,
}))));
const durationCases = durations.flatMap((duration) => frameRates.map((frameRate) => ({ duration, frameRate })));

const pythonHarness = String.raw`
import ast
import json
import math
import sys
from pathlib import Path

runtime_path = Path(sys.argv[1])
source = runtime_path.read_text(encoding='utf-8')
tree = ast.parse(source, filename=str(runtime_path))
wanted_functions = {
    '_parse_aspect_ratio', '_even', '_align64', '_delivery_dimensions',
    '_internal_dimensions', '_frame_count',
}
wanted_assignments = {'RESOLUTION_SHORT_EDGES'}
selected = []
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name in wanted_functions:
        selected.append(node)
        continue
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        names = {target.id for target in targets if isinstance(target, ast.Name)}
        if names & wanted_assignments:
            selected.append(node)
namespace = {'math': math}
module = ast.Module(body=selected, type_ignores=[])
ast.fix_missing_locations(module)
exec(compile(module, str(runtime_path), 'exec'), namespace)

payload = json.load(sys.stdin)
matrix = []
for case in payload['matrixCases']:
    delivery = namespace['_delivery_dimensions'](case['resolution'], case['aspect'])
    internal = namespace['_internal_dimensions'](case['resolution'], case['aspect'])
    frames = namespace['_frame_count'](case['duration'], case['frameRate'])
    matrix.append({**case, 'delivery': delivery, 'internal': internal, 'generatedFrames': frames})
duration_rows = []
for case in payload['durationCases']:
    frames = namespace['_frame_count'](case['duration'], case['frameRate'])
    duration_rows.append({**case, 'generatedFrames': frames})
print(json.dumps({'matrix': matrix, 'durations': duration_rows}))
`;

const python = spawnSync('python3', ['-c', pythonHarness, runtimePath], {
  input: JSON.stringify({ matrixCases, durationCases }),
  encoding: 'utf8',
  maxBuffer: 10 * 1024 * 1024,
});
expect(python.status === 0, `Pure runtime delivery harness failed: ${python.stderr || python.stdout}`);
const runtimeContract = JSON.parse(python.stdout);
expect(runtimeContract.matrix.length === matrixCases.length, 'Runtime matrix result count mismatch');
expect(runtimeContract.durations.length === durationCases.length, 'Runtime duration result count mismatch');

let worstAspectError = 0;
let worstAspectTolerance = 0;
let worstAspectCase = null;
for (const row of runtimeContract.matrix) {
  const [deliveryWidth, deliveryHeight] = row.delivery;
  const [internalWidth, internalHeight] = row.internal;
  const requestedRatio = parseRatio(row.aspect);
  const deliveredRatio = deliveryWidth / deliveryHeight;
  const relativeError = Math.abs(deliveredRatio - requestedRatio) / requestedRatio;
  const idealLongEdge = requestedRatio >= 1 ? deliveryHeight * requestedRatio : deliveryWidth / requestedRatio;
  const actualLongEdge = requestedRatio >= 1 ? deliveryWidth : deliveryHeight;
  const longEdgeQuantizationError = Math.abs(actualLongEdge - idealLongEdge);
  const aspectRelativeTolerance = 1 / idealLongEdge + 1e-12;
  if (relativeError > worstAspectError) {
    worstAspectError = relativeError;
    worstAspectTolerance = aspectRelativeTolerance;
    worstAspectCase = row;
  }

  expect(deliveryWidth % 2 === 0 && deliveryHeight % 2 === 0, `${row.resolution} ${row.aspect}: delivery dimensions must be even, got ${deliveryWidth}×${deliveryHeight}`);
  expect(internalWidth % 64 === 0 && internalHeight % 64 === 0, `${row.resolution} ${row.aspect}: internal dimensions must be 64-aligned, got ${internalWidth}×${internalHeight}`);
  expect(internalWidth >= deliveryWidth && internalHeight >= deliveryHeight, `${row.resolution} ${row.aspect}: internal dimensions cannot undershoot delivery dimensions`);
  expect((internalWidth / 2) % 32 === 0 && (internalHeight / 2) % 32 === 0, `${row.resolution} ${row.aspect}: low-stage dimensions must remain 32-aligned`);
  expect(longEdgeQuantizationError <= 1 + 1e-9, `${row.resolution} ${row.aspect}: nearest-even delivery changed the flexible edge by more than 1px (${longEdgeQuantizationError})`);
  expect(relativeError <= aspectRelativeTolerance, `${row.resolution} ${row.aspect}: delivered aspect error ${(relativeError * 100).toFixed(4)}% exceeds the exact one-pixel quantization tolerance ${(aspectRelativeTolerance * 100).toFixed(4)}%`);

  const uiDimensions = videoDeliveryDimensions(row.resolution, row.aspect);
  expect(uiDimensions.width === deliveryWidth && uiDimensions.height === deliveryHeight, `${row.resolution} ${row.aspect}: Studio/runtime delivery mismatch (${formatDimensions(uiDimensions)} vs ${deliveryWidth}×${deliveryHeight})`);

  const targetFrames = row.duration * row.frameRate;
  expect((row.generatedFrames - 1) % 8 === 0, `${row.frameRate}fps: generated frame count ${row.generatedFrames} is not 8n+1`);
  expect(row.generatedFrames >= targetFrames + 1 && row.generatedFrames <= targetFrames + 8, `${row.frameRate}fps: padded frame count ${row.generatedFrames} is outside exact-delivery padding bounds for ${targetFrames} delivered frames`);
}

for (const row of runtimeContract.durations) {
  const targetFrames = row.duration * row.frameRate;
  const deliveredDuration = targetFrames / row.frameRate;
  expect(deliveredDuration === row.duration, `${row.duration}s @ ${row.frameRate}fps: delivered duration is not exact`);
  expect((row.generatedFrames - 1) % 8 === 0, `${row.duration}s @ ${row.frameRate}fps: generated frame count ${row.generatedFrames} is not 8n+1`);
  expect(row.generatedFrames >= targetFrames + 1 && row.generatedFrames <= targetFrames + 8, `${row.duration}s @ ${row.frameRate}fps: internal padding escaped expected 1–8 frame range`);
}

const canonicalLandscape = runtimeContract.matrix.find((row) => row.resolution === '1080p' && row.aspect === '16:9' && row.frameRate === 24);
const canonicalPortrait = runtimeContract.matrix.find((row) => row.resolution === '1080p' && row.aspect === '9:16' && row.frameRate === 24);
expect(canonicalLandscape?.delivery?.[0] === 1920 && canonicalLandscape?.delivery?.[1] === 1080, `Canonical 1080p landscape changed: ${canonicalLandscape?.delivery?.join('×')}`);
expect(canonicalPortrait?.delivery?.[0] === 1080 && canonicalPortrait?.delivery?.[1] === 1920, `Canonical 1080p portrait changed: ${canonicalPortrait?.delivery?.join('×')}`);

console.log(JSON.stringify({
  ready: true,
  videoResolutions: VIDEO_RESOLUTIONS.map((item) => item.value),
  supportedAspects,
  oddReferenceAspects,
  frameRates,
  matrixCases: runtimeContract.matrix.length,
  durationCases: runtimeContract.durations.length,
  aspectToleranceRule: 'nearest-even flexible edge <= 1px; relative tolerance <= 1 / ideal long edge',
  worstAspectTolerance,
  worstAspectError,
  worstAspectCase: worstAspectCase ? {
    resolution: worstAspectCase.resolution,
    aspect: worstAspectCase.aspect,
    delivery: worstAspectCase.delivery,
  } : null,
  canonical: {
    landscape1080p: canonicalLandscape.delivery,
    portrait1080p: canonicalPortrait.delivery,
  },
}, null, 2));
