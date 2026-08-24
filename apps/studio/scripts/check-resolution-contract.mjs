// Item 09 delivery contract: keep Studio terminology and runtime output math aligned.
import { readFile } from 'node:fs/promises';
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

const runtimeSource = await readFile(new URL('../../../integrations/comfyui/ltx23_app.py', import.meta.url), 'utf8');
expect(runtimeSource.includes('ENABLED_RESOLUTIONS = {"480p", "720p", "1080p", "2K"}'), 'Runtime enabled-resolution contract changed');
expect(runtimeSource.includes('RESOLUTION_SHORT_EDGES = {"480p": 480, "720p": 720, "1080p": 1080, "2K": 1152, "4K": 2160}'), 'Runtime short-edge contract changed');
expect(runtimeSource.includes('delivery_width, delivery_height = _delivery_dimensions(resolution, aspect_ratio)'), 'Runtime no longer finalizes against delivery dimensions');

const workflowSource = await readFile(new URL('../api/_workflows.js', import.meta.url), 'utf8');
expect(workflowSource.includes("resolutions: ['480p', '720p', '1080p', '2K']"), 'Studio workflow capability list changed');

const createSource = await readFile(new URL('../src/create-controls.jsx', import.meta.url), 'utf8');
expect(!createSource.includes("label: 'Full HD'"), 'Create controls still use Full HD marketing terminology');
expect(createSource.includes('videoDeliveryDimensions(videoResolution, videoAspect)'), 'Video resolution trigger is not using delivery dimensions');

console.log(JSON.stringify({
  ready: true,
  videoResolutions: VIDEO_RESOLUTIONS.map((item) => item.value),
  examples: {
    landscape1080p: formatDimensions(videoDeliveryDimensions('1080p', '16:9')),
    portrait1080p: formatDimensions(videoDeliveryDimensions('1080p', '9:16')),
    reference4x3: formatDimensions(videoDeliveryDimensions('1080p', '4:3')),
  },
}, null, 2));
