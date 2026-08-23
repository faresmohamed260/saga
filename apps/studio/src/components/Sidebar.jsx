import React from 'react';
import { Box, ChevronDown, ChevronLeft, Folder, Heart, Images, LoaderCircle, Settings, Sparkles, WandSparkles, Workflow } from 'lucide-react';

const primary = [[WandSparkles, 'Create'], [LoaderCircle, 'Jobs'], [Images, 'Gallery'], [Heart, 'Favorites'], [Folder, 'Collections']];
const secondary = [[Box, 'Models'], [Workflow, 'Workflows']];

function NavItem({ icon: Icon, label, active, onClick }) {
  return <button className={`nav-item ${active ? 'active' : ''}`} onClick={onClick}><Icon size={19} strokeWidth={1.8}/><span>{label}</span></button>;
}

export default function Sidebar({ section, mode, mobileOpen, onCloseMobile, onSectionChange, onModeChange, onClearError }) {
  const chooseSection = (label) => {
    onSectionChange(label);
    if (label === 'Create' && mode === 'More') onModeChange('Image');
    onCloseMobile();
  };

  return (
    <aside className={`sidebar ${mobileOpen ? 'open' : ''}`}>
      <div className="brand-row"><div className="brand-mark">S</div><div className="brand-text">SAGA <span>Studio</span></div><button className="mobile-close" onClick={onCloseMobile}><ChevronLeft size={19}/></button></div>
      <nav className="nav-group primary-nav">
        {primary.map(([Icon, label]) => <NavItem key={label} icon={Icon} label={label} active={section === label && (label !== 'Create' || mode !== 'More')} onClick={() => chooseSection(label)} />)}
        <NavItem icon={Sparkles} label="More" active={section === 'Create' && mode === 'More'} onClick={() => { onSectionChange('Create'); onModeChange('More'); onClearError(); onCloseMobile(); }} />
      </nav>
      <div className="nav-divider" />
      <nav className="nav-group">{secondary.map(([Icon, label]) => <NavItem key={label} icon={Icon} label={label} active={section === label} onClick={() => chooseSection(label)} />)}</nav>
      <div className="nav-divider" />
      <NavItem icon={Settings} label="Settings" active={section === 'Settings'} onClick={() => onSectionChange('Settings')} />
      <div className="profile-card"><div className="avatar-orb"/><div className="profile-copy"><div className="profile-name">Saga Creator <span className="pro-badge">Studio</span></div><div className="profile-email">FLUX.2 online</div></div><ChevronDown size={16}/></div>
    </aside>
  );
}
