import { addCollectionItem, createCollection as createCollectionRequest, deleteCollection as deleteCollectionRequest, deleteGeneration as deleteGenerationRequest, downloadBatch, fetchCollections, removeCollectionItem, renameCollection as renameCollectionRequest, updateFavorite } from '../api/studioApi.js';

function isUuid(value) { return /^[0-9a-f-]{36}$/i.test(String(value || '')); }

function imageDimensions(file) {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => { resolve({ width: image.naturalWidth || 0, height: image.naturalHeight || 0 }); URL.revokeObjectURL(url); };
    image.onerror = () => { resolve({ width: 0, height: 0 }); URL.revokeObjectURL(url); };
    image.src = url;
  });
}

export default function useMediaActions({
  section, setSection, setMode, setPrompt, setSeed, setSteps, setCfg, setWorkflowId, setModelId,
  references, setReferences, setError, setItems, selectedMedia, setSelectedMedia,
  favorites, setFavorites, favoriteItems, setFavoriteItems, galleryItems, setGalleryItems,
  collections, setCollections, selectedCollection, setSelectedCollection, collectionItems, setCollectionItems,
  setLibraryError, loadGallery, loadFavorites, loadCollections, loadCollectionItems,
}) {
  const toggleFavorite = async (item) => {
    const id = item.id;
    const nextValue = !favorites.has(id);
    setFavorites((current) => { const next = new Set(current); nextValue ? next.add(id) : next.delete(id); return next; });
    if (!item.persisted || !isUuid(id)) return;
    try {
      await updateFavorite(id, nextValue);
      if (section === 'Favorites' || section === 'Create') loadFavorites();
      setGalleryItems((current) => current.map((entry) => entry.id === id ? { ...entry, favorite: nextValue } : entry));
    } catch {
      setFavorites((current) => { const next = new Set(current); nextValue ? next.delete(id) : next.add(id); return next; });
    }
  };

  const createCollection = async () => {
    const name = window.prompt('Collection name');
    if (!name?.trim()) return;
    setLibraryError('');
    try { await createCollectionRequest(name.trim()); await loadCollections(); }
    catch (err) { setLibraryError(err instanceof Error ? err.message : 'Unable to create collection.'); }
  };

  const renameCollection = async (collection) => {
    const name = window.prompt('Rename collection', collection.name);
    if (!name?.trim() || name.trim() === collection.name) return;
    try { await renameCollectionRequest(collection.id, name.trim()); await loadCollections(); }
    catch (err) { setLibraryError(err instanceof Error ? err.message : 'Unable to rename collection.'); }
  };

  const deleteCollection = async (collection) => {
    if (!window.confirm(`Delete “${collection.name}”? The media itself will stay in Gallery.`)) return;
    try { await deleteCollectionRequest(collection.id); setSelectedCollection(null); setCollectionItems([]); await loadCollections(); }
    catch (err) { setLibraryError(err instanceof Error ? err.message : 'Unable to delete collection.'); }
  };

  const resolveCollections = async () => {
    if (collections.length) return collections;
    const payload = await fetchCollections();
    const available = Array.isArray(payload?.collections) ? payload.collections : [];
    setCollections(available);
    return available;
  };

  const addToCollection = async (item) => {
    if (!item.persisted || !isUuid(item.id)) return;
    let currentCollections;
    try { currentCollections = await resolveCollections(); }
    catch (err) { return window.alert(err instanceof Error ? err.message : 'Unable to load collections.'); }
    const hint = currentCollections.length ? currentCollections.map((c, index) => `${index + 1}. ${c.name}`).join('\n') : 'No collections yet. Create one from the Collections page first.';
    const answer = window.prompt(`Add to collection:\n${hint}\n\nEnter collection number or exact name:`);
    if (!answer) return;
    const index = Number.parseInt(answer, 10) - 1;
    const collection = currentCollections[index] || currentCollections.find((c) => c.name.toLowerCase() === answer.trim().toLowerCase());
    if (!collection) return window.alert('Collection not found.');
    try { await addCollectionItem(collection.id, item.id); await loadCollections(); }
    catch { window.alert('Could not add item to collection.'); }
  };

  const removeFromCollection = async (item) => {
    if (!selectedCollection) return;
    try { await removeCollectionItem(selectedCollection.id, item.id); await loadCollectionItems(selectedCollection); await loadCollections(); } catch {}
  };

  const reuseSettings = (item) => {
    setPrompt(item.title || '');
    if (item.seed != null) setSeed(String(item.seed));
    if (item.kind === 'video') { setMode('Video'); setSteps(11); setCfg(1); setWorkflowId('ltx25-redgraft-video'); setModelId('ltx25-redgraft'); }
    else if (item.mode === 'edit') { setMode('Edit'); setSteps(4); setCfg(1); setWorkflowId('flux2-klein-image-edit'); setModelId('flux2-klein-9b'); }
    else setMode('Image');
    setSection('Create');
    setError('');
  };

  const editThis = async (item) => {
    if (item.kind === 'video') return window.alert('Video editing will be connected with the video workflow phase.');
    const mediaUrl = item.originalUrl || item.url;
    if (!mediaUrl) return;
    try {
      const response = await fetch(mediaUrl);
      if (!response.ok) throw new Error(`Media request failed (${response.status})`);
      const blob = await response.blob();
      if (!blob.type.startsWith('image/')) throw new Error('Selected media is not an image.');
      const extension = blob.type === 'image/jpeg' ? 'jpg' : blob.type === 'image/webp' ? 'webp' : 'png';
      const file = new File([blob], `saga-edit-${item.id}.${extension}`, { type: blob.type || 'image/png' });
      const dimensions = await imageDimensions(file);
      references.forEach((reference) => reference.preview && URL.revokeObjectURL(reference.preview));
      setReferences([{ id: `gallery-${item.id}-${Date.now()}`, file, preview: URL.createObjectURL(blob), ...dimensions }]);
      setPrompt('');
      if (item.seed != null) setSeed(String(item.seed));
      setSteps(4); setCfg(1); setWorkflowId('flux2-klein-image-edit'); setModelId('flux2-klein-9b');
      setMode('Edit'); setSection('Create'); setError('');
    } catch (err) { window.alert(err instanceof Error ? err.message : 'Could not prepare this image for editing.'); }
  };

  const downloadItem = (item) => {
    const mediaUrl = item.originalUrl || item.url;
    if (!mediaUrl) return;
    const separator = mediaUrl.includes('?') ? '&' : '?';
    const link = document.createElement('a');
    link.href = `${mediaUrl}${separator}download=1`; link.download = '';
    document.body.appendChild(link); link.click(); link.remove();
  };

  const removeDeleted = async (ids) => {
    const deleted = ids instanceof Set ? ids : new Set(ids);
    setSelectedMedia((current) => current && deleted.has(current.id) ? null : current);
    setGalleryItems((current) => current.filter((entry) => !deleted.has(entry.id)));
    setFavoriteItems((current) => current.filter((entry) => !deleted.has(entry.id)));
    setCollectionItems((current) => current.filter((entry) => !deleted.has(entry.id)));
    setItems((current) => current.filter((entry) => !deleted.has(entry.id)));
    setFavorites((current) => { const next = new Set(current); deleted.forEach((id) => next.delete(id)); return next; });
    await loadCollections();
  };

  const deleteGeneration = async (item) => {
    if (!item.persisted || !isUuid(item.id)) return window.alert('Only persisted generations can be deleted.');
    if (!window.confirm('Permanently delete this generation? This removes the original, thumbnail, favorites, collection memberships, and retained source references.')) return;
    try { await deleteGenerationRequest(item.id); await removeDeleted([item.id]); }
    catch (err) { window.alert(err instanceof Error ? err.message : 'Could not delete generation.'); }
  };

  const bulkFavorite = async (selectedItems) => {
    const candidates = selectedItems.filter(Boolean);
    if (!candidates.length) return false;
    setFavorites((current) => { const next = new Set(current); candidates.forEach((item) => next.add(item.id)); return next; });
    const persisted = candidates.filter((item) => item.persisted && isUuid(item.id));
    try {
      await Promise.all(persisted.map((item) => updateFavorite(item.id, true)));
      setGalleryItems((current) => current.map((entry) => candidates.some((item) => item.id === entry.id) ? { ...entry, favorite: true } : entry));
      return true;
    } catch (err) { window.alert(err instanceof Error ? err.message : 'Could not favorite selected media.'); await loadGallery({ append: false }); return false; }
  };

  const bulkAddToCollection = async (selectedItems) => {
    const candidates = selectedItems.filter((item) => item?.persisted && isUuid(item.id));
    if (!candidates.length) { window.alert('Only persisted generations can be added to a collection.'); return false; }
    let availableCollections;
    try { availableCollections = await resolveCollections(); }
    catch (err) { window.alert(err instanceof Error ? err.message : 'Unable to load collections.'); return false; }
    if (!availableCollections.length) { window.alert('No collections yet. Create one from the Collections page first.'); return false; }
    const hint = availableCollections.map((collection, index) => `${index + 1}. ${collection.name}`).join('\n');
    const answer = window.prompt(`Add ${candidates.length} selected item${candidates.length === 1 ? '' : 's'} to collection:\n${hint}\n\nEnter collection number or exact name:`);
    if (!answer) return false;
    const index = Number.parseInt(answer, 10) - 1;
    const collection = availableCollections[index] || availableCollections.find((entry) => entry.name.toLowerCase() === answer.trim().toLowerCase());
    if (!collection) { window.alert('Collection not found.'); return false; }
    try { await Promise.all(candidates.map((item) => addCollectionItem(collection.id, item.id))); await loadCollections(); return true; }
    catch (err) { window.alert(err instanceof Error ? err.message : 'Could not add selected media to collection.'); return false; }
  };

  const bulkDownload = async (selectedItems) => {
    const candidates = selectedItems.filter((item) => item?.persisted && isUuid(item.id));
    if (!candidates.length) { window.alert('Only persisted generations can be downloaded as a batch.'); return false; }
    try {
      const response = await downloadBatch(candidates.map((item) => item.id));
      const blob = await response.blob();
      const disposition = response.headers.get('content-disposition') || '';
      const match = disposition.match(/filename="?([^";]+)"?/i);
      const filename = match?.[1] || `saga-gallery-${new Date().toISOString().slice(0, 10)}.zip`;
      const url = URL.createObjectURL(blob); const link = document.createElement('a');
      link.href = url; link.download = filename; document.body.appendChild(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000); return true;
    } catch (err) { window.alert(err instanceof Error ? err.message : 'Could not download selected media.'); return false; }
  };

  const bulkDelete = async (selectedItems) => {
    const candidates = selectedItems.filter((item) => item.persisted && isUuid(item.id));
    if (!candidates.length) return false;
    if (!window.confirm(`Permanently delete ${candidates.length} selected generation${candidates.length === 1 ? '' : 's'}? This removes originals, favorites, collection memberships, and retained source references.`)) return false;
    const outcomes = await Promise.all(candidates.map(async (item) => {
      try { await deleteGenerationRequest(item.id); return { id: item.id, ok: true }; }
      catch (error) { return { id: item.id, ok: false, error: error instanceof Error ? error.message : 'Delete failed' }; }
    }));
    const succeededIds = new Set(outcomes.filter((outcome) => outcome.ok).map((outcome) => outcome.id));
    const failed = outcomes.filter((outcome) => !outcome.ok);
    if (succeededIds.size) await removeDeleted(succeededIds);
    if (failed.length) {
      const firstError = failed[0]?.error ? ` First error: ${failed[0].error}` : '';
      window.alert(`Deleted ${succeededIds.size} of ${candidates.length} selected items. ${failed.length} failed and remain selected for retry.${firstError}`);
      return { failedIds: failed.map((outcome) => outcome.id), succeededIds: [...succeededIds] };
    }
    return { failedIds: [], succeededIds: [...succeededIds] };
  };

  return { toggleFavorite, createCollection, renameCollection, deleteCollection, addToCollection, removeFromCollection, reuseSettings, editThis, downloadItem, deleteGeneration, bulkFavorite, bulkAddToCollection, bulkDownload, bulkDelete };
}
