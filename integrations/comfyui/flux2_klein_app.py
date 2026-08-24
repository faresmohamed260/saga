from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

import modal

APP_NAME = os.environ.get("MODAL_FLUX2_KLEIN_APP_NAME", "saga-flux2-klein-9b")
MODAL_VERSION = "1.4.2"
PYTHON_VERSION = "3.11"
COMFY_DIR = "/root/comfyui"
COMFY_PORT = 8188
CACHE_DIR = "/cache"
GPU_TYPE = os.environ.get("MODAL_FLUX2_KLEIN_GPU", "L40S")
FUNCTION_TIMEOUT_SECONDS = int(os.environ.get("MODAL_FLUX2_KLEIN_TIMEOUT_SECONDS", "1800"))
CONTAINER_IDLE_SECONDS = int(os.environ.get("MODAL_FLUX2_KLEIN_IDLE_SECONDS", "300"))
WORKER_MIN_CONTAINERS = 0
WORKER_MAX_CONTAINERS = int(os.environ.get("MODAL_FLUX2_KLEIN_MAX_CONTAINERS", "1"))
ECOSYSTEM_ID = "flux2-klein-9b"
WORKER_ID = os.environ.get("SAGA_MODAL_WORKER_ID", f"{ECOSYSTEM_ID}-worker")
STATE_DICT_NAME = os.environ.get("SAGA_MODAL_WORKER_STATE_DICT", "saga-flux2-klein-9b-worker-state")
CACHE_VOLUME_NAME = os.environ.get("SAGA_MODAL_WORKER_VOLUME", "saga-flux2-klein-9b-cache")

CHECKPOINT_NAME = "darkBeast_dbkleinv2BFS.safetensors"
CHECKPOINT_URL = "https://civitai.red/api/download/models/2740209?fileId=2626634"
TEXT_ENCODER_NAME = "qwen_3_8b_fp8mixed.safetensors"
VAE_NAME = "full_encoder_small_decoder.safetensors"
CHECKPOINT_CACHE = Path(CACHE_DIR) / "studio" / "flux2-klein-9b" / CHECKPOINT_NAME
WORKFLOW_BUNDLED_PATH = "/root/flux2_klein_9b_image_edit_api.json"
LOCAL_WORKFLOW_PATH = Path(__file__).parent / "workflows" / "flux2_klein_9b_image_edit_api.json"

cache_volume = modal.Volume.from_name(CACHE_VOLUME_NAME, create_if_missing=True)
worker_state = modal.Dict.from_name(STATE_DICT_NAME, create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version=PYTHON_VERSION)
    .apt_install("git", "ffmpeg", "libgl1", "libglib2.0-0", "libsm6", "libxrender1", "libxext6")
    .pip_install(
        f"modal=={MODAL_VERSION}",
        "aiohttp>=3.11.8",
        "fastapi[standard]==0.121.0",
        "huggingface_hub[hf_transfer]==0.36.0",
    )
    .env(
        {
            "HF_HUB_ENABLE_HF_TRANSFER": "1",
            "HF_HUB_CACHE": CACHE_DIR,
            "COMFYUI_DISABLE_TELEMETRY": "1",
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        }
    )
    .run_commands(
        f"git clone --depth 1 https://github.com/Comfy-Org/ComfyUI.git {COMFY_DIR}",
        f"cd {COMFY_DIR} && pip install -r requirements.txt",
    )
    .add_local_file(LOCAL_WORKFLOW_PATH, WORKFLOW_BUNDLED_PATH)
)

app = modal.App(APP_NAME, image=image)


def _log(event: str, **fields: Any) -> None:
    print({"event": event, **fields}, flush=True)


def _set_worker_state(state: str, **fields: Any) -> None:
    payload = {"state": state, "worker_id": WORKER_ID, "ecosystem": ECOSYSTEM_ID, "updated_at": int(time.time()), **fields}
    worker_state["worker"] = payload
    _log("worker_state", **payload)


