import React from 'react';
import {
  ArrowDownUp,
  ArrowLeft,
  Check,
  Download,
  Heart,
  Image as ImageIcon,
  LayoutGrid,
  LoaderCircle,
  MoreHorizontal,
  Pencil,
  Plus,
  SlidersHorizontal,
  Trash2,
  Upload,
  Video,
  X,
} from 'lucide-react';
import '../../uploads-library.css';

const MAX_BYTES = 25 * 1024 * 1024;
const SUPPORTED_TYPES = new Set(['image/png', 'image/jpeg', 'image/webp']);
const DENSITY_KEY = 'saga.uploadsDensity';

async function readError(response, fallback) {
  try {
    const payload = await response.json();
    if (payload?.error) return payload.error;
  } catch {}
  return `${fallback} (${response.status})`;
}

async function imageDimensions(file) {
  if (typeof createImageBitmap === 'function') {
    try {
      const bitmap = await createImageBitmap(file);
      const result = { width: bitmap.width || 0, height: bitmap.height || 0 };
      bitmap.close?.();
      return result;
    } catch {}
  }
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      resolve({ width: image.naturalWidth || 0, height: image.naturalHeight || 0 });
      URL.revokeObjectURL(url);
    };
    image.onerror = () => {
      resolve({ width: 0, height: 0 });
      URL.revokeObjectURL(url);
    };
    image.src = url;
  });
}

function triggerDownload(asset) {
  const anchor = document.createElement('a');
  anchor.href = asset.downloadUrl || asset.url;
  anchor.download = asset.filename || asset.name || 'upload';
  anchor.rel = 'noopener';
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
}

function UploadAssetModal({ asset, onClose, onFavorite, onRename, onDelete, onUseReference }) {
  const [menuOpen, setMenuOpen] = React.useState(false);

  React.useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  if (!asset) return null;
  return (
    <div className="upload-detail-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="upload-detail" role="dialog" aria-modal="true" aria-label={`Preview ${asset.name}`}>
        <header className="upload-detail-header">
          <div className="upload-detail-title">
            <button type="button" className="upload-detail-back" aria-label="Back to uploads" onClick={onClose}><ArrowLeft size={19}/></button>
            <strong title={asset.name}>{asset.name}</strong>
            <button type="button" className="upload-detail-rename" aria-label="Rename upload" onClick={() => onRename(asset)}><Pencil size={16}/></button>
          </div>
          <div className="upload-detail-actions">
            <button type="button" className={asset.favorite ? 'active' : ''} aria-label={asset.favorite ? 'Remove from favorites' : 'Add to favorites'} aria-pressed={asset.favorite} onClick={() => onFavorite(asset)}><Heart size={19} fill={asset.favorite ? 'currentColor' : 'none'}/></button>
            <div className="upload-detail-menu-wrap">
              <button type="button" aria-label="More upload actions" aria-expanded={menuOpen} onClick={() => setMenuOpen((value) => !value)}><MoreHorizontal size={20}/></button>
              {menuOpen && <div className="upload-detail-menu" role="menu">
                <button type="button" role="menuitem" onClick={() => { triggerDownload(asset); setMenuOpen(false); }}><Download size={16}/>Download</button>
                <button type="button" role="menuitem" onClick={() => { setMenuOpen(false); onRename(asset); }}><Pencil size={16}/>Rename</button>
                <button type="button" role="menuitem" className="danger" onClick={() => { setMenuOpen(false); onDelete(asset); }}><Trash2 size={16}/>Delete</button>
              </div>}
            </div>
            <button type="button" aria-label="Close upload preview" onClick={onClose}><X size={20}/></button>
          </div>
        </header>

        <div className="upload-detail-stage">
          <img src={asset.url} alt={asset.name} draggable="false" />
        </div>

        <div className="upload-detail-cta">
          <button type="button" onClick={() => onUseReference(asset, 'Edit')}><ImageIcon size={17}/>Set as Reference</button>
          <button type="button" onClick={() => onUseReference(asset, 'Video')}><Video size={17}/>Generate Video</button>
        </div>
      </section>
    </div>
  );
}

