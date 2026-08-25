from pathlib import Path


def replace_once(path, old, new, label):
    p = Path(path)
    text = p.read_text(encoding='utf-8')
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    p.write_text(text.replace(old, new, 1), encoding='utf-8')


# 1) Keep the Image setup state aligned with the actual live FLUX edit workflow.
replace_once(
    'apps/studio/src/app/App.jsx',
    "  const [workflowId, setWorkflowId] = useState('default-image');\n  const [modelId, setModelId] = useState('saga-image-auto');",
    "  const [workflowId, setWorkflowId] = useState('flux2-klein-image-edit');\n  const [modelId, setModelId] = useState('flux2-klein-9b');",
    'live Image setup defaults',
)
replace_once(
    'apps/studio/src/app/App.jsx',
    "      setWorkflowId('default-image');\n      setModelId('saga-image-auto');",
    "      setWorkflowId('flux2-klein-image-edit');\n      setModelId('flux2-klein-9b');",
    'live Image setup reset after last reference',
)

# 2) Remove the disabled Gallery tab that advertises a feature that does not exist.
replace_once(
    'apps/studio/src/features/library/GalleryView.jsx',
    "  Shapes,\n",
    "",
    'remove unused Elements icon import',
)
replace_once(
    'apps/studio/src/features/library/GalleryView.jsx',
    "          <button type=\"button\" role=\"tab\" aria-selected=\"false\" aria-disabled=\"true\" disabled title=\"Reusable Elements are not available yet\"><Shapes size={16}/><span>Elements</span></button>\n",
    "",
    'remove placeholder Elements tab',
)

# 3) Do not present video editing as a working action when no video-edit workflow exists.
replace_once(
    'apps/studio/src/components/MediaCard.jsx',
    "            <button type=\"button\" role=\"menuitem\" onClick={menuAction(onEdit)}><Pencil size={15}/><span>Edit</span></button>\n",
    "            {item.kind !== 'video' && <button type=\"button\" role=\"menuitem\" onClick={menuAction(onEdit)}><Pencil size={15}/><span>Edit</span></button>}\n",
    'hide unsupported video Edit menu action',
)
replace_once(
    'apps/studio/src/components/MediaCard.jsx',
    "      <button type=\"button\" title=\"Edit this\" aria-label=\"Edit this\" onClick={action(onEdit)}><Pencil size={16}/></button>\n",
    "      {item.kind !== 'video' && <button type=\"button\" title=\"Edit this\" aria-label=\"Edit this\" onClick={action(onEdit)}><Pencil size={16}/></button>}\n",
    'hide unsupported video Edit standard action',
)

# 4) Make the full-media viewer behave like a real accessible modal.
modal = Path('apps/studio/src/components/MediaModal.jsx')
modal.write_text("""import React from 'react';
import { X } from 'lucide-react';
import { modelDisplayName, modelImplementationLabel } from '../model-labels.js';

export default function MediaModal({ item, onClose }) {
  React.useEffect(() => {
    if (!item) return undefined;
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') onClose?.();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [item, onClose]);

  if (!item) return null;
  const implementation = modelImplementationLabel(item.model);
  const displayModel = modelDisplayName(item.model);
  const source = item.originalUrl || item.url || '';
  return (
    <div className=\"media-modal\" role=\"presentation\" onMouseDown={(event) => event.target === event.currentTarget && onClose?.()}>
      <section className=\"media-modal-card\" role=\"dialog\" aria-modal=\"true\" aria-label={`Preview ${item.title || 'generated media'}`}>
        <button type=\"button\" className=\"media-modal-close\" aria-label=\"Close media preview\" onClick={onClose}><X size={20}/></button>
        {item.kind === 'video'
          ? <video src={source} poster={item.thumbnailUrl || undefined} controls playsInline autoFocus />
          : <img src={source} alt={item.title || 'Generated image'} />}
        <div className=\"media-modal-copy\">
          <strong>{item.title || 'Generated media'}</strong>
          <span>{[displayModel !== 'Unknown model' ? displayModel : null, item.resolution, item.aspectRatio, item.frameRate ? `${item.frameRate}fps` : null].filter(Boolean).join(' · ')}</span>
          <details className=\"media-modal-details\">
            <summary>Details</summary>
            <dl>
              {item.model && <><dt>Model</dt><dd>{displayModel}</dd></>}
              {implementation && implementation !== displayModel && <><dt>Implementation</dt><dd>{implementation}</dd></>}
              {item.seed != null && <><dt>Seed</dt><dd>{item.seed}</dd></>}
              {item.width && item.height && <><dt>Dimensions</dt><dd>{item.width} × {item.height}</dd></>}
              {item.createdAt && <><dt>Created</dt><dd>{new Date(item.createdAt).toLocaleString()}</dd></>}
            </dl>
          </details>
        </div>
      </section>
    </div>
  );
}
""", encoding='utf-8')

