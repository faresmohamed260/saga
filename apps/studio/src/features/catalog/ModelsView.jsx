import React from 'react';
import LibraryHeader from '../../components/LibraryHeader.jsx';

const models = [
  { name: 'FLUX.2 Klein 9B', mode: 'Edit', detail: 'Reference-based image transformation with multi-reference prompting plus automatic or manual output canvas sizing.', controls: 'Seed · steps · CFG · negative prompt · canvas' },
  { name: 'REDGraft LTX 2.5', mode: 'Video', detail: 'Text-to-video and image-to-video generation with production delivery controls for framing, timing, motion output, and audio.', controls: 'Resolution · duration · audio · aspect · 24/25/30 fps · seed · CFG' },
];

export default function ModelsView() {
  return (
    <section className="history-view">
      <LibraryHeader eyebrow="Production capability" title="Production models" description="Only models that currently back a usable Studio generation path are listed here." />
      <div className="collection-grid">
        {models.map((model) => (
          <article className="collection-card" style={{ padding: 18 }} key={model.name}>
            <div className="history-eyebrow">LIVE · {model.mode.toUpperCase()}</div>
            <h3 style={{ margin: '8px 0' }}>{model.name}</h3>
            <p style={{ color: '#a5adba', fontSize: 12, lineHeight: 1.6 }}>{model.detail}</p>
            <p style={{ color: '#707a8b', fontSize: 11, lineHeight: 1.6, marginTop: 12 }}>Controls: {model.controls}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
