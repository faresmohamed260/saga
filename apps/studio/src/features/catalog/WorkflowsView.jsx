import React from 'react';
import LibraryHeader from '../../components/LibraryHeader.jsx';

const workflows = [
  { name: 'Klein Multi-Reference Edit', detail: 'Direct R2 references → Studio orchestration → FLUX.2 Klein worker fleet → persisted R2 image and thumbnail.' },
  { name: 'LTX 2.5 Two-Stage Video', detail: 'Optional R2 image reference → Studio orchestration → REDGraft LTX worker fleet → persisted MP4 and poster.' },
];

export default function WorkflowsView() {
  return (
    <section className="history-view">
      <LibraryHeader eyebrow="Studio" title="Workflows" description="Registered production generation paths and their current capabilities." />
      <div className="collection-grid">{workflows.map((workflow) => <article className="collection-card" style={{ padding: 18 }} key={workflow.name}><div className="history-eyebrow">LIVE</div><h3 style={{ margin: '8px 0' }}>{workflow.name}</h3><p style={{ color: '#8f98a8', fontSize: 12, lineHeight: 1.6 }}>{workflow.detail}</p></article>)}</div>
    </section>
  );
}
