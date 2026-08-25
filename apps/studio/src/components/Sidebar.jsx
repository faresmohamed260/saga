import React from 'react';
import { Box, ChevronLeft, Folder, Heart, Images, LoaderCircle, Settings, WandSparkles, Workflow } from 'lucide-react';

const primary = [[WandSparkles, 'Create'], [LoaderCircle, 'Jobs'], [Images, 'Gallery'], [Heart, 'Favorites'], [Folder, 'Collections']];
const secondary = [[Box, 'Models'], [Workflow, 'Workflows']];

function NavItem({ icon: Icon, label, active, onClick, title }) {
  return <button type="button" className={`nav-item ${active ? 'active' : ''}`} onClick={onClick} title={title} aria-current={active ? 'page' : undefined}><Icon size={19} strokeWidth={1.8}/><span>{label}</span></button>;
}

export default function Sidebar({ section, mobileOpen, onCloseMobile, onSectionChange }) {
  const chooseSection = (label) => {
    onSectionChange(label);
    onCloseMobile();
  };

  return (
    <aside className={`sidebar ${mobileOpen ? 'open' : ''}`}>
      <div className="brand-row"><div className="brand-mark">S</div><div className="brand-text">SAGA <span>Studio</span></div><button type="button" className="mobile-close" aria-label="Close navigation" onClick={onCloseMobile}><ChevronLeft size={19}/></button></div>
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
