from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

import modal

APP_NAME = "saga-ltx25-video"
COMFY_DIR = Path("/root/ComfyUI")
CACHE_DIR = Path("/cache")
MODEL_ROOT = CACHE_DIR / "studio-models"
OUTPUT_DIR = COMFY_DIR / "output"
INPUT_DIR = COMFY_DIR / "input"
SERVER = "127.0.0.1:8188"
DEFAULT_FPS = 24
FRAME_RATES = {24, 25, 30}
GPU_CHOICES = [x.strip() for x in os.environ.get("MODAL_LTX25_GPU", "L40S,A100-40GB").split(",") if x.strip()]
GPU_REQUEST: str | list[str] = GPU_CHOICES[0] if len(GPU_CHOICES) == 1 else GPU_CHOICES
GPU_LABEL = ",".join(GPU_CHOICES)
CONTAINER_IDLE_SECONDS = int(os.environ.get("MODAL_LTX25_IDLE_SECONDS", "180"))
WORKER_MIN_CONTAINERS = 0
WORKER_MAX_CONTAINERS = int(os.environ.get("MODAL_LTX25_MAX_CONTAINERS", "1"))
ECOSYSTEM_ID = "ltx25-redgraft"
WORKER_ID = os.environ.get("SAGA_MODAL_WORKER_ID", f"{ECOSYSTEM_ID}-worker")
STATE_DICT_NAME = os.environ.get("SAGA_MODAL_WORKER_STATE_DICT", "saga-ltx25-redgraft-worker-state")
CACHE_VOLUME_NAME = os.environ.get("SAGA_MODAL_WORKER_VOLUME", "saga-ltx25-redgraft-cache")

CHECKPOINT = "REDGraft-ltx25-sulphur2-int8-convrot-ComfyMCP.safetensors"
CHECKPOINT_URL = "https://civitai.red/api/download/models/3250230?fileId=3133376"
CHECKPOINT_AUTOV2 = "AB59BB5E74"

TEXT_ENCODER = "gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors"
VIDEO_VAE = "ltx-2.5-video-vae-conv-bf16.safetensors"
AUDIO_VAE = "ltx-2.5-audio-vae-bf16.safetensors"
SPATIAL_UPSCALER = "ltx-2.3-spatial-upscaler-x2-1.1.safetensors"

HF_REPO = "Lightricks/LTX-2.5"
HF_BASE = f"https://huggingface.co/{HF_REPO}/resolve/main"
TEXT_ENCODER_URL = f"{HF_BASE}/text_encoders/{TEXT_ENCODER}"
VIDEO_VAE_URL = f"{HF_BASE}/vae/{VIDEO_VAE}"
AUDIO_VAE_URL = f"{HF_BASE}/vae/{AUDIO_VAE}"
SPATIAL_UPSCALER_URL = (
    f"https://huggingface.co/Lightricks/LTX-2.3/resolve/main/{SPATIAL_UPSCALER}"
)

# Final two-stage delivery dimensions. All dimensions are divisible by 64 so the
# low-resolution stage remains divisible by 32 after halving.
RESOLUTIONS: dict[str, tuple[int, int]] = {
    "480p": (896, 512),
    "720p": (1280, 704),
    "1080p": (1920, 1088),
    "2K": (2048, 1152),
    "4K": (3840, 2176),
}
ENABLED_RESOLUTIONS = {"480p", "720p", "1080p", "2K"}
RESOLUTION_SHORT_EDGES = {"480p": 480, "720p": 720, "1080p": 1080, "2K": 1152, "4K": 2160}

LOW_STAGE_SIGMAS = "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"
HIGH_STAGE_SIGMAS = "0.85, 0.7250, 0.4219, 0.0"

cache_volume = modal.Volume.from_name(CACHE_VOLUME_NAME, create_if_missing=True)
worker_state = modal.Dict.from_name(STATE_DICT_NAME, create_if_missing=True)

_runtime_secret_values: dict[str, str] = {}
for _name in ("HF_TOKEN", "CIVITAI_API_TOKEN"):
    _value = str(os.environ.get(_name) or "").strip()
    if _value:
        _runtime_secret_values[_name] = _value