def _find_cached_file(name: str) -> Path | None:
    direct_candidates = [
        Path(CACHE_DIR) / "studio" / "flux2-klein-9b" / name,
        Path(CACHE_DIR) / "weights" / name,
    ]
    for candidate in direct_candidates:
        if candidate.is_file():
            return candidate
    try:
        for candidate in Path(CACHE_DIR).rglob(name):
            if candidate.is_file():
                return candidate
    except OSError:
        return None
    return None


def _download_stream(url: str, destination: Path, *, bearer_token: str = "") -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix(destination.suffix + ".part")
    if temp.exists():
        temp.unlink()

    resolved_url = url
    if bearer_token:
        parsed = urllib.parse.urlsplit(url)
        query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if not any(key == "token" for key, _ in query):
            query.append(("token", bearer_token))
        resolved_url = urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), parsed.fragment)
        )

    headers = {"User-Agent": "SAGA-Studio/1.0"}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    request = urllib.request.Request(resolved_url, headers=headers)
    with urllib.request.urlopen(request, timeout=120) as response, temp.open("wb") as out:
        shutil.copyfileobj(response, out, length=16 * 1024 * 1024)
    temp.replace(destination)
    return destination


def _ensure_checkpoint(*, force: bool = False) -> Path:
    if not force:
        existing = _find_cached_file(CHECKPOINT_NAME)
        if existing:
            return existing
    token = str(os.environ.get("CIVITAI_API_TOKEN") or "").strip()
    started = time.perf_counter()
    path = _download_stream(CHECKPOINT_URL, CHECKPOINT_CACHE, bearer_token=token)
    cache_volume.commit()
    _log(
        "flux2_klein_checkpoint_downloaded",
        path=str(path),
        elapsed_seconds=round(time.perf_counter() - started, 3),
    )
    return path


