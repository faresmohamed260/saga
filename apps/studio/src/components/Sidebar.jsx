import React, { useEffect, useRef } from 'react';
import { Box, ChevronLeft, Folder, Heart, Images, LoaderCircle, Settings, WandSparkles, Workflow } from 'lucide-react';

const primary = [[WandSparkles, 'Create'], [LoaderCircle, 'Jobs'], [Images, 'Gallery'], [Heart, 'Favorites'], [Folder, 'Collections']];
const secondary = [[Box, 'Models'], [Workflow, 'Workflows']];

function NavItem({ icon: Icon, label, active, onClick, title }) {
  return <button type="button" className={`nav-item ${active ? 'active' : ''}`} onClick={onClick} title={title} aria-current={active ? 'page' : undefined}><Icon size={19} strokeWidth={1.8}/><span>{label}</span></button>;
}

export default function Sidebar({ section, open, onClose, onSectionChange }) {
  const sidebarRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const handlePointerDown = (event) => {
      if (sidebarRef.current?.contains(event.target)) return;
      if (event.target?.closest?.('[data-navigation-trigger="true"]')) return;
      onClose();
    };
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [open, onClose]);

  const chooseSection = (label) => {
    onSectionChange(label);
    onClose();
  };

  return (
    <aside
      ref={sidebarRef}
      className={`sidebar ${open ? 'open' : ''}`}
      aria-hidden={!open}
      onBlurCapture={(event) => {
        const next = event.relatedTarget;
        if (next && !sidebarRef.current?.contains(next)) onClose();
      }}
    >
      <div className="brand-row"><div className="brand-mark">S</div><div className="brand-text">SAGA <span>Studio</span></div><button type="button" className="mobile-close" aria-label="Close navigation" onClick={onClose}><ChevronLeft size={19}/></button></div>
      <nav className="nav-group primary-nav" aria-label="Primary navigation">
        {primary.map(([Icon, label]) => <NavItem key={label} icon={Icon} label={label} active={section === label} onClick={() => chooseSection(label)} />)}
      </nav>
      <div className="nav-divider" />
      <nav className="nav-group" aria-label="Catalog navigation">{secondary.map(([Icon, label]) => <NavItem key={label} icon={Icon} label={label} active={section === label} onClick={() => chooseSection(label)} />)}</nav>
      <div className="nav-divider" />
      <NavItem icon={Settings} label="Settings" active={section === 'Settings'} onClick={() => chooseSection('Settings')} />
      <div className="profile-card sidebar-workspace-card">
        <div className="avatar-orb"/>
        <div className="profile-copy">
          <div className="profile-name">Studio workspace</div>
          <div className="profile-email">Status in Jobs &amp; Models</div>
        </div>
      </div>
    </aside>
  );
}
