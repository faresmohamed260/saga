from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'apps/studio/src/app/App.jsx'
app = APP.read_text()
app = app.replace("import useGenerationController from '../hooks/useGenerationController.js';\n", "import useGenerationController from '../hooks/useGenerationController.js';\nimport useMediaActions from '../hooks/useMediaActions.js';\n")
start = app.index("  const toggleFavorite = async")
end = app.index("\n\n  const openMedia", start)
app = app[:start] + app[end:]
anchor = "  const { busy, jobStatus, workerStatus, activeJob, cancelBusy, generate, viewActiveJob, cancelActiveJob } = useGenerationController({ mode, isEdit, prompt, references, seed, steps, cfg, autoEditInfo, section, setItems, loadGallery, setError, setSection, setJobsFilter });\n"
insert = r'''  const mediaActions = useMediaActions({
    section, setSection, setMode, setPrompt, setSeed, setSteps, setCfg, setWorkflowId, setModelId,
    references, setReferences, setError, setItems, selectedMedia, setSelectedMedia,
    favorites, setFavorites, favoriteItems, setFavoriteItems, galleryItems, setGalleryItems,
    collections, setCollections, selectedCollection, setSelectedCollection, collectionItems, setCollectionItems,
    setLibraryError, loadGallery, loadFavorites, loadCollections, loadCollectionItems,
  });
  const { toggleFavorite, createCollection, renameCollection, deleteCollection, addToCollection, removeFromCollection, reuseSettings, editThis, downloadItem, deleteGeneration, bulkFavorite, bulkAddToCollection, bulkDownload, bulkDelete } = mediaActions;
'''
app = app.replace(anchor, anchor + insert)
APP.write_text(app)
print('Iteration 20 media actions extracted.')
