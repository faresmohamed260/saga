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
CIVITAI_MODEL_ID = 2246542
CIVITAI_VERSION_ID = 2553500
CIVITAI_FILE_ID = 2443737
CIVITAI_MODEL_NAME = "Qwn-Image-Edit-abliterated"
CIVITAI_VERSION_NAME = "v1.6-bf16"
CIVITAI_WEIGHT_NAME = "qwnImageEdit_v16Bf16.safetensors"
CIVITAI_WEIGHT_SHA256 = "4F8CA1242C7FDBE6CFD1835833C66E9CDBCF23EA27C7B811B43BDA316F30A6DA"
CIVITAI_EXPECTED_BYTES = 40861031560
CIVITAI_DIR = Path(CACHE_DIR) / "qwen-image-edit-2511-civitai-v16-bf16"
CIVITAI_WEIGHT_PATH = CIVITAI_DIR / CIVITAI_WEIGHT_NAME
CIVITAI_HASH_MARKER = CIVITAI_DIR / f"{CIVITAI_WEIGHT_NAME}.sha256"
LIGHTNING_REPO = "lightx2v/Qwen-Image-Edit-2511-Lightning"
LIGHTNING_WEIGHT_NAME = "Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors"
LIGHTNING_DIR = Path(CACHE_DIR) / "qwen-image-edit-2511-lightning"
LIGHTNING_MIN_STEPS = 4
LIGHTNING_MAX_STEPS = 4
LIGHTNING_DEFAULT_STEPS = 4
LIGHTNING_TRUE_CFG_SCALE = 1.0
GPU_TYPE = os.environ.get("MODAL_QWEN_IMAGE_EDIT_GPU", "A10:4")
WORKER_MEMORY_MB = int(os.environ.get("MODAL_QWEN_IMAGE_EDIT_MEMORY_MB", "98304"))
FUNCTION_TIMEOUT_SECONDS = int(os.environ.get("MODAL_QWEN_IMAGE_EDIT_TIMEOUT_SECONDS", "7200"))
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
for _name in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "CIVITAI_API_TOKEN"):
    _value = str(os.environ.get(_name) or "").strip()
    if _value:
        _runtime_secret_values[_name] = _value
RUNTIME_SECRETS = [modal.Secret.from_dict(_runtime_secret_values)] if _runtime_secret_values else []

