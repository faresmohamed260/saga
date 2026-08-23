from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any

import modal

APP_NAME = "saga-ltx23-video"
COMFY_DIR = Path("/root/ComfyUI")
CACHE_DIR = Path("/cache")
MODEL_ROOT = CACHE_DIR / "studio-models"
OUTPUT_DIR = COMFY_DIR / "output"
INPUT_DIR = COMFY_DIR / "input"
SERVER = "127.0.0.1:8188"
FPS = 24

TRANSFORMER = "ltx-2.3-22b-distilled-1.1_transformer_only_mxfp8_block32.safetensors"
GEMMA = "gemma-3-12b-it-IQ4_XS.gguf"
CONNECTORS = "ltx-2.3-22b-distilled_embeddings_connectors.safetensors"
VIDEO_VAE = "ltx-2.3-22b-distilled_video_vae.safetensors"
AUDIO_VAE = "ltx-2.3-22b-distilled_audio_vae.safetensors"

RESOLUTIONS: dict[str, tuple[int, int]] = {
    "480p": (864, 480),
    "720p": (1280, 704),
    # Full HD / higher delivery tiers are enabled after the two-stage upscaler smoke test.
    "1080p": (1280, 704),
    "2K": (1280, 704),
    "4K": (1280, 704),
}

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "ffmpeg", "libgl1", "libglib2.0-0")
    .pip_install(
        "aiohttp>=3.11,<4",
        "fastapi>=0.115,<1",
        "python-multipart>=0.0.20,<1",
        "requests>=2.32,<3",
        "pillow>=11,<13",
    )
    .run_commands(
        "git clone --depth 1 https://github.com/Comfy-Org/ComfyUI.git /root/ComfyUI",
        "pip install -r /root/ComfyUI/requirements.txt",
        "git clone --depth 1 https://github.com/city96/ComfyUI-GGUF.git /root/ComfyUI/custom_nodes/ComfyUI-GGUF",
        "pip install -r /root/ComfyUI/custom_nodes/ComfyUI-GGUF/requirements.txt",
    )
)

cache_volume = modal.Volume.from_name("graduation-comfyui-cache", create_if_missing=False)
app = modal.App(APP_NAME, image=image)


def _source(name: str, folder: str) -> Path:
    path = MODEL_ROOT / folder / name
    if not path.exists():
        raise FileNotFoundError(f"Required cached model is missing: {path}")
    return path


