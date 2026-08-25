import React from 'react';
import LibraryHeader from '../../components/LibraryHeader.jsx';

const models = [
  { name: 'FLUX.2 Klein 9B', detail: 'Reference-based image editing with manual/automatic canvas sizing and multi-reference conditioning.' },
  { name: 'REDGraft LTX 2.5', detail: 'Text-to-video and image-to-video generation with resolution, duration, audio, aspect ratio, frame rate, seed, and CFG controls.' },
];

export default function ModelsView() {
  return (
    <section className="history-view">
      <LibraryHeader eyebrow="Studio" title="Models" description="Production models currently exposed by the Studio generation registry." />
      <div className="collection-grid">
        {models.map((model) => <article className="collection-card" style={{ padding: 18 }} key={model.name}><div className="history-eyebrow">LIVE</div><h3 style={{ margin: '8px 0' }}>{model.name}</h3><p style={{ color: '#8f98a8', fontSize: 12, lineHeight: 1.6 }}>{model.detail}</p></article>)}
      </div>
    </section>
  );
}