RUNTIME_SECRETS = [modal.Secret.from_dict(_runtime_secret_values)] if _runtime_secret_values else []

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "ffmpeg", "libgl1", "libglib2.0-0", "libsm6", "libxrender1", "libxext6")
    .pip_install(
        "aiohttp>=3.11,<4",
        "fastapi>=0.115,<1",
        "python-multipart>=0.0.20,<1",
        "requests>=2.32,<3",
        "pillow>=11,<13",
    )
    .env({
        "COMFYUI_DISABLE_TELEMETRY": "1",
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "SAGA_MODAL_WORKER_ID": WORKER_ID,
        "SAGA_MODAL_WORKER_STATE_DICT": STATE_DICT_NAME,
        "SAGA_MODAL_WORKER_VOLUME": CACHE_VOLUME_NAME,
    })
    .run_commands(
        "git clone --depth 1 https://github.com/Comfy-Org/ComfyUI.git /root/ComfyUI",
        "pip install -r /root/ComfyUI/requirements.txt",
    )
)

app = modal.App(APP_NAME, image=image)


def _log(event: str, **fields: Any) -> None:
    print({"event": event, **fields}, flush=True)


def _set_worker_state(state: str, **fields: Any) -> None:
    payload = {"state": state, "worker_id": WORKER_ID, "ecosystem": ECOSYSTEM_ID, "updated_at": int(time.time()), **fields}
    worker_state["worker"] = payload
    _log("worker_state", **payload)


def _safe_link(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink() or destination.exists():
        try:
            if destination.resolve() == source.resolve():
                return
        except OSError:
            pass
        destination.unlink()
    destination.symlink_to(source)


def _append_civitai_token(url: str, token: str) -> str:
    if not token:
        return url
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    if not any(key == "token" for key, _ in query):
        query.append(("token", token))
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), parsed.fragment)
    )


def _download_stream(
    url: str,
    destination: Path,
    *,
    token: str = "",
    min_bytes: int = 1,
    civitai: bool = False,
) -> Path:
    import requests

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and destination.stat().st_size >= min_bytes:
        return destination

    partial = destination.with_suffix(destination.suffix + ".part")
    resume_from = partial.stat().st_size if partial.exists() else 0
    resolved_url = _append_civitai_token(url, token) if civitai else url
    headers = {"User-Agent": "SAGA-Studio/1.0"}
    if token and not civitai:
        headers["Authorization"] = f"Bearer {token}"
    if resume_from:
        headers["Range"] = f"bytes={resume_from}-"

    response = requests.get(
        resolved_url,
        headers=headers,
        stream=True,
        allow_redirects=True,
        timeout=(30, 600),
    )
    if resume_from and response.status_code != 206:
        response.close()
        partial.unlink(missing_ok=True)
        resume_from = 0
        headers.pop("Range", None)
        response = requests.get(
            resolved_url,
            headers=headers,
            stream=True,
            allow_redirects=True,
            timeout=(30, 600),
        )
    response.raise_for_status()

    mode = "ab" if resume_from and response.status_code == 206 else "wb"
    with partial.open(mode) as handle:
        for chunk in response.iter_content(chunk_size=32 * 1024 * 1024):
            if chunk:
                handle.write(chunk)
    response.close()

    if partial.stat().st_size < min_bytes:
        size = partial.stat().st_size
        raise RuntimeError(f"Downloaded asset is unexpectedly small: {destination.name} bytes={size}")

    partial.replace(destination)
    return destination


def _asset_path(folder: str, name: str) -> Path:
    return MODEL_ROOT / folder / name


def _ensure_asset(
    *,
    folder: str,
    name: str,
    url: str,
    min_bytes: int,
    token_name: str = "",
    civitai: bool = False,
) -> Path:
    destination = _asset_path(folder, name)
    if destination.is_file() and destination.stat().st_size >= min_bytes:
        return destination
    token = str(os.environ.get(token_name) or "").strip() if token_name else ""
    started = time.perf_counter()
    result = _download_stream(
        url,
        destination,
        token=token,
        min_bytes=min_bytes,
        civitai=civitai,
    )
    cache_volume.commit()
    _log(
        "ltx25_asset_downloaded",
        name=name,
        bytes=result.stat().st_size,
        elapsed_seconds=round(time.perf_counter() - started, 3),
    )
    return result


