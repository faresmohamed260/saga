import React from 'react';
import { Menu, SlidersHorizontal } from 'lucide-react';

export default function MobileTopbar({ onOpenNavigation, onOpenSettings }) {
  return (
    <div className="mobile-topbar">
      <button className="icon-button" onClick={onOpenNavigation}><Menu size={20}/></button>
      <div className="mobile-brand">SAGA Studio</div>
      <button className="icon-button" onClick={onOpenSettings}><SlidersHorizontal size={20}/></button>
    </div>
  );
}
