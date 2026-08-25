from __future__ import annotations

import io
import os
import time
from pathlib import Path
from typing import Any

import modal

APP_NAME = os.environ.get("MODAL_QWEN_IMAGE_EDIT_APP_NAME", "saga-qwen-image-edit-2511")
MODAL_VERSION = "1.4.2"
PYTHON_VERSION = "3.11"
CACHE_DIR = "/cache"
MODEL_REPO = "Qwen/Qwen-Image-Edit-2511"
MODEL_DIR = Path(CACHE_DIR) / "qwen-image-edit-2511"
GPU_TYPE = os.environ.get("MODAL_QWEN_IMAGE_EDIT_GPU", "H100")
FUNCTION_TIMEOUT_SECONDS = int(os.environ.get("MODAL_QWEN_IMAGE_EDIT_TIMEOUT_SECONDS", "3600"))
CONTAINER_IDLE_SECONDS = int(os.environ.get("MODAL_QWEN_IMAGE_EDIT_IDLE_SECONDS", "300"))
WORKER_MIN_CONTAINERS = 0
WORKER_MAX_CONTAINERS = int(os.environ.get("MODAL_QWEN_IMAGE_EDIT_MAX_CONTAINERS", "1"))
ECOSYSTEM_ID = "qwen-image-edit-2511"
WORKER_ID = os.environ.get("SAGA_MODAL_WORKER_ID", f"{ECOSYSTEM_ID}-worker")
STATE_DICT_NAME = os.environ.get("SAGA_MODAL_WORKER_STATE_DICT", "saga-qwen-image-edit-2511-worker-state")
CACHE_VOLUME_NAME = os.environ.get("SAGA_MODAL_WORKER_VOLUME", "saga-qwen-image-edit-2511-cache")

cache_volume = modal.Volume.from_name(CACHE_VOLUME_NAME, create_if_missing=True)
worker_state = modal.Dict.from_name(STATE_DICT_NAME, create_if_missing=True)

_runtime_secret_values: dict[str, str] = {}
for _name in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
    _value = str(os.environ.get(_name) or "").strip()
    if _value:
        _runtime_secret_values[_name] = _value
RUNTIME_SECRETS = [modal.Secret.from_dict(_runtime_secret_values)] if _runtime_secret_values else []

image = (
    modal.Image.debian_slim(python_version=PYTHON_VERSION)
    .apt_install("git", "libgl1", "libglib2.0-0")
    .pip_install(
        f"modal=={MODAL_VERSION}",
        "torch==2.7.1",
        "torchvision==0.22.1",
        "transformers>=4.57.0",
        "accelerate>=1.8.0",
        "safetensors>=0.5.3",
        "huggingface_hub[hf_transfer]>=0.36.0",
        "pillow>=11.0.0",
        "git+https://github.com/huggingface/diffusers.git",
    )
    .env({
        "HF_HUB_ENABLE_HF_TRANSFER": "1",
        "HF_HUB_CACHE": CACHE_DIR,
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "SAGA_MODAL_WORKER_ID": WORKER_ID,
        "SAGA_MODAL_WORKER_STATE_DICT": STATE_DICT_NAME,
        "SAGA_MODAL_WORKER_VOLUME": CACHE_VOLUME_NAME,
    })
)

app = modal.App(APP_NAME, image=image)


def _log(event: str, **fields: Any) -> None:
    print({"event": event, **fields}, flush=True)


def _set_worker_state(state: str, **fields: Any) -> None:
    payload = {
        "state": state,
        "worker_id": WORKER_ID,
        "ecosystem": ECOSYSTEM_ID,
        "updated_at": int(time.time()),
        **fields,
    }
    worker_state["worker"] = payload
    _log("worker_state", **payload)