def _verify_checkpoint(path: Path) -> str:
    marker = path.with_suffix(path.suffix + f".autov2-{CHECKPOINT_AUTOV2.lower()}")
    if marker.is_file():
        return CHECKPOINT_AUTOV2
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(64 * 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    prefix = digest.hexdigest()[:10].upper()
    if prefix != CHECKPOINT_AUTOV2:
        raise RuntimeError(
            f"Checkpoint hash mismatch for {CHECKPOINT}: expected {CHECKPOINT_AUTOV2}, got {prefix}"
        )
    marker.write_text(prefix + "\n", encoding="utf-8")
    cache_volume.commit()
    return prefix


def _ensure_model_files(*, verify_checkpoint: bool = True) -> dict[str, Path]:
    checkpoint = _ensure_asset(
        folder="diffusion_models",
        name=CHECKPOINT,
        url=CHECKPOINT_URL,
        min_bytes=15_000_000_000,
        token_name="CIVITAI_API_TOKEN",
        civitai=True,
    )
    if verify_checkpoint:
        _verify_checkpoint(checkpoint)

    text_encoder = _ensure_asset(
        folder="text_encoders",
        name=TEXT_ENCODER,
        url=TEXT_ENCODER_URL,
        min_bytes=14_000_000_000,
        token_name="HF_TOKEN",
    )
    video_vae = _ensure_asset(
        folder="vae",
        name=VIDEO_VAE,
        url=VIDEO_VAE_URL,
        min_bytes=1_000_000_000,
        token_name="HF_TOKEN",
    )
    audio_vae = _ensure_asset(
        folder="vae",
        name=AUDIO_VAE,
        url=AUDIO_VAE_URL,
        min_bytes=300_000_000,
        token_name="HF_TOKEN",
    )
    upscaler = _ensure_asset(
        folder="latent_upscale_models",
        name=SPATIAL_UPSCALER,
        url=SPATIAL_UPSCALER_URL,
        min_bytes=800_000_000,
        token_name="HF_TOKEN",
    )
    return {
        "checkpoint": checkpoint,
        "text_encoder": text_encoder,
        "video_vae": video_vae,
        "audio_vae": audio_vae,
        "spatial_upscaler": upscaler,
    }


def _prepare_models(files: dict[str, Path]) -> dict[str, str]:
    targets = {
        "checkpoint": COMFY_DIR / "models/diffusion_models" / CHECKPOINT,
        "text_encoder": COMFY_DIR / "models/text_encoders" / TEXT_ENCODER,
        "video_vae": COMFY_DIR / "models/vae" / VIDEO_VAE,
        "audio_vae": COMFY_DIR / "models/vae" / AUDIO_VAE,
        "spatial_upscaler": COMFY_DIR / "models/latent_upscale_models" / SPATIAL_UPSCALER,
    }
    result: dict[str, str] = {}
    for key, target in targets.items():
        _safe_link(files[key], target)
        result[key] = str(files[key])
    return result


def _request_json(path: str, payload: dict[str, Any] | None = None, timeout: int = 30) -> Any:
    url = f"http://{SERVER}{path}"
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _wait_server(timeout: int = 240) -> None:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            _request_json("/system_stats", timeout=3)
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(1)
    raise RuntimeError(f"ComfyUI did not become ready: {last_error}")


def _upload_image(image_bytes: bytes, filename: str = "saga-video-reference.png") -> str:
    import requests

    response = requests.post(
        f"http://{SERVER}/upload/image",
        files={"image": (filename, image_bytes, "application/octet-stream")},
        data={"overwrite": "true", "type": "input"},
        timeout=120,
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("name") or filename


def _parse_aspect_ratio(value: str) -> float:
    left, separator, right = str(value or "16:9").strip().partition(":")
    if not separator:
        raise ValueError("aspect_ratio must be W:H")
    width = float(left)
    height = float(right)
    ratio = width / height
    if not math.isfinite(ratio) or ratio < 0.4 or ratio > 2.5:
        raise ValueError("aspect_ratio is outside the supported range")
    return ratio


def _even(value: float) -> int:
    # Delivery dimensions are positive. Use explicit half-up rounding so exact
    # odd-pixel ties match JavaScript Math.round in Studio instead of Python's
    # bankers rounding (for example 481px -> 482px, not 480px).
    return max(2, int(math.floor(float(value) / 2.0 + 0.5)) * 2)


def _align64(value: int) -> int:
    return max(64, int(math.ceil(int(value) / 64.0)) * 64)


def _delivery_dimensions(resolution: str, aspect_ratio: str) -> tuple[int, int]:
    ratio = _parse_aspect_ratio(aspect_ratio)
    short_edge = RESOLUTION_SHORT_EDGES[resolution]
    if ratio >= 1:
        height = short_edge
        width = _even(height * ratio)
    else:
        width = short_edge
        height = _even(width / ratio)
    return width, height


def _internal_dimensions(resolution: str, aspect_ratio: str) -> tuple[int, int]:
    width, height = _delivery_dimensions(resolution, aspect_ratio)
    return _align64(width), _align64(height)


def _frame_count(duration_seconds: int, frame_rate: int) -> int:
    requested = int(duration_seconds) * int(frame_rate) + 1
    # LTX temporal latents require 8n+1 frames. Pad upward so selectable
    # frame rates keep the requested duration as closely as possible.
    return ((requested - 2) // 8 + 1) * 8 + 1


def _workflow(
    *,
    prompt: str,
    seed: int,
    resolution: str,
    duration_seconds: int,
    audio_enabled: bool,
    aspect_ratio: str,
    frame_rate: int,
    source_name: str | None,
    output_token: str,
) -> dict[str, Any]:
    target_width, target_height = _internal_dimensions(resolution, aspect_ratio)
    low_width, low_height = target_width // 2, target_height // 2
    frames = _frame_count(duration_seconds, frame_rate)

    graph: dict[str, Any] = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": CHECKPOINT, "weight_dtype": "default"}},
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": TEXT_ENCODER, "type": "ltxv", "device": "default"},
        },
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": VIDEO_VAE}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": AUDIO_VAE}},
        "5": {"class_type": "LatentUpscaleModelLoader", "inputs": {"model_name": SPATIAL_UPSCALER}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        "7": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["6", 0]}},
        "8": {
            "class_type": "LTXVConditioning",
            "inputs": {"positive": ["6", 0], "negative": ["7", 0], "frame_rate": frame_rate},
        },
        "9": {
            "class_type": "EmptyLTXVLatentVideo",
            "inputs": {"width": low_width, "height": low_height, "length": frames, "batch_size": 1},
        },
        "10": {
            "class_type": "LTXVEmptyLatentAudio",
            "inputs": {"audio_vae": ["4", 0], "frames_number": frames, "frame_rate": frame_rate, "batch_size": 1},
        },
        "12": {"class_type": "LTXVConcatAVLatent", "inputs": {"video_latent": ["9", 0], "audio_latent": ["10", 0]}},
        "13": {"class_type": "RandomNoise", "inputs": {"noise_seed": int(seed)}},
        "14": {
            "class_type": "CFGGuider",
            "inputs": {"model": ["1", 0], "positive": ["8", 0], "negative": ["8", 1], "cfg": 1.0},
        },
        "15": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "16": {"class_type": "ManualSigmas", "inputs": {"sigmas": LOW_STAGE_SIGMAS}},
        "17": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["13", 0],
                "guider": ["14", 0],
                "sampler": ["15", 0],
                "sigmas": ["16", 0],
                "latent_image": ["12", 0],
            },
        },
        "18": {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["17", 0]}},
        "19": {
            "class_type": "LTXVCropGuides",
            "inputs": {"positive": ["8", 0], "negative": ["8", 1], "latent": ["18", 0]},
        },
        "20": {
            "class_type": "LTXVLatentUpsampler",
            "inputs": {"samples": ["18", 0], "upscale_model": ["5", 0], "vae": ["3", 0]},
        },
        "21": {
            "class_type": "LatentUpscaleBy",
            "inputs": {"samples": ["20", 0], "upscale_method": "bicubic", "scale_by": 1.0},
        },
        "23": {"class_type": "LTXVConcatAVLatent", "inputs": {"video_latent": ["21", 0], "audio_latent": ["18", 1]}},
        "24": {"class_type": "RandomNoise", "inputs": {"noise_seed": int(seed) + 1}},
        "25": {
            "class_type": "CFGGuider",
            "inputs": {"model": ["1", 0], "positive": ["19", 0], "negative": ["19", 1], "cfg": 1.0},
        },
        "26": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "27": {"class_type": "ManualSigmas", "inputs": {"sigmas": HIGH_STAGE_SIGMAS}},
        "28": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["24", 0],
                "guider": ["25", 0],
                "sampler": ["26", 0],
                "sigmas": ["27", 0],
                "latent_image": ["23", 0],
            },
        },
        "29": {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["28", 0]}},
        "30": {
            "class_type": "VAEDecodeTiled",
            "inputs": {
                "samples": ["29", 0],
                "vae": ["3", 0],
                "tile_size": 480,
                "overlap": 96,
                "temporal_size": 96,
                "temporal_overlap": 24,
            },
        },
        "32": {"class_type": "CreateVideo", "inputs": {"images": ["30", 0], "fps": frame_rate, "bit_depth": 8}},
        "33": {
            "class_type": "SaveVideo",
            "inputs": {
                "video": ["32", 0],
                "filename_prefix": f"saga/ltx25-redgraft-{output_token}",
                "format": "auto",
                "codec": "auto",
            },
        },
    }

    if source_name:
        graph["40"] = {"class_type": "LoadImage", "inputs": {"image": source_name}}
        graph["41"] = {
            "class_type": "ImageScale",
            "inputs": {
                "image": ["40", 0],
                "upscale_method": "lanczos",
                "width": target_width,
                "height": target_height,
                "crop": "center",
            },
        }
        graph["42"] = {"class_type": "LTXVPreprocess", "inputs": {"image": ["41", 0], "img_compression": 18}}
        graph["43"] = {
            "class_type": "LTXVImgToVideoInplace",
            "inputs": {
                "vae": ["3", 0],
                "image": ["42", 0],
                "latent": ["9", 0],
                "strength": 0.7,
                "bypass": False,
            },
        }
        graph["12"]["inputs"]["video_latent"] = ["43", 0]
        graph["44"] = {
            "class_type": "LTXVImgToVideoInplace",
            "inputs": {
                "vae": ["3", 0],
                "image": ["42", 0],
                "latent": ["21", 0],
                "strength": 1.0,
                "bypass": False,
            },
        }
        graph["23"]["inputs"]["video_latent"] = ["44", 0]

    if audio_enabled:
        graph["31"] = {
            "class_type": "LTXVAudioVAEDecode",
            "inputs": {"samples": ["29", 1], "audio_vae": ["4", 0]},
        }
        graph["32"]["inputs"]["audio"] = ["31", 0]

    return graph


