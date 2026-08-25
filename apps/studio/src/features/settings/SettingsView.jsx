import React from 'react';
import { SlidersHorizontal } from 'lucide-react';
import LibraryHeader from '../../components/LibraryHeader.jsx';

export default function SettingsView({ onOpenGenerationSettings }) {
  return (
    <section className="history-view">
      <LibraryHeader eyebrow="Studio" title="Studio settings" description="This surface only points to settings Studio currently owns. Generation parameters stay beside the composer and follow the active production workflow." action={<button type="button" className="secondary-button" onClick={onOpenGenerationSettings}><SlidersHorizontal size={18}/> Open generation settings</button>} />
      <div className="history-state">Advanced exposes the live workflow's seed, sampling controls, negative prompt, and model-specific output controls. Resolution, duration, framing, frame rate, and audio remain in the generation workspace where their effect is visible.</div>
    </section>
  );
}
