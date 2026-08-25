from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one match in {path} for {old!r}; found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


legacy = Path("apps/studio/src/create-controls.jsx")
replace_once(
    legacy,
    "  videoReferenceInfo = null, videoFrameRate = 24, setVideoFrameRate = () => {},\n}) {",
    "  videoReferenceInfo = null, videoFrameRate = 24, setVideoFrameRate = () => {},\n  imageModelName = 'FLUX', imageModelLabel = 'FLUX.2 Klein 9B',\n}) {",
)
replace_once(
    legacy,
    "function AdvancedSettings({\n  open, onClose, anchorRef, mode, seed, setSeed, steps, setSteps,\n",
    "function AdvancedSettings({\n  open, onClose, anchorRef, mode, imageModelName = 'FLUX', seed, setSeed, steps, setSteps,\n",
)
replace_once(
    legacy,
    "Reset to {isVideo ? 'LTX' : 'FLUX'} defaults",
    "Reset to {isVideo ? 'LTX' : imageModelName} defaults",
)
replace_once(
    legacy,
    ": 'Add an image, describe the change, and generate with the live FLUX edit model.'}</p>",
    ": `Add an image, describe the change, and generate with the live ${imageModelName} edit model.`}</p>",
)
replace_once(
    legacy,
    "{jobStatus ? `Job ${jobStatus} · ` : ''}Live backend · FLUX.2 Klein 9B · {editAuto ? 'Auto canvas' : `${aspect} · ${imageDimensions.width}×${imageDimensions.height}`} · {references.length} reference{references.length === 1 ? '' : 's'}",
    "{jobStatus ? `Job ${jobStatus} · ` : ''}Live backend · {imageModelLabel} · {editAuto ? 'Auto canvas' : `${aspect} · ${imageDimensions.width}×${imageDimensions.height}`} · {references.length} reference{references.length === 1 ? '' : 's'}",
)
replace_once(
    legacy,
    "          mode={mode}\n          seed={seed}\n",
    "          mode={mode}\n          imageModelName={imageModelName}\n          seed={seed}\n",
)

wrapper = Path("apps/studio/src/features/create/CreateWorkspace.jsx")
replace_once(
    wrapper,
    "        onGenerate={handleGenerate}\n        composerStatusSlot={composerStatusSlot}\n",
    "        imageModelName={imageModel === 'qwen-image-edit-2511' ? 'Qwen' : 'FLUX'}\n        imageModelLabel={imageModel === 'qwen-image-edit-2511' ? 'Qwen Image Edit 2511' : 'FLUX.2 Klein 9B'}\n        onGenerate={handleGenerate}\n        composerStatusSlot={composerStatusSlot}\n",
)

print("Applied model-aware image backend labels")