def _history_video_paths(history_item: dict[str, Any] | None) -> list[Path]:
    video_suffixes = {".mp4", ".webm", ".mov", ".mkv"}
    found: list[Path] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            filename = value.get("filename")
            if isinstance(filename, str) and Path(filename).suffix.lower() in video_suffixes:
                subfolder = value.get("subfolder") or ""
                folder_type = str(value.get("type") or value.get("folder_type") or "output").lower()
                if folder_type in {"output", "temp"}:
                    root = OUTPUT_DIR if folder_type == "output" else COMFY_DIR / "temp"
                    found.append(root / str(subfolder) / filename)
            for child in value.values():
                visit(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                visit(child)

    if history_item:
        visit(history_item.get("outputs") or {})
    return found


def _find_new_video(started_at: float, history_item: dict[str, Any] | None = None, timeout: int = 30) -> Path:
    video_suffixes = {".mp4", ".webm", ".mov", ".mkv"}
    deadline = time.time() + timeout
    history_paths = _history_video_paths(history_item)

    while time.time() < deadline:
        for path in history_paths:
            if path.is_file() and path.stat().st_size > 0:
                return path

        candidates = [
            path
            for path in OUTPUT_DIR.rglob("*")
            if path.is_file()
            and path.suffix.lower() in video_suffixes
            and path.stat().st_mtime >= started_at - 2
        ]
        if candidates:
            return max(candidates, key=lambda path: path.stat().st_mtime)
        time.sleep(0.5)

    summary = [
        (str(path), path.stat().st_size, path.stat().st_mtime)
        for path in OUTPUT_DIR.rglob("*")
        if path.is_file()
    ][-20:]
    raise RuntimeError(
        f"ComfyUI completed but no video output was found; history_paths={[str(path) for path in history_paths]}; files={summary}"
    )


def _finalize_video(
    video_path: Path,
    *,
    width: int,
    height: int,
    frame_rate: int,
    duration_seconds: int,
) -> Path:
    final_path = video_path.with_name(f"{video_path.stem}-delivery.mp4")
    target_frames = int(duration_seconds) * int(frame_rate)
    video_filter = (
        f"scale={int(width)}:{int(height)}:force_original_aspect_ratio=increase,"
        f"crop={int(width)}:{int(height)},setsar=1"
    )
    audio_filter = f"atrim=duration={float(duration_seconds):.3f},asetpts=PTS-STARTPTS"
    command = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(video_path),
        "-map", "0:v:0", "-map", "0:a?",
        "-vf", video_filter,
        "-af", audio_filter,
        "-frames:v", str(target_frames),
        "-r", str(int(frame_rate)),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(final_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0 or not final_path.is_file() or final_path.stat().st_size <= 0:
        raise RuntimeError(f"ffmpeg delivery encode failed: {result.stderr[-3000:]}")
    return final_path


@app.function(
    image=image,
    timeout=7200,
    volumes={str(CACHE_DIR): cache_volume},
    secrets=RUNTIME_SECRETS,
)
def prefetch_ltx25(verify_checkpoint: bool = True) -> dict[str, Any]:
    started = time.perf_counter()
    files = _ensure_model_files(verify_checkpoint=verify_checkpoint)
    _set_worker_state("sleeping", assets_cached=True)
    return {
        "ready": True,
        "model": "redgraft-ltx25-sulphur2-int8-convrot",
        "checkpoint": CHECKPOINT,
        "checkpoint_autov2": CHECKPOINT_AUTOV2,
        "files": {key: str(value) for key, value in files.items()},
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }


@app.cls(
    image=image,
    gpu=GPU_REQUEST,
    timeout=4200,
    scaledown_window=CONTAINER_IDLE_SECONDS,
    min_containers=WORKER_MIN_CONTAINERS,
    max_containers=WORKER_MAX_CONTAINERS,
    volumes={str(CACHE_DIR): cache_volume},
    secrets=RUNTIME_SECRETS,
)
@modal.concurrent(max_inputs=1)
class LTX25Worker:
    @modal.enter()
    def start(self) -> None:
        _set_worker_state("loading")
        started = time.perf_counter()
        files = _ensure_model_files(verify_checkpoint=True)
        self.models = _prepare_models(files)
        INPUT_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        launch_command = [
            "python", "main.py", "--listen", "127.0.0.1", "--port", "8188",
            "--reserve-vram", "2", "--disable-auto-launch", "--preview-method", "none",
        ]
        if any(choice.upper() == "A10" for choice in GPU_CHOICES):
            launch_command.append("--lowvram")
        self.process = subprocess.Popen(launch_command, cwd=COMFY_DIR)
        _wait_server()
        self.started_seconds = round(time.perf_counter() - started, 3)
        _set_worker_state("ready", startup_seconds=self.started_seconds)

    @modal.method()
    def health(self) -> dict[str, Any]:
        return {
            "ready": True,
            "app": APP_NAME,
            "gpu": GPU_LABEL,
            "default_fps": DEFAULT_FPS,
            "frame_rates": sorted(FRAME_RATES),
            "model": "REDGraft LTX 2.5 · Sulphur2 INT8 ConvRot",
            "checkpoint": CHECKPOINT,
            "checkpoint_autov2": CHECKPOINT_AUTOV2,
            "resolutions": RESOLUTIONS,
            "enabled_resolutions": sorted(ENABLED_RESOLUTIONS),
            "models": self.models,
            "startup_seconds": self.started_seconds,
            "recipe": {
                "low_stage_sigmas": LOW_STAGE_SIGMAS,
                "high_stage_sigmas": HIGH_STAGE_SIGMAS,
                "cfg": 1.0,
                "sampler": "euler",
                "two_stage_latent_upscale": True,
            },
        }

    @modal.method()
    def object_info(self) -> dict[str, Any]:
        info = _request_json("/object_info", timeout=120)
        wanted = {
            "UNETLoader",
            "CLIPLoader",
            "VAELoader",
            "LatentUpscaleModelLoader",
            "ConditioningZeroOut",
            "LTXVEmptyLatentAudio",
            "LTXVConcatAVLatent",
            "LTXVSeparateAVLatent",
            "LTXVConditioning",
            "LTXVCropGuides",
            "LTXVLatentUpsampler",
            "LTXVImgToVideoInplace",
            "LTXVPreprocess",
            "LatentUpscaleBy",
            "ImageScale",
            "CreateVideo",
            "SaveVideo",
        }
        return {name: info.get(name) for name in sorted(wanted)}

    def _generate_impl(
        self,
        prompt: str,
        negative_prompt: str = "",
        seed: int = 42,
        resolution: str = "480p",
        duration_seconds: int = 5,
        audio_enabled: bool = True,
        aspect_ratio: str = "16:9",
        frame_rate: int = DEFAULT_FPS,
        source_image: bytes | None = None,
    ) -> bytes:
        del negative_prompt  # REDGraft reference recipe uses zeroed negative conditioning.
        prompt = (prompt or "").strip()
        if not prompt:
            raise ValueError("prompt is required")
        if resolution not in RESOLUTIONS:
            raise ValueError(f"unsupported resolution: {resolution}")
        if resolution not in ENABLED_RESOLUTIONS:
            raise ValueError(f"{resolution} is not enabled for the REDGraft LTX 2.5 runtime")
        if not 5 <= int(duration_seconds) <= 30:
            raise ValueError("duration_seconds must be between 5 and 30")
        _parse_aspect_ratio(aspect_ratio)
        if int(frame_rate) not in FRAME_RATES:
            raise ValueError("frame_rate must be 24, 25, or 30")

        _set_worker_state("generating")
        source_name = _upload_image(source_image) if source_image else None
        output_token = uuid.uuid4().hex[:12]
        graph = _workflow(
            prompt=prompt,
            seed=int(seed),
            resolution=resolution,
            duration_seconds=int(duration_seconds),
            audio_enabled=bool(audio_enabled),
            aspect_ratio=str(aspect_ratio),
            frame_rate=int(frame_rate),
            source_name=source_name,
            output_token=output_token,
        )
        started_at = time.time()
        client_id = str(uuid.uuid4())
        queued = _request_json("/prompt", {"prompt": graph, "client_id": client_id}, timeout=120)
        prompt_id = queued.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI rejected REDGraft LTX 2.5 workflow: {queued}")

        deadline = time.time() + 3900
        while time.time() < deadline:
            history = _request_json(f"/history/{prompt_id}", timeout=45)
            item = history.get(prompt_id)
            if item:
                status = item.get("status") or {}
                messages = status.get("messages") or []
                if status.get("status_str") == "error" or any(
                    message and message[0] == "execution_error" for message in messages
                ):
                    raise RuntimeError(
                        f"ComfyUI REDGraft LTX 2.5 execution failed: {json.dumps(status)[:7000]}"
                    )
                if status.get("completed") is True:
                    video_path = _find_new_video(started_at, item)
                    delivery_width, delivery_height = _delivery_dimensions(resolution, aspect_ratio)
                    final_path = _finalize_video(
                        video_path,
                        width=delivery_width,
                        height=delivery_height,
                        frame_rate=int(frame_rate),
                        duration_seconds=int(duration_seconds),
                    )
                    _set_worker_state("finalizing")
                    _log(
                        "ltx25_delivery_ready",
                        resolution=resolution,
                        aspect_ratio=aspect_ratio,
                        frame_rate=int(frame_rate),
                        duration_seconds=int(duration_seconds),
                        width=delivery_width,
                        height=delivery_height,
                        bytes=final_path.stat().st_size,
                    )
                    result = final_path.read_bytes()
                    _set_worker_state("ready")
                    return result
            time.sleep(2)
        _set_worker_state("failed")
        raise TimeoutError("REDGraft LTX 2.5 generation timed out")


    @modal.method()
    def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        seed: int = 42,
        resolution: str = "480p",
        duration_seconds: int = 5,
        audio_enabled: bool = True,
        aspect_ratio: str = "16:9",
        frame_rate: int = DEFAULT_FPS,
        source_image: bytes | None = None,
    ) -> bytes:
        try:
            return self._generate_impl(
                prompt=prompt,
                negative_prompt=negative_prompt,
                seed=seed,
                resolution=resolution,
                duration_seconds=duration_seconds,
                audio_enabled=audio_enabled,
                aspect_ratio=aspect_ratio,
                frame_rate=frame_rate,
                source_image=source_image,
            )
        except Exception:
            _set_worker_state("failed")
            raise

    @modal.exit()
    def stop(self) -> None:
        _set_worker_state("sleeping")
