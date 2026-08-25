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
GPU_TYPE = os.environ.get("MODAL_QWEN_IMAGE_EDIT_GPU", "L40S")
WORKER_MEMORY_MB = int(os.environ.get("MODAL_QWEN_IMAGE_EDIT_MEMORY_MB", "98304"))
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

# Use the released library versions matching the checkpoint's own serialization
# metadata (Diffusers 0.36.x / Transformers 4.57.1) rather than tracking Git HEAD.
# The model weights remain the official BF16 checkpoint.
image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.8.1-devel-ubuntu22.04",
        add_python=PYTHON_VERSION,
    )
    .entrypoint([])
    .apt_install("git", "libgl1", "libglib2.0-0")
    .uv_pip_install(
        f"modal=={MODAL_VERSION}",
        "Pillow~=11.2.1",
        "accelerate~=1.8.1",
        "diffusers==0.36.0",
        "huggingface-hub==0.36.0",
        "safetensors>=0.8.0,<1.0.0",
        "sentencepiece==0.2.0",
        "torch==2.7.1",
        "transformers==4.57.1",
        extra_options="--index-strategy unsafe-best-match",
        extra_index_url="https://download.pytorch.org/whl/cu128",
    )
    .env({
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
    memory=WORKER_MEMORY_MB,
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
        # Keep the official BF16 checkpoint intact. The 57.7 GB pipeline is
        # larger than an L40S, so move whole components between CPU RAM and GPU
        # on demand instead of quantizing or casting the weights.
        self.pipe.enable_model_cpu_offload(device="cuda")
        self.pipe.set_progress_bar_config(disable=True)
        startup_seconds = round(time.perf_counter() - started, 3)
        _set_worker_state("ready", startup_seconds=startup_seconds)
        _log(
            "qwen_image_edit_worker_ready",
            model=MODEL_REPO,
            precision="official-bfloat16",
            gpu=GPU_TYPE,
            memory_mb=WORKER_MEMORY_MB,
            offload="model_cpu_offload",
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
        import math
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

        first_width, first_height = pil_images[0].size
        ratio = max(first_width, 1) / max(first_height, 1)
        target_area = max(0.25, min(float(megapixels), 4.0)) * 1_000_000
        target_width = max(32, round(math.sqrt(target_area * ratio) / 32) * 32)
        target_height = max(32, round((target_width / ratio) / 32) * 32)

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
                width=target_width,
                height=target_height,
            ).images[0]

        _set_worker_state("finalizing")
        out = io.BytesIO()
        result.save(out, format="PNG", optimize=False)
        payload = out.getvalue()
        _set_worker_state(
            "ready",
            last_generation_seconds=round(time.perf_counter() - started, 3),
            output_width=result.width,
            output_height=result.height,
        )
        return payload
