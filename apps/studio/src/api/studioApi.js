async function jsonResponse(response, fallback) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload?.error || fallback || `Request failed (${response.status})`);
  return payload;
}

export async function fetchGallery({ limit, offset, kind, model, search, sort }) {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (kind === 'image' || kind === 'video') params.set('kind', kind);
  if (model && model !== 'all') params.set('model', model);
  if (search?.trim()) params.set('search', search.trim());
  if (sort === 'oldest') params.set('sort', 'oldest');
  const response = await fetch(`/api/history?${params.toString()}`, { headers: { Accept: 'application/json' } });
  return jsonResponse(response, `Gallery request failed (${response.status})`);
}

export async function fetchFavorites() {
  const response = await fetch('/api/favorites');
  return jsonResponse(response, `Favorites request failed (${response.status})`);
}

export async function updateFavorite(id, isFavorite) {
  const response = await fetch('/api/favorites', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id, isFavorite }) });
  if (!response.ok) throw new Error(`Favorite update failed (${response.status})`);
}

export async function fetchCollections() {
  const response = await fetch('/api/collections');
  return jsonResponse(response, `Collections request failed (${response.status})`);
}

export async function createCollection(name) {
  const response = await fetch('/api/collections', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }) });
  return jsonResponse(response, `Create collection failed (${response.status})`);
}

export async function renameCollection(id, name) {
  const response = await fetch('/api/collections', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id, name }) });
  return jsonResponse(response, `Rename collection failed (${response.status})`);
}

export async function deleteCollection(id) {
  const response = await fetch(`/api/collections?id=${encodeURIComponent(id)}`, { method: 'DELETE' });
  if (!response.ok && response.status !== 204) throw new Error(`Delete collection failed (${response.status})`);
}

export async function fetchCollectionItems(collectionId) {
  const response = await fetch(`/api/collection-items?collectionId=${encodeURIComponent(collectionId)}`);
  return jsonResponse(response, `Collection request failed (${response.status})`);
}

export async function addCollectionItem(collectionId, generationId) {
  const response = await fetch('/api/collection-items', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ collectionId, generationId }) });
  if (!response.ok && response.status !== 204) throw new Error(`Collection update failed (${response.status})`);
}

export async function removeCollectionItem(collectionId, generationId) {
  const response = await fetch('/api/collection-items', { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ collectionId, generationId }) });
  if (!response.ok && response.status !== 204) throw new Error(`Collection update failed (${response.status})`);
}

export async function deleteGeneration(id) {
  const response = await fetch(`/api/generations?id=${encodeURIComponent(id)}`, { method: 'DELETE' });
  if (!response.ok) {
    let detail = '';
    try { const body = await response.json(); detail = body?.error ? `: ${body.error}` : ''; } catch {}
    throw new Error(`Delete failed (${response.status})${detail}`);
  }
}

export async function downloadBatch(ids) {
  const response = await fetch('/api/download-batch', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ids }) });
  if (!response.ok) {
    let detail = '';
    try { const body = await response.json(); detail = body?.error ? `: ${body.error}` : ''; } catch {}
    throw new Error(`Batch download failed (${response.status})${detail}`);
  }
  return response;
}

export async function runJobAction(id, action) {
  const response = await fetch('/api/job-actions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id, action }) });
  return jsonResponse(response, `${action === 'retry' ? 'Retry' : 'Cancel'} failed (${response.status})`);
}
