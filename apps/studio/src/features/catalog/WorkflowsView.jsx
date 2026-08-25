import React from 'react';
import LibraryHeader from '../../components/LibraryHeader.jsx';

const workflows = [
  {
    name: 'Klein Multi-Reference Edit',
    mode: 'Image edit',
    detail: 'Transform one or more image references with prompt mentions, reference-derived Auto canvas sizing, or a manually selected canvas.',
    path: 'Direct source references → Studio orchestration → FLUX.2 Klein worker fleet → persisted image and thumbnail.',
  },
  {
    name: 'LTX 2.5 Two-Stage Video',
    mode: 'Video',
    detail: 'Generate text-to-video or animate a reference image with selectable aspect, delivery resolution, duration, frame rate, audio, seed, and CFG.',
    path: 'Optional source reference → Studio orchestration → REDGraft LTX worker fleet → persisted MP4 and poster.',
  },
];

export default function WorkflowsView() {
  return (
    <section className="history-view">
      <LibraryHeader eyebrow="Production capability" title="Production workflows" description="Registered generation paths are shown in terms of what Studio can actually produce today." />
      <div className="collection-grid">
        {workflows.map((workflow) => (
          <article className="collection-card" style={{ padding: 18 }} key={workflow.name}>
            <div className="history-eyebrow">LIVE · {workflow.mode.toUpperCase()}</div>
            <h3 style={{ margin: '8px 0' }}>{workflow.name}</h3>
            <p style={{ color: '#a5adba', fontSize: 12, lineHeight: 1.6 }}>{workflow.detail}</p>
            <details style={{ color: '#707a8b', fontSize: 11, lineHeight: 1.6, marginTop: 12 }}>
              <summary style={{ cursor: 'pointer', width: 'fit-content' }}>Technical path</summary>
              <p style={{ margin: '7px 0 0' }}>{workflow.path}</p>
            </details>
          </article>
        ))}
      </div>
    </section>
  );
}
