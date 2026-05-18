from __future__ import annotations

import copy
import json
import os
import subprocess
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

import modal


APP_NAME = os.environ.get("MODAL_COMFYUI_APP_NAME", "graduation-comfyui")
COMFYUI_VERSION = "0.19.3"
MODAL_VERSION = "1.4.2"
PYTHON_VERSION = "3.11"
COMFY_DIR = "/root/comfyui"
COMFY_PORT = 8188
CACHE_DIR = "/cache"
DEFAULT_WORKFLOW_PATH = "/root/workflow_api.json"
DEFAULT_CHECKPOINT = "v1-5-pruned-emaonly.safetensors"
CHECKPOINT_REPO = "stable-diffusion-v1-5/stable-diffusion-v1-5"
GPU_TYPE = os.environ.get("MODAL_COMFYUI_GPU", "L4")
CONTAINER_IDLE_SECONDS = int(os.environ.get("MODAL_COMFYUI_IDLE_SECONDS", "60"))
FUNCTION_TIMEOUT_SECONDS = int(os.environ.get("MODAL_COMFYUI_TIMEOUT_SECONDS", "1200"))
LOCAL_WORKFLOW = Path(__file__).with_name("workflow_api.json")


def download_default_checkpoint() -> None:
    from huggingface_hub import hf_hub_download

    checkpoint = hf_hub_download(
        repo_id=CHECKPOINT_REPO,
        filename=DEFAULT_CHECKPOINT,
        cache_dir=CACHE_DIR,
    )
    target_dir = Path(COMFY_DIR) / "models" / "checkpoints"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / DEFAULT_CHECKPOINT
    if target_path.exists() or target_path.is_symlink():
        target_path.unlink()
    target_path.symlink_to(Path(checkpoint))


cache_volume = modal.Volume.from_name("graduation-comfyui-cache", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version=PYTHON_VERSION)
    .apt_install("git", "ffmpeg", "libgl1", "libglib2.0-0", "libsm6", "libxrender1", "libxext6")
    .pip_install(
        f"modal=={MODAL_VERSION}",
        "aiohttp>=3.11.8",
        "fastapi[standard]==0.121.0",
        "huggingface_hub[hf_transfer]==0.36.0",
        "websocket-client==1.9.0",
    )
    .env(
        {
            "HF_HUB_ENABLE_HF_TRANSFER": "1",
            "HF_HUB_CACHE": CACHE_DIR,
            "PIP_PREFER_BINARY": "1",
            "COMFYUI_DISABLE_TELEMETRY": "1",
        }
    )
    .run_commands(
        f"git clone --depth 1 --branch v{COMFYUI_VERSION} https://github.com/Comfy-Org/ComfyUI.git {COMFY_DIR}",
        f"cd {COMFY_DIR} && pip install -r requirements.txt",
    )
    .run_function(download_default_checkpoint, volumes={CACHE_DIR: cache_volume})
    .add_local_file(LOCAL_WORKFLOW, DEFAULT_WORKFLOW_PATH)
)

app = modal.App(name=APP_NAME, image=image)