# Keep the released Diffusers/Transformers versions that support Qwen Image Edit
# single-file transformer loading. The Civitai fallback is pinned by version, file ID, size, and SHA.
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
        "torchvision==0.22.1",
        "transformers==4.57.1",
        extra_options="--index-strategy unsafe-best-match",
        extra_index_url="https://download.pytorch.org/whl/cu128",
    )
    .env({
        "HF_HUB_CACHE": CACHE_DIR,
        "HF_ENABLE_PARALLEL_LOADING": "YES",
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


def _hf_token() -> str | None:
    return str(os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN") or "").strip() or None


def _civitai_token() -> str:
    token = str(os.environ.get("CIVITAI_API_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("CIVITAI_API_TOKEN is required for the pinned Qwen fallback checkpoint")
    return token


def _snapshot_download() -> Path:
    marker = MODEL_DIR / "model_index.json"
    if marker.is_file():
        return MODEL_DIR

    from huggingface_hub import snapshot_download

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    snapshot_download(
        repo_id=MODEL_REPO,
        local_dir=str(MODEL_DIR),
        token=_hf_token(),
        ignore_patterns=[
            "transformer/*.safetensors",
            "transformer/*.bin",
        ],
    )
    cache_volume.commit()
    _log(
        "qwen_image_edit_base_components_downloaded",
        repo=MODEL_REPO,
        elapsed_seconds=round(time.perf_counter() - started, 3),
    )
    return MODEL_DIR


def _civitai_checkpoint_download() -> Path:
    import hashlib
    import urllib.error
    import urllib.parse
    import urllib.request

    expected = CIVITAI_WEIGHT_SHA256.upper()
    if CIVITAI_WEIGHT_PATH.is_file() and CIVITAI_HASH_MARKER.is_file():
        marker = CIVITAI_HASH_MARKER.read_text(encoding="utf-8").strip().upper()
        if marker == expected and CIVITAI_WEIGHT_PATH.stat().st_size == CIVITAI_EXPECTED_BYTES:
            return CIVITAI_WEIGHT_PATH

    CIVITAI_DIR.mkdir(parents=True, exist_ok=True)
    temporary = CIVITAI_WEIGHT_PATH.with_suffix(CIVITAI_WEIGHT_PATH.suffix + ".partial")
    if temporary.exists():
        temporary.unlink()

    query = urllib.parse.urlencode({
        "fileId": CIVITAI_FILE_ID,
        "token": _civitai_token(),
    })
    request = urllib.request.Request(
        f"https://civitai.com/api/download/models/{CIVITAI_VERSION_ID}?{query}",
        headers={
            "Accept": "application/octet-stream",
            "User-Agent": "saga-qwen-image-edit-worker/2.0",
        },
    )
    started = time.perf_counter()
    digest = hashlib.sha256()
    downloaded = 0
    try:
        with urllib.request.urlopen(request, timeout=180) as response, temporary.open("wb") as output:
            disposition = str(response.headers.get("Content-Disposition") or "")
            if CIVITAI_WEIGHT_NAME not in disposition:
                raise RuntimeError("Civitai download resolved to an unexpected checkpoint filename")
            while True:
                chunk = response.read(8 * 1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                digest.update(chunk)
                downloaded += len(chunk)
    except urllib.error.HTTPError as exc:
        if temporary.exists():
            temporary.unlink()
        try:
            detail = exc.read(2048).decode("utf-8", errors="replace").strip()[:1000]
        except Exception:
            detail = ""
        raise RuntimeError(
            f"Civitai checkpoint download failed with HTTP {int(exc.code)}: {detail or 'no response body'}"
        ) from None
    except urllib.error.URLError as exc:
        if temporary.exists():
            temporary.unlink()
        reason = str(getattr(exc, "reason", "network error"))[:500]
        raise RuntimeError(f"Civitai checkpoint download failed: {reason}") from None
    except Exception as exc:
        if temporary.exists():
            temporary.unlink()
        raise RuntimeError(
            f"Civitai checkpoint download failed: {type(exc).__name__}: {str(exc)[:500]}"
        ) from None

    if downloaded != CIVITAI_EXPECTED_BYTES:
        if temporary.exists():
            temporary.unlink()
        raise RuntimeError(
            f"Civitai checkpoint size mismatch for file {CIVITAI_FILE_ID}: expected {CIVITAI_EXPECTED_BYTES}, got {downloaded}"
        )

    actual = digest.hexdigest().upper()
    if actual != expected:
        if temporary.exists():
            temporary.unlink()
        raise RuntimeError(
            f"Civitai checkpoint SHA256 mismatch for file {CIVITAI_FILE_ID}: expected {expected}, got {actual}"
        )

    temporary.replace(CIVITAI_WEIGHT_PATH)
    CIVITAI_HASH_MARKER.write_text(expected + "\n", encoding="utf-8")
    cache_volume.commit()
    _log(
        "qwen_image_edit_civitai_checkpoint_downloaded",
        model_id=CIVITAI_MODEL_ID,
        version_id=CIVITAI_VERSION_ID,
        file_id=CIVITAI_FILE_ID,
        version=CIVITAI_VERSION_NAME,
        weight=CIVITAI_WEIGHT_NAME,
        bytes=downloaded,
        sha256=expected,
        elapsed_seconds=round(time.perf_counter() - started, 3),
    )
    return CIVITAI_WEIGHT_PATH


def _lightning_download() -> Path:
    weight = LIGHTNING_DIR / LIGHTNING_WEIGHT_NAME
    if weight.is_file():
        return LIGHTNING_DIR

    from huggingface_hub import snapshot_download

    LIGHTNING_DIR.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    snapshot_download(
        repo_id=LIGHTNING_REPO,
        local_dir=str(LIGHTNING_DIR),
        allow_patterns=[LIGHTNING_WEIGHT_NAME],
        token=_hf_token(),
    )
    cache_volume.commit()
    _log(
        "qwen_image_edit_lightning_downloaded",
        repo=LIGHTNING_REPO,
        weight=LIGHTNING_WEIGHT_NAME,
        elapsed_seconds=round(time.perf_counter() - started, 3),
    )
    return LIGHTNING_DIR


@app.function(image=image, timeout=7200, volumes={CACHE_DIR: cache_volume}, secrets=RUNTIME_SECRETS)
def prefetch_qwen_image_edit_2511(force: bool = False) -> dict[str, Any]:
    if force:
        import shutil

        for path in (MODEL_DIR, CIVITAI_DIR, LIGHTNING_DIR):
            if path.exists():
                shutil.rmtree(path)
    model_path = _snapshot_download()
    checkpoint_path = _civitai_checkpoint_download()
    lightning_path = _lightning_download()
    _set_worker_state(
        "sleeping",
        assets_cached=True,
        checkpoint_source="civitai",
        checkpoint_version_id=CIVITAI_VERSION_ID,
        checkpoint_file_id=CIVITAI_FILE_ID,
        precision="civitai-bfloat16",
        acceleration="lightning-lora-4step-bf16",
        lightning_steps=str(LIGHTNING_DEFAULT_STEPS),
    )
    return {
        "ready": True,
        "model": MODEL_REPO,
        "path": str(model_path),
        "precision": "civitai-bfloat16",
        "checkpointModelId": CIVITAI_MODEL_ID,
        "checkpointVersionId": CIVITAI_VERSION_ID,
        "checkpointFileId": CIVITAI_FILE_ID,
        "checkpointVersion": CIVITAI_VERSION_NAME,
        "checkpointPath": str(checkpoint_path),
        "checkpointSha256": CIVITAI_WEIGHT_SHA256,
        "checkpointBytes": CIVITAI_EXPECTED_BYTES,
        "lightningRepo": LIGHTNING_REPO,
        "lightningPath": str(lightning_path / LIGHTNING_WEIGHT_NAME),
        "lightningSteps": [LIGHTNING_DEFAULT_STEPS],
        "defaultSteps": LIGHTNING_DEFAULT_STEPS,
        "trueCfgScale": LIGHTNING_TRUE_CFG_SCALE,
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
        from diffusers import QwenImageEditPlusPipeline, QwenImageTransformer2DModel

        _set_worker_state(
            "loading",
            checkpoint_source="civitai",
            checkpoint_version_id=CIVITAI_VERSION_ID,
            checkpoint_file_id=CIVITAI_FILE_ID,
            precision="civitai-bfloat16",
        )
        started = time.perf_counter()
        model_path = _snapshot_download()
        checkpoint_path = _civitai_checkpoint_download()
        lightning_path = _lightning_download()
        gpu_count = torch.cuda.device_count()
        if gpu_count < 2:
            raise RuntimeError(f"Qwen Image Edit requires a multi-GPU worker; visible CUDA devices={gpu_count}")
        max_memory = {index: "22GB" for index in range(gpu_count)}

        transformer_started = time.perf_counter()
        transformer = QwenImageTransformer2DModel.from_single_file(
            str(checkpoint_path),
            config=MODEL_REPO,
            subfolder="transformer",
            torch_dtype=torch.bfloat16,
            device_map="balanced",
            max_memory=max_memory,
        )
        transformer_load_seconds = round(time.perf_counter() - transformer_started, 3)
        _set_worker_state(
            "loading",
            checkpoint_source="civitai",
            checkpoint_version_id=CIVITAI_VERSION_ID,
            checkpoint_file_id=CIVITAI_FILE_ID,
            precision="civitai-bfloat16",
            transformer_load_seconds=transformer_load_seconds,
        )

        self.pipe = QwenImageEditPlusPipeline.from_pretrained(
            str(model_path),
            transformer=transformer,
            torch_dtype=torch.bfloat16,
            local_files_only=True,
            device_map="balanced",
            max_memory=max_memory,
        )
        self.pipe.load_lora_weights(
            str(lightning_path),
            weight_name=LIGHTNING_WEIGHT_NAME,
            adapter_name="lightning_4step",
        )
        self.pipe.set_adapters("lightning_4step", adapter_weights=1.0)
        self.pipe.set_progress_bar_config(disable=True)
        startup_seconds = round(time.perf_counter() - started, 3)
        device_map = getattr(self.pipe, "hf_device_map", None)
        _set_worker_state(
            "ready",
            startup_seconds=startup_seconds,
            transformer_load_seconds=transformer_load_seconds,
            gpu_count=gpu_count,
            placement="balanced-multi-gpu",
            checkpoint_source="civitai",
            checkpoint_version_id=CIVITAI_VERSION_ID,
            checkpoint_file_id=CIVITAI_FILE_ID,
            precision="civitai-bfloat16",
            acceleration="lightning-lora-4step-bf16",
            lightning_steps=str(LIGHTNING_DEFAULT_STEPS),
        )
        _log(
            "qwen_image_edit_worker_ready",
            model=MODEL_REPO,
            checkpoint_model=CIVITAI_MODEL_NAME,
            checkpoint_version=CIVITAI_VERSION_NAME,
            checkpoint_version_id=CIVITAI_VERSION_ID,
            checkpoint_file_id=CIVITAI_FILE_ID,
            checkpoint_sha256=CIVITAI_WEIGHT_SHA256,
            precision="civitai-bfloat16",
            lightning_repo=LIGHTNING_REPO,
            lightning_weight=LIGHTNING_WEIGHT_NAME,
            lightning_steps=LIGHTNING_DEFAULT_STEPS,
            true_cfg_scale=LIGHTNING_TRUE_CFG_SCALE,
            gpu=GPU_TYPE,
            gpu_count=gpu_count,
            memory_mb=WORKER_MEMORY_MB,
            placement="balanced-multi-gpu",
            device_map=device_map,
            transformer_load_seconds=transformer_load_seconds,
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
        steps: int = LIGHTNING_DEFAULT_STEPS,
        cfg: float = LIGHTNING_TRUE_CFG_SCALE,
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

        lightning_steps = max(LIGHTNING_MIN_STEPS, min(int(steps), LIGHTNING_MAX_STEPS))
        _set_worker_state(
            "generating",
            checkpoint_source="civitai",
            checkpoint_version_id=CIVITAI_VERSION_ID,
            checkpoint_file_id=CIVITAI_FILE_ID,
            precision="civitai-bfloat16",
            acceleration="lightning-lora-4step-bf16",
            inference_steps=lightning_steps,
            true_cfg_scale=LIGHTNING_TRUE_CFG_SCALE,
        )
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
                true_cfg_scale=LIGHTNING_TRUE_CFG_SCALE,
                guidance_scale=1.0,
                num_inference_steps=lightning_steps,
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
            inference_steps=lightning_steps,
            true_cfg_scale=LIGHTNING_TRUE_CFG_SCALE,
            checkpoint_source="civitai",
            checkpoint_version_id=CIVITAI_VERSION_ID,
            checkpoint_file_id=CIVITAI_FILE_ID,
            precision="civitai-bfloat16",
            acceleration="lightning-lora-4step-bf16",
        )
        return payload
