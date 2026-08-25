import React from 'react';
import { SlidersHorizontal } from 'lucide-react';
import LibraryHeader from '../../components/LibraryHeader.jsx';

export default function SettingsView({ onOpenGenerationSettings }) {
  return (
    <section className="history-view">
      <LibraryHeader eyebrow="Studio" title="Settings" description="Generation controls stay beside the composer so every option is scoped to the active production workflow." action={<button type="button" className="secondary-button" onClick={onOpenGenerationSettings}><SlidersHorizontal size={18}/> Open generation settings</button>} />
      <div className="history-state">Advanced exposes the live workflow's seed, sampling controls, negative prompt, and model-specific output controls. Resolution, duration, and audio remain next to the composer when they are primary generation choices.</div>
    </section>
  );
}
