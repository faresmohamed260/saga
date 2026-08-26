import React from 'react';
import { Menu, SlidersHorizontal } from 'lucide-react';

export default function MobileTopbar({ onOpenNavigation, onOpenSettings, navigationOpen = false }) {
  return (
    <div className="mobile-topbar">
      <button className="icon-button" type="button" data-navigation-trigger="true" aria-label="Open navigation" aria-expanded={navigationOpen} onClick={onOpenNavigation}><Menu size={20}/></button>
      <div className="mobile-brand">SAGA Studio</div>
      <button className="icon-button" type="button" aria-label="Open generation settings" onClick={onOpenSettings}><SlidersHorizontal size={20}/></button>
    </div>
  );
}