def _request_json(url: str, data: bytes | None = None) -> Any:
    request = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def _request_bytes(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


@app.cls(
    image=image,
    gpu=GPU_TYPE,
    timeout=FUNCTION_TIMEOUT_SECONDS,
    scaledown_window=CONTAINER_IDLE_SECONDS,
    volumes={CACHE_DIR: cache_volume},
)
@modal.concurrent(max_inputs=1)
class ComfyService:
    port: int = COMFY_PORT

    @modal.enter()
    def launch_comfy_background(self) -> None:
        self._process = subprocess.Popen(
            [
                "python",
                "main.py",
                "--listen",
                "0.0.0.0",
                "--port",
                str(self.port),
                "--disable-auto-launch",
            ],
            cwd=COMFY_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._wait_until_ready()

    def _wait_until_ready(self) -> None:
        url = f"http://127.0.0.1:{self.port}/system_stats"
        deadline = time.time() + 180
        last_error: Exception | None = None
        while time.time() < deadline:
            try:
                _request_json(url)
                return
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                time.sleep(2)
        raise RuntimeError(f"ComfyUI server did not become ready: {last_error}")

    def _load_workflow(self, workflow_path: str = DEFAULT_WORKFLOW_PATH) -> dict[str, Any]:
        return json.loads(Path(workflow_path).read_text(encoding="utf-8"))

    def _apply_prompt_inputs(
        self,
        workflow: dict[str, Any],
        prompt: str,
        negative_prompt: str,
        seed: int,
        steps: int,
        cfg: float,
        width: int,
        height: int,
        filename_prefix: str,
    ) -> dict[str, Any]:
        workflow = copy.deepcopy(workflow)
        workflow["6"]["inputs"]["text"] = prompt
        workflow["7"]["inputs"]["text"] = negative_prompt
        workflow["3"]["inputs"]["seed"] = seed
        workflow["3"]["inputs"]["steps"] = steps
        workflow["3"]["inputs"]["cfg"] = cfg
        workflow["5"]["inputs"]["width"] = width
        workflow["5"]["inputs"]["height"] = height
        workflow["9"]["inputs"]["filename_prefix"] = filename_prefix
        return workflow

    def _queue_prompt(self, workflow: dict[str, Any], prompt_id: str) -> None:
        payload = {"prompt": workflow, "prompt_id": prompt_id, "client_id": prompt_id}
        _request_json(
            f"http://127.0.0.1:{self.port}/prompt",
            data=json.dumps(payload).encode("utf-8"),
        )

    def _poll_history(self, prompt_id: str, timeout_seconds: int = 900) -> dict[str, Any]:
        url = f"http://127.0.0.1:{self.port}/history/{prompt_id}"
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            history = _request_json(url)
            item = history.get(prompt_id)
            if item and item.get("outputs"):
                return item
            time.sleep(2)
        raise TimeoutError(f"Timed out waiting for prompt {prompt_id} to finish.")

    def _fetch_first_image(self, history: dict[str, Any]) -> bytes:
        outputs = history.get("outputs", {})
        for node_output in outputs.values():
            for image in node_output.get("images", []):
                query = urllib.parse.urlencode(
                    {
                        "filename": image["filename"],
                        "subfolder": image["subfolder"],
                        "type": image["type"],
                    }
                )
                return _request_bytes(f"http://127.0.0.1:{self.port}/view?{query}")
        raise RuntimeError("Workflow completed but no image was produced.")

    @modal.method()
    def render(
        self,
        prompt: str,
        negative_prompt: str = "blurry, low quality, distorted hands, artifacts",
        seed: int = 5,
        steps: int = 20,
        cfg: float = 8.0,
        width: int = 512,
        height: int = 512,
        workflow_path: str = DEFAULT_WORKFLOW_PATH,
    ) -> bytes:
        self._wait_until_ready()
        workflow = self._load_workflow(workflow_path)
        prompt_id = str(uuid.uuid4())
        workflow = self._apply_prompt_inputs(
            workflow=workflow,
            prompt=prompt,
            negative_prompt=negative_prompt,
            seed=seed,
            steps=steps,
            cfg=cfg,
            width=width,
            height=height,
            filename_prefix=f"modal-comfyui-{prompt_id[:8]}",
        )
        self._queue_prompt(workflow, prompt_id)
        history = self._poll_history(prompt_id)
        return self._fetch_first_image(history)

    @modal.fastapi_endpoint(method="GET", docs=True)
    def api(
        self,
        prompt: str,
        negative_prompt: str = "blurry, low quality, distorted hands, artifacts",
        seed: int = 5,
        steps: int = 20,
        cfg: float = 8.0,
        width: int = 512,
        height: int = 512,
    ):
        from fastapi import Response

        image_bytes = self.render.local(
            prompt=prompt,
            negative_prompt=negative_prompt,
            seed=seed,
            steps=steps,
            cfg=cfg,
            width=width,
            height=height,
        )
        return Response(content=image_bytes, media_type="image/png")


@app.function(
    image=image,
    gpu=GPU_TYPE,
    max_containers=1,
    scaledown_window=CONTAINER_IDLE_SECONDS,
    timeout=FUNCTION_TIMEOUT_SECONDS,
    volumes={CACHE_DIR: cache_volume},
)
@modal.concurrent(max_inputs=3)
@modal.web_server(COMFY_PORT, startup_timeout=180)
def ui() -> None:
    subprocess.Popen(
        [
            "python",
            "main.py",
            "--listen",
            "0.0.0.0",
            "--port",
            str(COMFY_PORT),
            "--disable-auto-launch",
        ],
        cwd=COMFY_DIR,
    )


@app.local_entrypoint()
def entrypoint(
    prompt: str,
    output_path: str = "modal_comfyui/outputs/render.png",
    negative_prompt: str = "blurry, low quality, distorted hands, artifacts",
    seed: int = 5,
    steps: int = 20,
    cfg: float = 8.0,
    width: int = 512,
    height: int = 512,
) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    image_bytes = ComfyService().render.remote(
        prompt=prompt,
        negative_prompt=negative_prompt,
        seed=seed,
        steps=steps,
        cfg=cfg,
        width=width,
        height=height,
    )
    output.write_bytes(image_bytes)
    print(output.resolve())