def _link(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_symlink() or dst.exists():
        try:
            if dst.resolve() == src.resolve():
                return
        except OSError:
            pass
        dst.unlink()
    dst.symlink_to(src)


def _prepare_models() -> dict[str, str]:
    targets = {
        "transformer": (TRANSFORMER, "diffusion_models", COMFY_DIR / "models/diffusion_models" / TRANSFORMER),
        "gemma": (GEMMA, "text_encoders", COMFY_DIR / "models/text_encoders" / GEMMA),
        "connectors": (CONNECTORS, "text_encoders", COMFY_DIR / "models/text_encoders" / CONNECTORS),
        "video_vae": (VIDEO_VAE, "vae", COMFY_DIR / "models/vae" / VIDEO_VAE),
        # Core LTXVAudioVAELoader currently reads the checkpoints directory.
        "audio_vae": (AUDIO_VAE, "vae", COMFY_DIR / "models/checkpoints" / AUDIO_VAE),
    }
    result: dict[str, str] = {}
    for key, (name, folder, target) in targets.items():
        src = _source(name, folder)
        _link(src, target)
        result[key] = str(src)
    return result


def _request_json(path: str, payload: dict[str, Any] | None = None, timeout: int = 30) -> Any:
    url = f"http://{SERVER}{path}"
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _wait_server(timeout: int = 150) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            _request_json("/system_stats", timeout=3)
            return
        except Exception:
            time.sleep(1)
    raise RuntimeError("ComfyUI did not become ready")


def _upload_image(image_bytes: bytes, filename: str = "saga-video-reference.png") -> str:
    import requests

    response = requests.post(
        f"http://{SERVER}/upload/image",
        files={"image": (filename, image_bytes, "image/png")},
        data={"overwrite": "true", "type": "input"},
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("name") or filename


def _frame_count(duration_seconds: int) -> int:
    # 24 fps gives an 8n+1 valid LTX sequence for every whole-second duration.
    return int(duration_seconds) * FPS + 1


def _workflow(
    *,
    prompt: str,
    negative_prompt: str,
    seed: int,
    resolution: str,
    duration_seconds: int,
    audio_enabled: bool,
    source_name: str | None,
) -> dict[str, Any]:
    width, height = RESOLUTIONS[resolution]
    frames = _frame_count(duration_seconds)

    graph: dict[str, Any] = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": TRANSFORMER, "weight_dtype": "default"}},
        "2": {
            "class_type": "DualCLIPLoaderGGUF",
            "inputs": {"clip_name1": GEMMA, "clip_name2": CONNECTORS, "type": "ltxv"},
        },
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": VIDEO_VAE}},
        "4": {"class_type": "LTXVAudioVAELoader", "inputs": {"ckpt_name": AUDIO_VAE}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": negative_prompt, "clip": ["2", 0]}},
        "7": {
            "class_type": "LTXVConditioning",
            "inputs": {"positive": ["5", 0], "negative": ["6", 0], "frame_rate": FPS},
        },
        "8": {
            "class_type": "EmptyLTXVLatentVideo",
            "inputs": {"width": width, "height": height, "length": frames, "batch_size": 1},
        },
        "9": {
            "class_type": "LTXVEmptyLatentAudio",
            "inputs": {"audio_vae": ["4", 0], "frames_number": frames, "frame_rate": FPS, "batch_size": 1},
        },
        "12": {"class_type": "RandomNoise", "inputs": {"noise_seed": int(seed)}},
        "13": {"class_type": "CFGGuider", "inputs": {"model": ["1", 0], "positive": ["7", 0], "negative": ["7", 1], "cfg": 1.0}},
        "14": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "15": {
            "class_type": "ManualSigmas",
            "inputs": {"sigmas": "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"},
        },
        "16": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {"noise": ["12", 0], "guider": ["13", 0], "sampler": ["14", 0], "sigmas": ["15", 0], "latent_image": ["11", 0]},
        },
        "17": {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["16", 0]}},
        "18": {
            "class_type": "VAEDecodeTiled",
            "inputs": {"samples": ["17", 0], "vae": ["3", 0], "tile_size": 512, "overlap": 64, "temporal_size": 4096, "temporal_overlap": 4},
        },
        "20": {"class_type": "CreateVideo", "inputs": {"images": ["18", 0], "fps": FPS, "bit_depth": 8}},
        "21": {"class_type": "SaveVideo", "inputs": {"video": ["20", 0], "filename_prefix": "saga/ltx23", "format": "auto", "codec": "auto"}},
    }

    video_latent: list[Any] = ["8", 0]
    if source_name:
        graph["22"] = {"class_type": "LoadImage", "inputs": {"image": source_name}}
        graph["23"] = {"class_type": "LTXVPreprocess", "inputs": {"image": ["22", 0], "img_compression": 18}}
        graph["24"] = {
            "class_type": "LTXVImgToVideoInplace",
            "inputs": {"vae": ["3", 0], "image": ["23", 0], "latent": ["8", 0], "strength": 0.7, "bypass": False},
        }
        video_latent = ["24", 0]

    graph["11"] = {"class_type": "LTXVConcatAVLatent", "inputs": {"video_latent": video_latent, "audio_latent": ["9", 0]}}

    if audio_enabled:
        graph["19"] = {"class_type": "LTXVAudioVAEDecode", "inputs": {"samples": ["17", 1], "audio_vae": ["4", 0]}}
        graph["20"]["inputs"]["audio"] = ["19", 0]

    return graph


