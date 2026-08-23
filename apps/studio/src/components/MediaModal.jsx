import React from 'react';
import { X } from 'lucide-react';

export default function MediaModal({ item, onClose }) {
  if (!item) return null;
  return (
    <div className="media-modal" onClick={onClose}>
      <div className="media-modal-card" onClick={(event) => event.stopPropagation()}>
        <button className="media-modal-close" onClick={onClose}><X size={20}/></button>
        {item.kind === 'video' ? <video src={item.originalUrl} poster={item.thumbnailUrl || undefined} controls playsInline /> : <img src={item.originalUrl || item.url} alt={item.title || 'Generated image'} />}
        <div className="media-modal-copy"><strong>{item.title || 'Generated media'}</strong><span>{item.model || ''}{item.seed != null ? ` · Seed ${item.seed}` : ''}</span></div>
      </div>
    </div>
  );
}
