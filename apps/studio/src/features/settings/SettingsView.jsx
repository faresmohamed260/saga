import React from 'react';
import { SlidersHorizontal } from 'lucide-react';
import LibraryHeader from '../../components/LibraryHeader.jsx';

export default function SettingsView({ onOpenGenerationSettings }) {
  return (
    <section className="history-view">
      <LibraryHeader eyebrow="Studio" title="Settings" description="Generation settings live beside the composer so they stay contextual to the selected workflow." action={<button className="secondary-button" onClick={onOpenGenerationSettings}><SlidersHorizontal size={18}/> Open generation settings</button>} />
      <div className="history-state">Use the settings panel to control model, aspect ratio, resolution, seed, steps, CFG, and workflow.</div>
    </section>
  );
}