function UploadCard({ asset, managing, selected, onSelect, onOpen, onFavorite, onRename, onDelete }) {
  const [menuOpen, setMenuOpen] = React.useState(false);
  const activate = () => managing ? onSelect(asset.id) : onOpen(asset);
  return (
    <article className={`upload-asset-card ${selected ? 'selected' : ''}`}>
      <button type="button" className="upload-asset-primary" onClick={activate} aria-label={managing ? `${selected ? 'Deselect' : 'Select'} ${asset.name}` : `Open ${asset.name}`} aria-pressed={managing ? selected : undefined}>
        <img src={asset.url} alt="" loading="lazy" draggable="false" />
      </button>
      {managing ? (
        <span className={`upload-selection-mark ${selected ? 'selected' : ''}`} aria-hidden="true">{selected && <Check size={15}/>}</span>
      ) : (
        <>
          <button type="button" className={`upload-favorite ${asset.favorite ? 'active' : ''}`} aria-label={asset.favorite ? `Unfavorite ${asset.name}` : `Favorite ${asset.name}`} aria-pressed={asset.favorite} onClick={() => onFavorite(asset)}><Heart size={17} fill={asset.favorite ? 'currentColor' : 'none'}/></button>
          <div className="upload-card-menu-wrap">
            <button type="button" className="upload-card-menu-trigger" aria-label={`More actions for ${asset.name}`} aria-expanded={menuOpen} onClick={() => setMenuOpen((value) => !value)}><MoreHorizontal size={18}/></button>
            {menuOpen && <div className="upload-card-menu" role="menu">
              <button type="button" role="menuitem" onClick={() => { setMenuOpen(false); onRename(asset); }}><Pencil size={15}/>Rename</button>
              <button type="button" role="menuitem" onClick={() => { setMenuOpen(false); triggerDownload(asset); }}><Download size={15}/>Download</button>
              <button type="button" role="menuitem" className="danger" onClick={() => { setMenuOpen(false); onDelete(asset); }}><Trash2 size={15}/>Delete</button>
            </div>}
          </div>
        </>
      )}
      <div className="upload-card-caption" title={asset.name}>{asset.name}</div>
    </article>
  );
}

