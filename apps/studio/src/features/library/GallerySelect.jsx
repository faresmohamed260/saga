import React from 'react';
import { Check, ChevronDown } from 'lucide-react';

export default function GallerySelect({ value, options, onChange, ariaLabel, className = '' }) {
  const [open, setOpen] = React.useState(false);
  const rootRef = React.useRef(null);
  const buttonRef = React.useRef(null);
  const selected = options.find((option) => option.value === value) || options[0];

  React.useEffect(() => {
    if (!open) return undefined;
    const onPointerDown = (event) => {
      if (!rootRef.current?.contains(event.target)) setOpen(false);
    };
    const onKeyDown = (event) => {
      if (event.key !== 'Escape') return;
      setOpen(false);
      window.setTimeout(() => buttonRef.current?.focus(), 0);
    };
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  const choose = (nextValue) => {
    onChange(nextValue);
    setOpen(false);
    window.setTimeout(() => buttonRef.current?.focus(), 0);
  };

  return (
    <div ref={rootRef} className={`gallery-menu-select ${className} ${open ? 'open' : ''}`}>
      <select className="gallery-menu-select-metadata" value={value} onChange={(event) => onChange(event.target.value)} tabIndex={-1} aria-hidden="true">
        {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
      <button
        ref={buttonRef}
        type="button"
        className="gallery-menu-select-trigger"
        aria-label={ariaLabel}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        <span>{selected?.label || value}</span>
        <ChevronDown size={14}/>
      </button>
      {open && (
        <div className="gallery-menu-select-popover" role="menu" aria-label={ariaLabel}>
          {options.map((option) => (
            <button
              key={option.value}
              type="button"
              role="menuitemradio"
              aria-checked={option.value === value}
              className={option.value === value ? 'selected' : ''}
              onClick={() => choose(option.value)}
            >
              <span>{option.label}</span>
              {option.value === value && <Check size={15}/>} 
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
