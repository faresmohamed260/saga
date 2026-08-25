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
    "    videoSource, onVideoSourceChange, onClearVideoSource, autoPrefillInfo,\n    onVideoResolutionChange, onVideoDurationChange, onVideoFrameRateChange,\n",
    "    videoSource, onVideoSourceChange, onClearVideoSource, autoPrefillInfo,\n    onVideoResolutionChange, onVideoDurationChange, onVideoFrameRateChange,\n    imageModelName = 'FLUX', imageModelLabel = 'FLUX.2 Klein 9B',\n",
)
replace_once(
    legacy,
    "        ? 'Edit the selected Gallery asset with the live FLUX edit model.'\n        : 'Add an image, describe the change, and generate with the live FLUX edit model.'}",
    "        ? `Edit the selected Gallery asset with the live ${imageModelName} edit model.`\n        : `Add an image, describe the change, and generate with the live ${imageModelName} edit model.`}",
)
replace_once(
    legacy,
    "Live backend · FLUX.2 Klein 9B · {editAuto ? `Auto canvas · ${sourceCount} reference${sourceCount === 1 ? '' : 's'}` : advanced.resolution}",
    "Live backend · {imageModelLabel} · {editAuto ? `Auto canvas · ${sourceCount} reference${sourceCount === 1 ? '' : 's'}` : advanced.resolution}",
)

wrapper = Path("apps/studio/src/features/create/CreateWorkspace.jsx")
replace_once(
    wrapper,
    "        onGenerate={handleGenerate}\n        composerStatusSlot={composerStatusSlot}\n",
    "        imageModelName={imageModel === 'qwen-image-edit-2511' ? 'Qwen' : 'FLUX'}\n        imageModelLabel={imageModel === 'qwen-image-edit-2511' ? 'Qwen Image Edit 2511' : 'FLUX.2 Klein 9B'}\n        onGenerate={handleGenerate}\n        composerStatusSlot={composerStatusSlot}\n",
)

print("Applied model-aware image backend labels")