def _find_new_video(started_at: float) -> Path:
    candidates = [p for p in OUTPUT_DIR.rglob("*") if p.is_file() and p.stat().st_mtime >= started_at - 1]
    video_files = [p for p in candidates if p.suffix.lower() in {".mp4", ".webm", ".mov", ".mkv"}]
    if not video_files:
        raise RuntimeError(f"ComfyUI completed but no video output was found; files={[(str(p), p.stat().st_size) for p in candidates[-20:]]}")
    return max(video_files, key=lambda p: p.stat().st_mtime)


@app.cls(
    image=image,
    gpu="A10",
    timeout=3600,
    scaledown_window=300,
    volumes={str(CACHE_DIR): cache_volume},
)
@modal.concurrent(max_inputs=1)
class LTX23Worker:
    @modal.enter()
    def start(self) -> None:
        self.models = _prepare_models()
        INPUT_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.process = subprocess.Popen(
            [
                "python",
                "main.py",
                "--listen",
                "127.0.0.1",
                "--port",
                "8188",
                "--lowvram",
                "--reserve-vram",
                "2",
                "--disable-auto-launch",
            ],
            cwd=COMFY_DIR,
        )
        _wait_server()

    @modal.method()
    def health(self) -> dict[str, Any]:
        return {
            "ready": True,
            "app": APP_NAME,
            "gpu": "A10",
            "fps": FPS,
            "resolutions": RESOLUTIONS,
            "models": self.models,
        }

    @modal.method()
    def object_info(self) -> dict[str, Any]:
        info = _request_json("/object_info", timeout=90)
        wanted = {
            "UNETLoader",
            "DualCLIPLoaderGGUF",
            "VAELoader",
            "LTXVAudioVAELoader",
            "LTXVEmptyLatentAudio",
            "LTXVConcatAVLatent",
            "LTXVSeparateAVLatent",
            "LTXVConditioning",
            "LTXVImgToVideoInplace",
            "LTXVPreprocess",
            "CreateVideo",
            "SaveVideo",
        }
        return {name: info.get(name) for name in sorted(wanted)}

    @modal.method()
    def generate(
        self,
        prompt: str,
        negative_prompt: str = "pc game, console game, video game, cartoon, childish, ugly, watermark, subtitles, text overlay",
        seed: int = 42,
        resolution: str = "480p",
        duration_seconds: int = 5,
        audio_enabled: bool = True,
        source_image: bytes | None = None,
    ) -> bytes:
        prompt = (prompt or "").strip()
        if not prompt:
            raise ValueError("prompt is required")
        if resolution not in RESOLUTIONS:
            raise ValueError(f"unsupported resolution: {resolution}")
        if not 5 <= int(duration_seconds) <= 30:
            raise ValueError("duration_seconds must be between 5 and 30")
        # Until the two-stage upscaler is validated, high tiers intentionally use the safe 720p generation envelope.
        if resolution in {"1080p", "2K", "4K"}:
            raise ValueError(f"{resolution} is not enabled until the LTX 2.3 two-stage upscaler smoke test passes")

        source_name = _upload_image(source_image) if source_image else None
        graph = _workflow(
            prompt=prompt,
            negative_prompt=negative_prompt,
            seed=int(seed),
            resolution=resolution,
            duration_seconds=int(duration_seconds),
            audio_enabled=bool(audio_enabled),
            source_name=source_name,
        )
        started_at = time.time()
        client_id = str(uuid.uuid4())
        queued = _request_json("/prompt", {"prompt": graph, "client_id": client_id}, timeout=90)
        prompt_id = queued.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI rejected LTX workflow: {queued}")

        deadline = time.time() + 3300
        while time.time() < deadline:
            history = _request_json(f"/history/{prompt_id}", timeout=30)
            item = history.get(prompt_id)
            if item:
                status = item.get("status") or {}
                messages = status.get("messages") or []
                if status.get("status_str") == "error" or any(message and message[0] == "execution_error" for message in messages):
                    raise RuntimeError(f"ComfyUI LTX execution failed: {json.dumps(status)[:6000]}")
                if status.get("completed") is True:
                    video_path = _find_new_video(started_at)
                    return video_path.read_bytes()
            time.sleep(2)
        raise TimeoutError("LTX 2.3 generation timed out")
