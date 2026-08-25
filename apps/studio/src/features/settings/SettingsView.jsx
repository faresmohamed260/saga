import React from 'react';
import { SlidersHorizontal } from 'lucide-react';
import LibraryHeader from '../../components/LibraryHeader.jsx';

const rows = [
  {
    label: 'Output controls',
    value: 'Aspect, resolution, duration, frame rate, and audio stay beside the Create prompt so their effect is visible before generation.',
  },
  {
    label: 'Advanced controls',
    value: 'Seed, sampling, CFG, negative prompt, and model-specific controls follow the active production workflow in Advanced.',
  },
];

export default function SettingsView({ onOpenGenerationSettings }) {
  return (
    <section className="history-view">
      <LibraryHeader
        eyebrow="Studio"
        title="Studio settings"
        description="Studio keeps generation controls close to the work they affect instead of duplicating them into disconnected global preferences."
      />
      <div className="collection-grid" style={{ maxWidth: 760 }}>
        <article className="collection-card" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16 }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              <div className="history-eyebrow">GENERATION</div>
              <h3 style={{ margin: 0 }}>Generation controls</h3>
            </div>
            <SlidersHorizontal size={20} aria-hidden="true" style={{ flex: '0 0 auto' }} />
          </div>

          <div style={{ display: 'grid', gap: 12 }}>
            {rows.map((row) => (
              <div key={row.label} style={{ display: 'grid', gridTemplateColumns: 'minmax(120px, .4fr) minmax(0, 1fr)', gap: 16, paddingTop: 12, borderTop: '1px solid rgba(255,255,255,.07)' }}>
                <strong style={{ fontSize: 12 }}>{row.label}</strong>
                <span style={{ color: '#8f98a8', fontSize: 12, lineHeight: 1.55 }}>{row.value}</span>
              </div>
            ))}
          </div>

          <div style={{ paddingTop: 2 }}>
            <button type="button" className="secondary-button" onClick={onOpenGenerationSettings}>
              <SlidersHorizontal size={17}/> Open generation settings
            </button>
          </div>
        </article>
      </div>
    </section>
  );
}
