import sharp from 'sharp';
import { access, mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

const root = process.cwd();
const captureDir = path.resolve(process.env.UI_PREVIEW_DIR || 'visual-preview');
const baselineDir = path.resolve(process.env.UI_BASELINE_DIR || 'visual-baselines');
const diffDir = path.resolve(process.env.UI_DIFF_DIR || path.join(captureDir, 'diffs'));
const manifestPath = path.resolve(process.env.UI_BASELINE_MANIFEST || path.join(baselineDir, 'manifest.json'));
const update = process.env.UPDATE_VISUAL_BASELINES === '1';

await mkdir(diffDir, { recursive: true });
const manifest = JSON.parse(await readFile(manifestPath, 'utf8'));
const report = { generatedAt: new Date().toISOString(), update, baselineDir, captureDir, comparisons: [] };

function changedPixel(a, b, threshold) {
  return Math.max(Math.abs(a[0] - b[0]), Math.abs(a[1] - b[1]), Math.abs(a[2] - b[2]), Math.abs(a[3] - b[3])) > threshold;
}

for (const surface of manifest.surfaces) {
  const actualPath = path.join(captureDir, surface.file);
  const baselinePath = path.join(baselineDir, surface.file);
  await access(actualPath);

  if (update) {
    const buffer = await readFile(actualPath);
    await mkdir(path.dirname(baselinePath), { recursive: true });
    await writeFile(baselinePath, buffer);
    report.comparisons.push({ file: surface.file, status: 'baseline-updated' });
    continue;
  }

  await access(baselinePath).catch(() => { throw new Error(`Missing approved visual baseline: ${surface.file}. Run with UPDATE_VISUAL_BASELINES=1 only after review.`); });
  const actual = await sharp(actualPath).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  const baseline = await sharp(baselinePath).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  if (actual.info.width !== baseline.info.width || actual.info.height !== baseline.info.height) {
    throw new Error(`${surface.file} dimensions changed: ${baseline.info.width}x${baseline.info.height} -> ${actual.info.width}x${actual.info.height}`);
  }

  const threshold = surface.channelThreshold ?? manifest.defaults.channelThreshold;
  const allowedRatio = surface.maxChangedRatio ?? manifest.defaults.maxChangedRatio;
  const pixels = actual.info.width * actual.info.height;
  let changed = 0;
  const diff = Buffer.alloc(actual.data.length);
  for (let offset = 0; offset < actual.data.length; offset += 4) {
    const a = actual.data.subarray(offset, offset + 4);
    const b = baseline.data.subarray(offset, offset + 4);
    const isChanged = changedPixel(a, b, threshold);
    if (isChanged) changed += 1;
    diff[offset] = isChanged ? 255 : Math.round(b[0] * 0.24);
    diff[offset + 1] = isChanged ? 64 : Math.round(b[1] * 0.24);
    diff[offset + 2] = isChanged ? 128 : Math.round(b[2] * 0.24);
    diff[offset + 3] = 255;
  }
  const ratio = changed / pixels;
  const result = { file: surface.file, changedPixels: changed, changedRatio: ratio, maxChangedRatio: allowedRatio, channelThreshold: threshold, status: ratio <= allowedRatio ? 'pass' : 'fail' };
  report.comparisons.push(result);
  if (changed) await sharp(diff, { raw: { width: actual.info.width, height: actual.info.height, channels: 4 } }).png().toFile(path.join(diffDir, surface.file));
}

await writeFile(path.join(captureDir, 'visual-regression-report.json'), JSON.stringify(report, null, 2));
const failures = report.comparisons.filter((entry) => entry.status === 'fail');
if (failures.length) {
  throw new Error(`Visual regression detected: ${failures.map((entry) => `${entry.file} ${(entry.changedRatio * 100).toFixed(3)}% > ${(entry.maxChangedRatio * 100).toFixed(3)}%`).join(', ')}`);
}
console.log(update ? `Updated ${report.comparisons.length} visual baselines.` : `Visual regression gate passed for ${report.comparisons.length} approved surfaces.`);
