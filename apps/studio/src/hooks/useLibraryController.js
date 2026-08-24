import React from 'react';
import { fetchCollectionItems, fetchCollections, fetchFavorites, fetchGallery } from '../api/studioApi.js';

const GALLERY_PAGE_SIZE = 24;

export default function useLibraryController({ section, toGalleryItem }) {
  const [favorites, setFavorites] = React.useState(new Set());
  const [favoriteItems, setFavoriteItems] = React.useState([]);
  const [galleryItems, setGalleryItems] = React.useState([]);
  const [galleryLoading, setGalleryLoading] = React.useState(false);
  const [galleryAppending, setGalleryAppending] = React.useState(false);
  const [galleryError, setGalleryError] = React.useState('');
  const [galleryKind, setGalleryKind] = React.useState('all');
  const [galleryModel, setGalleryModel] = React.useState('all');
  const [gallerySearch, setGallerySearch] = React.useState('');
  const [gallerySort, setGallerySort] = React.useState('newest');
  const [galleryModels, setGalleryModels] = React.useState([]);
  const [galleryPage, setGalleryPage] = React.useState({ nextOffset: null, hasMore: false });
  const [libraryLoading, setLibraryLoading] = React.useState(false);
  const [libraryError, setLibraryError] = React.useState('');
  const [collections, setCollections] = React.useState([]);
  const [selectedCollection, setSelectedCollection] = React.useState(null);
  const [collectionItems, setCollectionItems] = React.useState([]);

  const loadGallery = async ({ append = false, kind = galleryKind, model = galleryModel, search = gallerySearch, sort = gallerySort } = {}) => {
    if (append && galleryPage.nextOffset == null) return;
    append ? setGalleryAppending(true) : setGalleryLoading(true);
    setGalleryError('');
    try {
      const payload = await fetchGallery({ limit: GALLERY_PAGE_SIZE, offset: append ? galleryPage.nextOffset : 0, kind, model, search, sort });
      const nextItems = (Array.isArray(payload?.items) ? payload.items : []).map(toGalleryItem);
      setGalleryItems((current) => append ? [...current, ...nextItems] : nextItems);
      setFavorites((current) => {
        const next = new Set(current);
        nextItems.forEach((item) => item.favorite ? next.add(item.id) : next.delete(item.id));
        return next;
      });
      setGalleryPage({ nextOffset: payload?.page?.nextOffset ?? null, hasMore: Boolean(payload?.page?.hasMore) });
      if (Array.isArray(payload?.facets?.models)) setGalleryModels(payload.facets.models);
    } catch (err) { setGalleryError(err instanceof Error ? err.message : 'Unable to load Gallery.'); }
    finally { append ? setGalleryAppending(false) : setGalleryLoading(false); }
  };

  const loadFavorites = async () => {
    setLibraryLoading(true); setLibraryError('');
    try {
      const payload = await fetchFavorites();
      const nextItems = (Array.isArray(payload?.items) ? payload.items : []).map(toGalleryItem);
      setFavoriteItems(nextItems);
      setFavorites(new Set(nextItems.map((item) => item.id)));
    } catch (err) { setLibraryError(err instanceof Error ? err.message : 'Unable to load favorites.'); }
    finally { setLibraryLoading(false); }
  };

  const loadCollections = async () => {
    setLibraryLoading(true); setLibraryError('');
    try { const payload = await fetchCollections(); setCollections(Array.isArray(payload?.collections) ? payload.collections : []); }
    catch (err) { setLibraryError(err instanceof Error ? err.message : 'Unable to load collections.'); }
    finally { setLibraryLoading(false); }
  };

  const loadCollectionItems = async (collection) => {
    setSelectedCollection(collection); setLibraryLoading(true); setLibraryError('');
    try {
      const payload = await fetchCollectionItems(collection.id);
      const nextItems = (Array.isArray(payload?.items) ? payload.items : []).map(toGalleryItem);
      setCollectionItems(nextItems);
      setFavorites((current) => {
        const next = new Set(current);
        nextItems.forEach((item) => item.favorite ? next.add(item.id) : next.delete(item.id));
        return next;
      });
    } catch (err) { setLibraryError(err instanceof Error ? err.message : 'Unable to load collection.'); }
    finally { setLibraryLoading(false); }
  };

  React.useEffect(() => {
    if (section === 'Gallery') loadGallery({ append: false, kind: galleryKind, model: galleryModel });
    if (section === 'Favorites') loadFavorites();
    if (section === 'Collections') { setSelectedCollection(null); setCollectionItems([]); loadCollections(); }
  }, [section, galleryKind, galleryModel, gallerySearch, gallerySort]);

  return { favorites, setFavorites, favoriteItems, setFavoriteItems, galleryItems, setGalleryItems, galleryLoading, galleryAppending, galleryError, galleryKind, setGalleryKind, galleryModel, setGalleryModel, gallerySearch, setGallerySearch, gallerySort, setGallerySort, galleryModels, galleryPage, libraryLoading, libraryError, setLibraryError, collections, setCollections, selectedCollection, setSelectedCollection, collectionItems, setCollectionItems, loadGallery, loadFavorites, loadCollections, loadCollectionItems };
}