def _ensure_hf_model(*, repo_id: str, filename: str, target_name: str) -> Path:
    existing = _find_cached_file(target_name)
    if existing:
        return existing
    from huggingface_hub import hf_hub_download

    token = str(os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN") or "").strip() or None
    path = Path(hf_hub_download(repo_id=repo_id, filename=filename, cache_dir=CACHE_DIR, token=token))
    cache_volume.commit()
    return path


def _ensure_model_files(*, force_checkpoint: bool = False) -> dict[str, Path]:
    checkpoint = _ensure_checkpoint(force=force_checkpoint)
    text_encoder = _ensure_hf_model(
        repo_id="Comfy-Org/flux2-klein-9B",
        filename="split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors",
        target_name=TEXT_ENCODER_NAME,
    )
    vae = _ensure_hf_model(
        repo_id="black-forest-labs/FLUX.2-small-decoder",
        filename=VAE_NAME,
        target_name=VAE_NAME,
    )
    return {"checkpoint": checkpoint, "text_encoder": text_encoder, "vae": vae}


def _safe_link(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        destination.unlink()
    destination.symlink_to(source)


def _link_models(files: dict[str, Path]) -> None:
    _safe_link(files["checkpoint"], Path(COMFY_DIR) / "models" / "diffusion_models" / CHECKPOINT_NAME)
    _safe_link(files["text_encoder"], Path(COMFY_DIR) / "models" / "text_encoders" / TEXT_ENCODER_NAME)
    _safe_link(files["vae"], Path(COMFY_DIR) / "models" / "vae" / VAE_NAME)


def _load_workflow() -> dict[str, Any]:
    return json.loads(Path(WORKFLOW_BUNDLED_PATH).read_text(encoding="utf-8"))


def _request_json(url: str, data: bytes | None = None) -> Any:
    request = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def _request_bytes(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


@app.function(image=image, timeout=FUNCTION_TIMEOUT_SECONDS, volumes={CACHE_DIR: cache_volume})
def prefetch_klein(force_checkpoint: bool = False) -> dict[str, Any]:
    started = time.perf_counter()
    files = _ensure_model_files(force_checkpoint=force_checkpoint)
    _set_worker_state("sleeping", assets_cached=True)
    return {
        "ready": True,
        "model": "flux2-klein-9b-darkbeast-v2-bfs",
        "files": {key: str(value) for key, value in files.items()},
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }


@app.cls(
    image=image,
    gpu=GPU_TYPE,
    timeout=FUNCTION_TIMEOUT_SECONDS,
    scaledown_window=CONTAINER_IDLE_SECONDS,
    min_containers=WORKER_MIN_CONTAINERS,
    max_containers=WORKER_MAX_CONTAINERS,
    volumes={CACHE_DIR: cache_volume},
)
@modal.concurrent(max_inputs=1)
class Flux2KleinWorker:
    port: int = COMFY_PORT

    @modal.enter()
    def start(self) -> None:
        _set_worker_state("loading")
        started = time.perf_counter()
        files = _ensure_model_files(force_checkpoint=False)
        _link_models(files)
        self._process = subprocess.Popen(
            [
                "python",
                "main.py",
                "--listen",
                "0.0.0.0",
                "--port",
                str(self.port),
                "--disable-auto-launch",
                "--preview-method",
                "none",
            ],
            cwd=COMFY_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._wait_until_ready()
        self._status = {
            "ready": True,
            "app": APP_NAME,
            "model": "flux2-klein-9b-darkbeast-v2-bfs",
            "gpu": GPU_TYPE,
            "startup_seconds": round(time.perf_counter() - started, 3),
            "checkpoint": CHECKPOINT_NAME,
            "text_encoder": TEXT_ENCODER_NAME,
            "vae": VAE_NAME,
            "multiple_references": True,
        }
        _set_worker_state("ready", startup_seconds=self._status["startup_seconds"])
        _log("flux2_klein_worker_ready", **self._status)

    def _wait_until_ready(self) -> None:
        deadline = time.time() + 300
        last_error: Exception | None = None
        while time.time() < deadline:
            try:
                _request_json(f"http://127.0.0.1:{self.port}/system_stats")
                return
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                time.sleep(2)
        raise RuntimeError(f"ComfyUI failed to start: {last_error}")

    def _stage_image_bytes(self, image_bytes: bytes, filename: str) -> str:
        safe_name = f"saga_flux2_{uuid.uuid4().hex[:12]}_{Path(filename).name or 'input.png'}"
        target = Path(COMFY_DIR) / "input" / safe_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(image_bytes)
        return safe_name

    def _build_workflow(
        self,
        *,
        input_names: list[str],
        prompt: str,
        negative_prompt: str,
        seed: int,
        steps: int,
        cfg: float,
        filename_prefix: str,
        megapixels: float,
    ) -> dict[str, Any]:
        if not input_names:
            raise ValueError("at least one input image is required")

        workflow = copy.deepcopy(_load_workflow())
        workflow["1"]["inputs"]["image"] = input_names[0]
        workflow["2"]["inputs"]["megapixels"] = float(megapixels)
        workflow["8"]["inputs"]["text"] = prompt
        workflow["9"]["inputs"]["text"] = negative_prompt
        workflow["12"]["inputs"]["cfg"] = float(cfg)
        workflow["13"]["inputs"]["noise_seed"] = int(seed)
        workflow["15"]["inputs"]["steps"] = int(steps)
        workflow["19"]["inputs"]["filename_prefix"] = filename_prefix

        positive_node = "10"
        negative_node = "11"
        auxiliary_megapixels = min(float(megapixels), 1.0)

        for reference_index, input_name in enumerate(input_names[1:], start=2):
            base = 100 + (reference_index - 2) * 5
            load_node = str(base)
            scale_node = str(base + 1)
            encode_node = str(base + 2)
            positive_reference_node = str(base + 3)
            negative_reference_node = str(base + 4)

            workflow[load_node] = {
                "class_type": "LoadImage",
                "inputs": {"image": input_name},
                "_meta": {"title": f"Reference Image {reference_index}"},
            }
            workflow[scale_node] = {
                "class_type": "ImageScaleToTotalPixels",
                "inputs": {
                    "upscale_method": "lanczos",
                    "megapixels": auxiliary_megapixels,
                    "resolution_steps": 1,
                    "image": [load_node, 0],
                },
                "_meta": {"title": f"Normalize Reference {reference_index}"},
            }
            workflow[encode_node] = {
                "class_type": "VAEEncode",
                "inputs": {"pixels": [scale_node, 0], "vae": ["7", 0]},
                "_meta": {"title": f"Reference {reference_index} latent"},
            }
            workflow[positive_reference_node] = {
                "class_type": "ReferenceLatent",
                "inputs": {"conditioning": [positive_node, 0], "latent": [encode_node, 0]},
                "_meta": {"title": f"Positive reference {reference_index}"},
            }
            workflow[negative_reference_node] = {
                "class_type": "ReferenceLatent",
                "inputs": {"conditioning": [negative_node, 0], "latent": [encode_node, 0]},
                "_meta": {"title": f"Negative reference {reference_index}"},
            }
            positive_node = positive_reference_node
            negative_node = negative_reference_node

        workflow["12"]["inputs"]["positive"] = [positive_node, 0]
        workflow["12"]["inputs"]["negative"] = [negative_node, 0]
        return workflow

    def _queue_and_wait(self, workflow: dict[str, Any], prompt_id: str) -> bytes:
        payload = {"prompt": workflow, "prompt_id": prompt_id, "client_id": prompt_id}
        response = _request_json(
            f"http://127.0.0.1:{self.port}/prompt",
            data=json.dumps(payload).encode("utf-8"),
        )
        if response.get("error") or response.get("node_errors"):
            raise RuntimeError(f"ComfyUI rejected FLUX.2 Klein workflow: {response!r}")

        deadline = time.time() + 1500
        while time.time() < deadline:
            history = _request_json(f"http://127.0.0.1:{self.port}/history/{prompt_id}")
            item = history.get(prompt_id)
            if item:
                for node_output in (item.get("outputs") or {}).values():
                    for output_image in node_output.get("images", []):
                        query = urllib.parse.urlencode(
                            {
                                "filename": output_image["filename"],
                                "subfolder": output_image.get("subfolder", ""),
                                "type": output_image.get("type", "output"),
                            }
                        )
                        return _request_bytes(f"http://127.0.0.1:{self.port}/view?{query}")
                status = item.get("status") if isinstance(item.get("status"), dict) else {}
                if status.get("completed") is True:
                    raise RuntimeError(f"FLUX.2 Klein workflow completed without image output: {item!r}")
                if str(status.get("status_str") or "").lower() in {"error", "failed", "execution_error"}:
                    raise RuntimeError(f"FLUX.2 Klein workflow failed: {item!r}")
            time.sleep(1)
        raise TimeoutError(f"Timed out waiting for FLUX.2 Klein prompt {prompt_id}")

    @modal.method()
    def status(self) -> dict[str, Any]:
        return dict(self._status)

    @modal.method()
    def edit(
        self,
        *,
        images: list[dict[str, Any]] | None = None,
        image_bytes: bytes = b"",
        filename: str = "input.png",
        prompt: str,
        negative_prompt: str = "",
        seed: int = 42,
        steps: int = 4,
        cfg: float = 1.0,
        megapixels: float = 1.0,
    ) -> bytes:
        normalized_images = list(images or [])
        if not normalized_images and image_bytes:
            normalized_images = [{"bytes": image_bytes, "filename": filename, "content_type": "image/png"}]
        if not normalized_images:
            raise ValueError("at least one reference image is required")
        if not str(prompt or "").strip():
            raise ValueError("prompt is required")

        input_names = []
        for index, image in enumerate(normalized_images):
            reference_bytes = image.get("bytes") if isinstance(image, dict) else None
            reference_filename = image.get("filename") if isinstance(image, dict) else None
            if not reference_bytes:
                raise ValueError(f"Image {index + 1} is empty")
            input_names.append(self._stage_image_bytes(reference_bytes, str(reference_filename or f"input-{index + 1}.png")))

        prompt_id = str(uuid.uuid4())
        prefix = f"SAGA/flux2-klein-9b/{prompt_id[:12]}"
        workflow = self._build_workflow(
            input_names=input_names,
            prompt=str(prompt).strip(),
            negative_prompt=str(negative_prompt or ""),
            seed=int(seed),
            steps=max(1, min(int(steps), 50)),
            cfg=float(cfg),
            filename_prefix=prefix,
            megapixels=max(0.25, min(float(megapixels), 4.0)),
        )
        _set_worker_state("generating", job_token=prompt_id[:12])
        started = time.perf_counter()
        try:
            result = self._queue_and_wait(workflow, prompt_id)
            _set_worker_state("finalizing", job_token=prompt_id[:12])
        except Exception:
            _set_worker_state("failed", job_token=prompt_id[:12])
            raise
        _log(
            "flux2_klein_edit_completed",
            prompt_id=prompt_id,
            elapsed_seconds=round(time.perf_counter() - started, 3),
            byte_length=len(result),
            reference_count=len(input_names),
            steps=int(steps),
            cfg=float(cfg),
        )
        _set_worker_state("ready")
        return result

    @modal.exit()
    def stop(self) -> None:
        _set_worker_state("sleeping")


@app.function(image=image, timeout=FUNCTION_TIMEOUT_SECONDS, volumes={CACHE_DIR: cache_volume})
@modal.asgi_app()
def web():
    from fastapi import FastAPI, File, Form, HTTPException, UploadFile
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import Response

    api = FastAPI(title="SAGA FLUX.2 Klein 9B", version="0.2.0")
    origins = [
        origin.strip()
        for origin in str(
            os.environ.get(
                "SAGA_STUDIO_ALLOWED_ORIGINS",
                "https://studio.faresuniform.uk,http://localhost:5173",
            )
        ).split(",")
        if origin.strip()
    ]
    api.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @api.get("/health")
    async def health_route():
        return {
            "ready": True,
            "app": APP_NAME,
            "model": "flux2-klein-9b-darkbeast-v2-bfs",
            "gpu": GPU_TYPE,
            "checkpoint_cached": _find_cached_file(CHECKPOINT_NAME) is not None,
            "text_encoder_cached": _find_cached_file(TEXT_ENCODER_NAME) is not None,
            "vae_cached": _find_cached_file(VAE_NAME) is not None,
            "multiple_references": True,
        }

    @api.post("/edit")
    async def edit_route(
        image_file: UploadFile = File(...),
        prompt: str = Form(...),
        negative_prompt: str = Form(""),
        seed: int = Form(42),
        steps: int = Form(4),
        cfg: float = Form(1.0),
        megapixels: float = Form(1.0),
    ):
        if not image_file.content_type or not image_file.content_type.startswith("image/"):
            raise HTTPException(status_code=415, detail="image_file must be an image")
        image_bytes = await image_file.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="image_file is empty")
        if len(image_bytes) > 25 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="image_file must be 25 MB or smaller")
        if not prompt.strip():
            raise HTTPException(status_code=400, detail="prompt is required")

        result = Flux2KleinWorker().edit.remote(
            images=[
                {
                    "bytes": image_bytes,
                    "filename": image_file.filename or "input.png",
                    "content_type": image_file.content_type or "image/png",
                }
            ],
            prompt=prompt,
            negative_prompt=negative_prompt,
            seed=seed,
            steps=steps,
            cfg=cfg,
            megapixels=megapixels,
        )
        return Response(content=result, media_type="image/png")

    return api
