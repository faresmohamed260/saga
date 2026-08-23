import React from 'react';
import LibraryHeader from '../../components/LibraryHeader.jsx';

export default function ModelsView() {
  return (
    <section className="history-view">
      <LibraryHeader eyebrow="Studio" title="Models" description="Models exposed to the generation registry. Only live backends are selectable in production." />
      <div className="collection-grid"><article className="collection-card" style={{ padding: 18 }}><div className="history-eyebrow">LIVE</div><h3 style={{ margin: '8px 0' }}>FLUX.2 Klein 9B · DarkBeast V2 BFS</h3><p style={{ color: '#8f98a8', fontSize: 12, lineHeight: 1.6 }}>Image editing with automatic output sizing and multi-reference conditioning.</p></article><article className="collection-card" style={{ padding: 18 }}><div className="history-eyebrow">PLANNED</div><h3 style={{ margin: '8px 0' }}>SAGA Image</h3><p style={{ color: '#8f98a8', fontSize: 12, lineHeight: 1.6 }}>Original image generation UI presets are ready; the production workflow will be connected separately.</p></article></div>
    </section>
  );
}
