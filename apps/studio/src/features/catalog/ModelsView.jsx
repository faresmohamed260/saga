import React from 'react';
import { ArrowRight } from 'lucide-react';
import LibraryHeader from '../../components/LibraryHeader.jsx';

const models = [
  {
    name: 'FLUX.2 Klein 9B',
    mode: 'Edit',
    createMode: 'Image',
    detail: 'Reference-based image transformation with multi-reference prompting plus automatic or manual output canvas sizing.',
    controls: 'Seed · steps · CFG · negative prompt · canvas',
    input: 'Reference required',
    action: 'Start image edit',
  },
  {
    name: 'REDGraft LTX 2.5',
    mode: 'Video',
    createMode: 'Video',
    detail: 'Text-to-video and image-to-video generation with production delivery controls for framing, timing, motion output, and audio.',
    controls: 'Resolution · duration · audio · aspect · 24/25/30 fps · seed · CFG',
    input: 'Reference optional',
    action: 'Create video',
  },
];

export default function ModelsView({ onUseModel }) {
  return (
    <section className="history-view">
      <LibraryHeader eyebrow="Production capability" title="Production models" description="Only models that currently back a usable Studio generation path are listed here. Start from a model to enter the matching Create flow." />
      <div className="collection-grid">
        {models.map((model) => (
          <article className="collection-card" style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 10 }} key={model.name}>
            <div className="history-eyebrow">LIVE · {model.mode.toUpperCase()}</div>
            <h3 style={{ margin: 0 }}>{model.name}</h3>
            <p style={{ color: '#a5adba', fontSize: 12, lineHeight: 1.6, margin: 0 }}>{model.detail}</p>
            <p style={{ color: '#707a8b', fontSize: 11, lineHeight: 1.6, margin: 0 }}>Controls: {model.controls}</p>
            <div style={{ marginTop: 'auto', paddingTop: 6, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
              <span className="history-eyebrow" style={{ letterSpacing: '.05em' }}>{model.input}</span>
              <button type="button" className="secondary-button" onClick={() => onUseModel?.(model.createMode)}>
                {model.action}<ArrowRight size={16}/>
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