def _snapshot_download() -> Path:
    marker = MODEL_DIR / "model_index.json"
    if marker.is_file():
        return MODEL_DIR
    from huggingface_hub import snapshot_download

    token = str(os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN") or "").strip() or None
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    snapshot_download(
        repo_id=MODEL_REPO,
        local_dir=str(MODEL_DIR),
        token=token,
        local_dir_use_symlinks=False,
    )
    cache_volume.commit()
    _log("qwen_image_edit_checkpoint_downloaded", repo=MODEL_REPO, elapsed_seconds=round(time.perf_counter() - started, 3))
    return MODEL_DIR


@app.function(image=image, timeout=7200, volumes={CACHE_DIR: cache_volume}, secrets=RUNTIME_SECRETS)
def prefetch_qwen_image_edit_2511(force: bool = False) -> dict[str, Any]:
    if force and MODEL_DIR.exists():
        import shutil
        shutil.rmtree(MODEL_DIR)
    path = _snapshot_download()
    _set_worker_state("sleeping", assets_cached=True)
    return {
        "ready": True,
        "model": MODEL_REPO,
        "path": str(path),
        "precision": "official-bfloat16",
    }


@app.cls(
    image=image,
    gpu=GPU_TYPE,
    timeout=FUNCTION_TIMEOUT_SECONDS,
    scaledown_window=CONTAINER_IDLE_SECONDS,
    min_containers=WORKER_MIN_CONTAINERS,
    max_containers=WORKER_MAX_CONTAINERS,
    volumes={CACHE_DIR: cache_volume},
    secrets=RUNTIME_SECRETS,
)
@modal.concurrent(max_inputs=1)
class QwenImageEdit2511Worker:
    @modal.enter()
    def load(self) -> None:
        import torch
        from diffusers import QwenImageEditPlusPipeline

        _set_worker_state("loading")
        started = time.perf_counter()
        model_path = _snapshot_download()
        self.pipe = QwenImageEditPlusPipeline.from_pretrained(
            str(model_path),
            torch_dtype=torch.bfloat16,
            local_files_only=True,
        )
        self.pipe.to("cuda")
        self.pipe.set_progress_bar_config(disable=True)
        startup_seconds = round(time.perf_counter() - started, 3)
        _set_worker_state("ready", startup_seconds=startup_seconds)
        _log(
            "qwen_image_edit_worker_ready",
            model=MODEL_REPO,
            precision="official-bfloat16",
            gpu=GPU_TYPE,
            startup_seconds=startup_seconds,
        )

    @modal.method()
    def edit(
        self,
        *,
        images: list[dict[str, Any]],
        prompt: str,
        negative_prompt: str = "",
        seed: int = 42,
        steps: int = 40,
        cfg: float = 4.0,
        megapixels: float = 1.0,
    ) -> bytes:
        import torch
        from PIL import Image

        if not images:
            raise ValueError("at least one reference image is required")
        clean_prompt = str(prompt or "").strip()
        if not clean_prompt:
            raise ValueError("prompt is required")

        _set_worker_state("generating")
        started = time.perf_counter()
        pil_images = []
        for item in images:
            raw = bytes(item.get("bytes") or b"")
            if not raw:
                raise ValueError("reference image is empty")
            pil_images.append(Image.open(io.BytesIO(raw)).convert("RGB"))

        generator = torch.Generator(device="cuda").manual_seed(int(seed))
        with torch.inference_mode():
            result = self.pipe(
                image=pil_images,
                prompt=clean_prompt,
                negative_prompt=str(negative_prompt or " ") or " ",
                generator=generator,
                true_cfg_scale=float(cfg),
                guidance_scale=1.0,
                num_inference_steps=max(1, min(int(steps), 80)),
                num_images_per_prompt=1,
            ).images[0]

        _set_worker_state("finalizing")
        out = io.BytesIO()
        result.save(out, format="PNG", optimize=False)
        payload = out.getvalue()
        _set_worker_state("ready", last_generation_seconds=round(time.perf_counter() - started, 3))
        return payload
