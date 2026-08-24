export const IMAGE_RESOLUTIONS = [
  { value: 480, label: '480 px' },
  { value: 720, label: '720 px' },
  { value: 1080, label: '1080 px' },
  { value: 2048, label: '2048 px' },
  { value: 3840, label: '3840 px' },
];

// These are the resolutions currently accepted by the REDGraft LTX 2.5
// production workflow. 4K intentionally stays out of this list until the
// runtime capability is enabled.
export const VIDEO_RESOLUTIONS = [
  { value: '480p', label: '480p', shortEdge: 480 },
  { value: '720p', label: '720p', shortEdge: 720 },
  { value: '1080p', label: '1080p', shortEdge: 1080 },
  { value: '2K', label: '2K', shortEdge: 1152 },
];

function ratioValue(aspect, fallback = 1) {
  const match = String(aspect || '').trim().match(/^(\d+(?:\.\d+)?):(\d+(?:\.\d+)?)$/);
  if (!match) return fallback;
  const width = Number(match[1]);
  const height = Number(match[2]);
  if (!(width > 0) || !(height > 0)) return fallback;
  const ratio = width / height;
  return Number.isFinite(ratio) ? ratio : fallback;
}

function round64(value) {
  return Math.max(64, Math.round(Number(value) / 64) * 64);
}

function even(value) {
  return Math.max(2, Math.round(Number(value) / 2) * 2);
}

export function dimensionsForPreset(aspect, longEdge) {
  const ratio = ratioValue(aspect, 1);
  if (ratio >= 1) return { width: round64(longEdge), height: round64(Number(longEdge) / ratio) };
  return { width: round64(Number(longEdge) * ratio), height: round64(longEdge) };
}

export function videoDeliveryDimensions(resolution, aspect = '16:9') {
  const preset = VIDEO_RESOLUTIONS.find((item) => item.value === resolution) || VIDEO_RESOLUTIONS[2];
  const ratio = ratioValue(aspect, 16 / 9);
  if (ratio >= 1) {
    const height = preset.shortEdge;
    return { width: even(height * ratio), height };
  }
  const width = preset.shortEdge;
  return { width, height: even(width / ratio) };
}

export function formatDimensions(dimensions) {
  if (!dimensions) return '';
  return `${dimensions.width}×${dimensions.height}`;
}
