from __future__ import annotations

from pathlib import Path
from typing import Any

import modal

APP_NAME = "saga-ltx23-probe"
CACHE_DIR = "/cache"

cache_volume = modal.Volume.from_name("graduation-comfyui-cache", create_if_missing=False)
image = modal.Image.debian_slim(python_version="3.11").pip_install("modal==1.4.2")
app = modal.App(APP_NAME, image=image)


@app.function(image=image, timeout=300, volumes={CACHE_DIR: cache_volume})
def probe() -> dict[str, Any]:
    root = Path(CACHE_DIR)
    needles = (
        "ltx",
        "gemma-3-12b",
        "gemma_3_12",
        "video_vae",
        "audio_vae",
        "embeddings_connectors",
        "spatial-upscaler",
    )
    files: list[dict[str, Any]] = []
    for candidate in root.rglob("*"):
        if not candidate.is_file():
            continue
        lower = candidate.name.lower()
        if not any(needle in lower for needle in needles):
            continue
        try:
            size = candidate.stat().st_size
        except OSError:
            size = -1
        files.append({"path": str(candidate), "name": candidate.name, "size": size})
    files.sort(key=lambda row: row["path"])
    return {"ready": True, "count": len(files), "files": files}
