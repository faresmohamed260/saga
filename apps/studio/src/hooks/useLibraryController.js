import React from 'react';
import { fetchCollectionItems, fetchCollections, fetchFavorites, fetchGallery } from '../api/studioApi.js';

const GALLERY_PAGE_SIZE = 24;
const AUTO_REFRESH_MS = 5000;

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

  const galleryItemsRef = React.useRef([]);
  const selectedCollectionRef = React.useRef(null);
  const refreshInFlightRef = React.useRef(false);

  React.useEffect(() => { galleryItemsRef.current = galleryItems; }, [galleryItems]);
  React.useEffect(() => { selectedCollectionRef.current = selectedCollection; }, [selectedCollection]);

  const loadGallery = async ({
    append = false,
    silent = false,
    preserveLoaded = false,
    kind = galleryKind,
    model = galleryModel,
    search = gallerySearch,
    sort = gallerySort,
  } = {}) => {
    if (append && galleryPage.nextOffset == null) return;
    if (!silent) append ? setGalleryAppending(true) : setGalleryLoading(true);
    setGalleryError('');
    try {
      const refreshLimit = preserveLoaded
        ? Math.max(GALLERY_PAGE_SIZE, galleryItemsRef.current.length || 0)
        : GALLERY_PAGE_SIZE;
      const payload = await fetchGallery({
        limit: append ? GALLERY_PAGE_SIZE : refreshLimit,
        offset: append ? galleryPage.nextOffset : 0,
        kind,
        model,
        search,
        sort,
      });
      const nextItems = (Array.isArray(payload?.items) ? payload.items : []).map(toGalleryItem);
      setGalleryItems((current) => append ? [...current, ...nextItems] : nextItems);
      setFavorites((current) => {
        const next = new Set(current);
        nextItems.forEach((item) => item.favorite ? next.add(item.id) : next.delete(item.id));
        return next;
      });
      setGalleryPage({ nextOffset: payload?.page?.nextOffset ?? null, hasMore: Boolean(payload?.page?.hasMore) });
      if (Array.isArray(payload?.facets?.models)) setGalleryModels(payload.facets.models);
    } catch (err) {
      setGalleryError(err instanceof Error ? err.message : 'Unable to load Gallery.');
    } finally {
      if (!silent) append ? setGalleryAppending(false) : setGalleryLoading(false);
    }
  };

  const loadFavorites = async ({ silent = false } = {}) => {
    if (!silent) setLibraryLoading(true);
    setLibraryError('');
    try {
      const payload = await fetchFavorites();
      const nextItems = (Array.isArray(payload?.items) ? payload.items : []).map(toGalleryItem);
      setFavoriteItems(nextItems);
      setFavorites(new Set(nextItems.map((item) => item.id)));
    } catch (err) {
      setLibraryError(err instanceof Error ? err.message : 'Unable to load favorites.');
    } finally {
      if (!silent) setLibraryLoading(false);
    }
  };

  const loadCollections = async ({ silent = false } = {}) => {
    if (!silent) setLibraryLoading(true);
    setLibraryError('');
    try {
      const payload = await fetchCollections();
      const nextCollections = Array.isArray(payload?.collections) ? payload.collections : [];
      setCollections(nextCollections);
      const currentSelection = selectedCollectionRef.current;
      if (currentSelection?.id) {
        const refreshedSelection = nextCollections.find((collection) => collection.id === currentSelection.id) || null;
        if (refreshedSelection) {
          setSelectedCollection(refreshedSelection);
          selectedCollectionRef.current = refreshedSelection;
        } else {
          setSelectedCollection(null);
          selectedCollectionRef.current = null;
          setCollectionItems([]);
        }
      }
      return nextCollections;
    } catch (err) {
      setLibraryError(err instanceof Error ? err.message : 'Unable to load collections.');
      return null;
    } finally {
      if (!silent) setLibraryLoading(false);
    }
  };

  const loadCollectionItems = async (collection, { silent = false, select = true } = {}) => {
    if (!collection?.id) return;
    if (select) {
      setSelectedCollection(collection);
      selectedCollectionRef.current = collection;
    }
    if (!silent) setLibraryLoading(true);
    setLibraryError('');
    try {
      const payload = await fetchCollectionItems(collection.id);
      const nextItems = (Array.isArray(payload?.items) ? payload.items : []).map(toGalleryItem);
      setCollectionItems(nextItems);
      setFavorites((current) => {
        const next = new Set(current);
        nextItems.forEach((item) => item.favorite ? next.add(item.id) : next.delete(item.id));
        return next;
      });
    } catch (err) {
      setLibraryError(err instanceof Error ? err.message : 'Unable to load collection.');
    } finally {
      if (!silent) setLibraryLoading(false);
    }
  };

  React.useEffect(() => {
    if (!['Gallery', 'Favorites', 'Collections'].includes(section)) return undefined;

    let disposed = false;
    const refresh = async ({ initial = false } = {}) => {
      if (disposed || (typeof document !== 'undefined' && document.visibilityState === 'hidden')) return;
      if (refreshInFlightRef.current) return;
      refreshInFlightRef.current = true;
      try {
        if (section === 'Gallery') {
          await loadGallery({
            append: false,
            silent: !initial,
            preserveLoaded: !initial,
            kind: galleryKind,
            model: galleryModel,
            search: gallerySearch,
            sort: gallerySort,
          });
        } else if (section === 'Favorites') {
          await loadFavorites({ silent: !initial });
        } else if (section === 'Collections') {
          const nextCollections = await loadCollections({ silent: !initial });
          const currentSelection = selectedCollectionRef.current;
          if (nextCollections && currentSelection?.id && nextCollections.some((collection) => collection.id === currentSelection.id)) {
            await loadCollectionItems(currentSelection, { silent: true, select: false });
          }
        }
      } finally {
        refreshInFlightRef.current = false;
      }
    };

    refresh({ initial: true });
    const timer = window.setInterval(() => refresh(), AUTO_REFRESH_MS);
    const onFocus = () => refresh();
    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible') refresh();
    };
    window.addEventListener('focus', onFocus);
    document.addEventListener('visibilitychange', onVisibilityChange);

    return () => {
      disposed = true;
      window.clearInterval(timer);
      window.removeEventListener('focus', onFocus);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [section, galleryKind, galleryModel, gallerySearch, gallerySort, selectedCollection?.id]);

  return {
    favorites, setFavorites,
    favoriteItems, setFavoriteItems,
    galleryItems, setGalleryItems,
    galleryLoading, galleryAppending, galleryError,
    galleryKind, setGalleryKind,
    galleryModel, setGalleryModel,
    gallerySearch, setGallerySearch,
    gallerySort, setGallerySort,
    galleryModels, galleryPage,
    libraryLoading, libraryError, setLibraryError,
    collections, setCollections,
    selectedCollection, setSelectedCollection,
    collectionItems, setCollectionItems,
    loadGallery, loadFavorites, loadCollections, loadCollectionItems,
  };
}
