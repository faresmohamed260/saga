import React from 'react';
import { X } from 'lucide-react';
import { modelDisplayName, modelImplementationLabel } from '../model-labels.js';

export default function MediaModal({ item, onClose }) {
  if (!item) return null;
  const implementation = modelImplementationLabel(item.model);
  const displayModel = modelDisplayName(item.model);
  return (
    <div className="media-modal" onClick={onClose}>
      <div className="media-modal-card" onClick={(event) => event.stopPropagation()}>
        <button className="media-modal-close" onClick={onClose}><X size={20}/></button>
        {item.kind === 'video' ? <video src={item.originalUrl} poster={item.thumbnailUrl || undefined} controls playsInline /> : <img src={item.originalUrl || item.url} alt={item.title || 'Generated image'} />}
        <div className="media-modal-copy">
          <strong>{item.title || 'Generated media'}</strong>
          <span>{[displayModel !== 'Unknown model' ? displayModel : null, item.resolution, item.aspectRatio, item.frameRate ? `${item.frameRate}fps` : null].filter(Boolean).join(' · ')}</span>
          <details className="media-modal-details">
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
      </div>
    </div>
  );
}