# 5) Use task-first Image copy. Leading generation tools make the required input obvious before submission.
replace_once(
    'apps/studio/src/create-controls.jsx',
    "  const heading = isEdit ? 'Transform your references' : isVideo ? 'Create motion' : 'Prepare an image edit';",
    "  const heading = isEdit ? 'Transform your references' : isVideo ? 'Create motion' : 'Create from a reference';",
    'task-first Image heading',
)
replace_once(
    'apps/studio/src/create-controls.jsx',
    "          <p>{isEdit ? 'Click a reference to insert it exactly where your cursor is.' : isVideo ? 'Shape the shot, duration, resolution, and audio before generation.' : 'Set your image controls now, then add a reference to start the live FLUX edit workflow.'}</p>",
    "          <p>{isEdit ? 'Describe the change and reference images directly in your prompt.' : isVideo ? 'Describe the shot, then set duration, framing, resolution, and audio.' : 'Add an image, describe the change, and generate with the live FLUX edit model.'}</p>",
    'task-first Create guidance',
)

# 6) Add browser-visible contract checks for the removed fake surfaces.
check = Path('apps/studio/scripts/check-ui-ux-benchmark-contract.mjs')
check.write_text("""import { readFile } from 'node:fs/promises';

const [app, gallery, card, modal, controls] = await Promise.all([
  readFile(new URL('../src/app/App.jsx', import.meta.url), 'utf8'),
  readFile(new URL('../src/features/library/GalleryView.jsx', import.meta.url), 'utf8'),
  readFile(new URL('../src/components/MediaCard.jsx', import.meta.url), 'utf8'),
  readFile(new URL('../src/components/MediaModal.jsx', import.meta.url), 'utf8'),
  readFile(new URL('../src/create-controls.jsx', import.meta.url), 'utf8'),
]);

const checks = [
  [app.includes("useState('flux2-klein-image-edit')"), 'Image setup does not default to the live FLUX workflow'],
  [app.includes("useState('flux2-klein-9b')"), 'Image setup does not default to the live FLUX model'],
  [!gallery.includes('Reusable Elements are not available yet'), 'Disabled placeholder Elements tab remains'],
  [card.includes("item.kind !== 'video'"), 'Video cards still expose unsupported Edit actions'],
  [modal.includes('aria-modal=\"true\"'), 'Media preview is not a real modal dialog'],
  [modal.includes("event.key === 'Escape'"), 'Media preview cannot close with Escape'],
  [controls.includes("Create from a reference"), 'Image setup copy does not explain the real task'],
];
const failures = checks.filter(([ok]) => !ok).map(([, message]) => message);
if (failures.length) {
  console.error(`UI/UX benchmark contract failed:\n- ${failures.join('\n- ')}`);
  process.exit(1);
}
console.log('UI/UX benchmark contract passed.');
""", encoding='utf-8')

package = Path('apps/studio/package.json')
text = package.read_text(encoding='utf-8')
needle = 'node scripts/check-ui-audit-contract.mjs && node scripts/check-generation-lifecycle-contract.mjs'
replacement = 'node scripts/check-ui-audit-contract.mjs && node scripts/check-ui-ux-benchmark-contract.mjs && node scripts/check-generation-lifecycle-contract.mjs'
if text.count(needle) != 1:
    raise RuntimeError(f'package build contract hook: expected 1 match, found {text.count(needle)}')
package.write_text(text.replace(needle, replacement, 1), encoding='utf-8')

print('Studio UI/UX benchmark patch applied.')