export default function UploadsView({ search, onSearchChange, onUseReference }) {
  const inputRef = React.useRef(null);
  const [items, setItems] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState('');
  const [uploading, setUploading] = React.useState(0);
  const [sort, setSort] = React.useState('newest');
  const [favoritesOnly, setFavoritesOnly] = React.useState(false);
  const [managing, setManaging] = React.useState(false);
  const [selected, setSelected] = React.useState(new Set());
  const [selectedAsset, setSelectedAsset] = React.useState(null);
  const [mobileFiltersOpen, setMobileFiltersOpen] = React.useState(false);
  const [actionBusy, setActionBusy] = React.useState('');
  const [density, setDensity] = React.useState(() => {
    try { return window.localStorage.getItem(DENSITY_KEY) === 'comfortable' ? 'comfortable' : 'compact'; }
    catch { return 'compact'; }
  });

  const loadUploads = React.useCallback(async ({ silent = false } = {}) => {
    if (!silent) setLoading(true);
    try {
      const params = new URLSearchParams({ limit: '100', sort });
      if (favoritesOnly) params.set('favorite', 'true');
      if (search?.trim()) params.set('search', search.trim());
      const response = await fetch(`/api/uploads?${params.toString()}`, { headers: { Accept: 'application/json' }, cache: 'no-store' });
      if (!response.ok) throw new Error(await readError(response, 'Could not load uploads'));
      const payload = await response.json();
      setItems(Array.isArray(payload?.items) ? payload.items : []);
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load uploads.');
    } finally {
      if (!silent) setLoading(false);
    }
  }, [favoritesOnly, search, sort]);

  React.useEffect(() => { loadUploads(); }, [loadUploads]);

  React.useEffect(() => {
    const refresh = () => { if (document.visibilityState === 'visible') loadUploads({ silent: true }); };
    const timer = window.setInterval(refresh, 5000);
    window.addEventListener('focus', refresh);
    document.addEventListener('visibilitychange', refresh);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener('focus', refresh);
      document.removeEventListener('visibilitychange', refresh);
    };
  }, [loadUploads]);

  React.useEffect(() => {
    const ids = new Set(items.map((item) => item.id));
    setSelected((current) => new Set([...current].filter((id) => ids.has(id))));
    if (selectedAsset) {
      const fresh = items.find((item) => item.id === selectedAsset.id);
      if (fresh) setSelectedAsset(fresh);
    }
  }, [items]);

  const changeDensity = (next) => {
    setDensity(next);
    try { window.localStorage.setItem(DENSITY_KEY, next); } catch {}
  };

  const uploadFiles = async (fileList) => {
    const files = Array.from(fileList || []);
    if (!files.length) return;
    setUploading(files.length);
    setError('');
    try {
      for (const file of files) {
        if (!SUPPORTED_TYPES.has(file.type)) throw new Error(`${file.name} is not PNG, JPEG, or WebP.`);
        if (!file.size || file.size > MAX_BYTES) throw new Error(`${file.name} must be smaller than 25 MB.`);
        const dimensions = await imageDimensions(file);
        const ticketResponse = await fetch('/api/uploads', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ filename: file.name, contentType: file.type, size: file.size, purpose: 'library-upload' }),
        });
        if (!ticketResponse.ok) throw new Error(await readError(ticketResponse, 'Could not prepare upload'));
        const ticket = await ticketResponse.json();
        const putResponse = await fetch(ticket.uploadUrl, { method: 'PUT', headers: { 'Content-Type': ticket.contentType || file.type }, body: file });
        if (!putResponse.ok) throw new Error(`Direct upload failed for ${file.name} (${putResponse.status})`);
        const completeResponse = await fetch('/api/uploads', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ phase: 'complete', key: ticket.key, filename: file.name, displayName: file.name.replace(/\.[^.]+$/, ''), contentType: file.type, size: file.size, ...dimensions }),
        });
        if (!completeResponse.ok) throw new Error(await readError(completeResponse, 'Could not save upload'));
        setUploading((count) => Math.max(0, count - 1));
      }
      await loadUploads();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed.');
    } finally {
      setUploading(0);
      if (inputRef.current) inputRef.current.value = '';
    }
  };

  const patchAsset = async (asset, patch) => {
    const response = await fetch('/api/uploads', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: asset.id, ...patch }) });
    if (!response.ok) throw new Error(await readError(response, 'Could not update upload'));
    const payload = await response.json();
    setItems((current) => current.map((item) => item.id === asset.id ? payload.item : item));
    return payload.item;
  };

  const toggleFavorite = async (asset) => {
    try { await patchAsset(asset, { favorite: !asset.favorite }); }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not update favorite.'); }
  };

  const renameAsset = async (asset) => {
    const next = window.prompt('Rename upload', asset.name);
    if (next == null || !next.trim() || next.trim() === asset.name) return;
    try { await patchAsset(asset, { displayName: next.trim() }); }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not rename upload.'); }
  };

  const deleteAsset = async (asset, { skipConfirm = false } = {}) => {
    if (!skipConfirm && !window.confirm(`Delete “${asset.name}” permanently?`)) return false;
    const response = await fetch(`/api/uploads?id=${encodeURIComponent(asset.id)}`, { method: 'DELETE' });
    if (!response.ok) throw new Error(await readError(response, 'Could not delete upload'));
    setItems((current) => current.filter((item) => item.id !== asset.id));
    setSelected((current) => { const next = new Set(current); next.delete(asset.id); return next; });
    if (selectedAsset?.id === asset.id) setSelectedAsset(null);
    return true;
  };

  const removeAsset = async (asset) => {
    try { await deleteAsset(asset); }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not delete upload.'); }
  };

  const toggleSelected = (id) => setSelected((current) => {
    const next = new Set(current);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  const exitManage = () => { setManaging(false); setSelected(new Set()); };

  const runBulk = async (action) => {
    const chosen = items.filter((item) => selected.has(item.id));
    if (!chosen.length || actionBusy) return;
    if (action === 'delete' && !window.confirm(`Delete ${chosen.length} selected upload${chosen.length === 1 ? '' : 's'} permanently?`)) return;
    setActionBusy(action);
    setError('');
    try {
      if (action === 'download') {
        chosen.forEach((asset, index) => window.setTimeout(() => triggerDownload(asset), index * 180));
      } else if (action === 'favorite') {
        await Promise.all(chosen.map((asset) => patchAsset(asset, { favorite: true })));
      } else if (action === 'delete') {
        for (const asset of chosen) await deleteAsset(asset, { skipConfirm: true });
      }
      if (action !== 'download') await loadUploads({ silent: true });
      if (action === 'delete') exitManage();
    } catch (err) {
      setError(err instanceof Error ? err.message : `Could not ${action} selected uploads.`);
    } finally {
      setActionBusy('');
    }
  };

  const useReference = async (asset, targetMode) => {
    try {
      await onUseReference?.(asset, targetMode);
      setSelectedAsset(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not use this upload as a reference.');
    }
  };

  return (
    <div className={`uploads-library uploads-density-${density}`}>
      <div className="uploads-desktop-controls">
        <div className="uploads-filter-strip">
          <button type="button" className={!favoritesOnly ? 'selected' : ''} onClick={() => setFavoritesOnly(false)}>All</button>
          <label><input type="checkbox" checked={favoritesOnly} onChange={(event) => setFavoritesOnly(event.target.checked)}/><Heart size={15} fill={favoritesOnly ? 'currentColor' : 'none'}/><span>Favorites</span></label>
        </div>
        <div className="uploads-view-strip">
          <button type="button" className={managing ? 'active' : ''} onClick={() => managing ? exitManage() : setManaging(true)}>{managing ? <X size={16}/> : <Check size={16}/>}<span>{managing ? 'Exit Batch Selection' : 'Batch Actions'}</span></button>
          <label><ArrowDownUp size={15}/><span className="sr-only">Sort uploads</span><select aria-label="Sort uploads" value={sort} onChange={(event) => setSort(event.target.value)}><option value="newest">Newest</option><option value="oldest">Oldest</option></select></label>
          <div className="uploads-density" role="group" aria-label="Upload card density"><LayoutGrid size={15}/><button type="button" className={density === 'compact' ? 'selected' : ''} onClick={() => changeDensity('compact')}>Compact</button><button type="button" className={density === 'comfortable' ? 'selected' : ''} onClick={() => changeDensity('comfortable')}>Comfortable</button></div>
        </div>
      </div>

      <div className="uploads-mobile-controls" aria-label="Uploads controls">
        <button type="button" className={mobileFiltersOpen || favoritesOnly ? 'active' : ''} aria-expanded={mobileFiltersOpen} onClick={() => setMobileFiltersOpen((value) => !value)}><SlidersHorizontal size={19}/><span>Filter</span></button>
        <label><ArrowDownUp size={19}/><span>Sort</span><select aria-label="Mobile upload sort" value={sort} onChange={(event) => setSort(event.target.value)}><option value="newest">Newest</option><option value="oldest">Oldest</option></select></label>
        <button type="button" onClick={() => changeDensity(density === 'compact' ? 'comfortable' : 'compact')}><LayoutGrid size={19}/><span>Layout</span></button>
        <button type="button" className={managing ? 'active' : ''} onClick={() => managing ? exitManage() : setManaging(true)}>{managing ? <X size={19}/> : <Check size={19}/>}<span>{managing ? 'Done' : 'Manage'}</span></button>
      </div>

      {mobileFiltersOpen && <div className="uploads-mobile-filter-panel"><label><input type="checkbox" checked={favoritesOnly} onChange={(event) => setFavoritesOnly(event.target.checked)}/><Heart size={16} fill={favoritesOnly ? 'currentColor' : 'none'}/><span>Favorites only</span></label></div>}

      {managing && <div className="uploads-manager" role="toolbar" aria-label="Selected upload actions">
        <button type="button" onClick={() => setSelected(new Set(items.map((item) => item.id)))} disabled={!items.length}><Check size={16}/><span>Select All</span><strong>{selected.size} selected</strong></button>
        <button type="button" onClick={() => runBulk('favorite')} disabled={!selected.size || Boolean(actionBusy)}><Heart size={16}/><span>Favorite</span></button>
        <button type="button" onClick={() => runBulk('download')} disabled={!selected.size || Boolean(actionBusy)}>{actionBusy === 'download' ? <LoaderCircle className="spin" size={16}/> : <Download size={16}/>}<span>Download</span></button>
        <button type="button" className="danger" onClick={() => runBulk('delete')} disabled={!selected.size || Boolean(actionBusy)}>{actionBusy === 'delete' ? <LoaderCircle className="spin" size={16}/> : <Trash2 size={16}/>}<span>Delete</span></button>
        <button type="button" aria-label="Close upload batch actions" onClick={exitManage}><X size={17}/></button>
      </div>}

      {error && <div className="gallery-state error">{error}</div>}

      <section className="uploads-grid" data-density={density} aria-label="Uploaded assets">
        <button type="button" className="upload-add-card" onClick={() => inputRef.current?.click()} disabled={Boolean(uploading)}>
          {uploading ? <LoaderCircle className="spin" size={30}/> : <Plus size={34}/>}<span>{uploading ? `Uploading ${uploading}` : 'Upload'}</span>
        </button>
        <input ref={inputRef} className="sr-only" type="file" accept="image/png,image/jpeg,image/webp" multiple onChange={(event) => uploadFiles(event.target.files)} />
        {items.map((asset) => <UploadCard key={asset.id} asset={asset} managing={managing} selected={selected.has(asset.id)} onSelect={toggleSelected} onOpen={setSelectedAsset} onFavorite={toggleFavorite} onRename={renameAsset} onDelete={removeAsset}/>) }
      </section>

      {loading && !items.length && <div className="uploads-loading"><LoaderCircle className="spin" size={20}/>Loading uploads…</div>}
      {!loading && !items.length && !search?.trim() && !favoritesOnly && <div className="uploads-empty"><Upload size={22}/><span>Your uploaded references will stay here for reuse.</span></div>}
      {!loading && !items.length && (search?.trim() || favoritesOnly) && <div className="uploads-empty">No uploads match these filters.</div>}

      <UploadAssetModal asset={selectedAsset} onClose={() => setSelectedAsset(null)} onFavorite={toggleFavorite} onRename={renameAsset} onDelete={removeAsset} onUseReference={useReference}/>
    </div>
  );
}
