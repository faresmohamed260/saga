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


APP_NAME = os.environ.get("MODAL_COMFYUI_APP_NAME", "graduation-comfyui")
MODAL_VERSION = "1.4.2"
PYTHON_VERSION = "3.11"
COMFY_DIR = "/root/comfyui"
COMFY_PORT = 8188
CACHE_DIR = "/cache"
DEFAULT_WORKFLOW_PATH = "/root/workflow_api.json"
CHARACTER_SHEET_WORKFLOW_PATH = "/root/character_sheet_workflow.json"
CHARACTER_SHEET_POSE_PATH = "/root/pose-sheet.png"
GPU_TYPE = os.environ.get("MODAL_COMFYUI_GPU", "L40S")
CONTAINER_IDLE_SECONDS = int(os.environ.get("MODAL_COMFYUI_IDLE_SECONDS", "60"))
FUNCTION_TIMEOUT_SECONDS = int(os.environ.get("MODAL_COMFYUI_TIMEOUT_SECONDS", "1800"))

LOCAL_WORKFLOW = Path(__file__).with_name("workflow_api.json")
LOCAL_CHARACTER_SHEET_WORKFLOW = Path(__file__).parent / "workflows" / "character_sheet_workflow.json"
LOCAL_CHARACTER_SHEET_POSE = Path(__file__).parent / "assets" / "pose-sheet.png"

MODEL_SPECS = (
    {
        "repo_id": "Comfy-Org/z_image_turbo",
        "filename": "split_files/text_encoders/qwen_3_4b.safetensors",
        "target_subdir": "models/text_encoders",
        "target_name": "qwen_3_4b.safetensors",
    },
    {
        "repo_id": "Comfy-Org/z_image_turbo",
        "filename": "split_files/diffusion_models/z_image_turbo_bf16.safetensors",
        "target_subdir": "models/diffusion_models",
        "target_name": "z_image_turbo_bf16.safetensors",
    },
    {
        "repo_id": "Comfy-Org/z_image_turbo",
        "filename": "split_files/vae/ae.safetensors",
        "target_subdir": "models/vae",
        "target_name": "ae.safetensors",
    },
    {
        "repo_id": "alibaba-pai/Z-Image-Turbo-Fun-Controlnet-Union",
        "filename": "Z-Image-Turbo-Fun-Controlnet-Union.safetensors",
        "target_subdir": "models/model_patches",
        "target_name": "Z-Image-Turbo-Fun-Controlnet-Union.safetensors",
    },
)


def _link_model(downloaded_path: str, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists() or target_path.is_symlink():
        target_path.unlink()
    target_path.symlink_to(Path(downloaded_path))


def download_character_sheet_models() -> None:
    from huggingface_hub import hf_hub_download

    for spec in MODEL_SPECS:
        local_path = hf_hub_download(
            repo_id=spec["repo_id"],
            filename=spec["filename"],
            cache_dir=CACHE_DIR,
        )
        target = Path(COMFY_DIR) / spec["target_subdir"] / spec["target_name"]
        _link_model(local_path, target)


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
        f"git clone --depth 1 https://github.com/Comfy-Org/ComfyUI.git {COMFY_DIR}",
        f"cd {COMFY_DIR} && pip install -r requirements.txt",
    )
    .run_function(download_character_sheet_models, volumes={CACHE_DIR: cache_volume})
    .add_local_file(LOCAL_WORKFLOW, DEFAULT_WORKFLOW_PATH)
    .add_local_file(LOCAL_CHARACTER_SHEET_WORKFLOW, CHARACTER_SHEET_WORKFLOW_PATH)
    .add_local_file(LOCAL_CHARACTER_SHEET_POSE, CHARACTER_SHEET_POSE_PATH)
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
        deadline = time.time() + 240
        last_error: Exception | None = None
        while time.time() < deadline:
            try:
                _request_json(url)
                return
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                time.sleep(2)
        raise RuntimeError(f"ComfyUI server did not become ready: {last_error}")

    def _load_workflow(self, workflow_path: str) -> dict[str, Any]:
        return json.loads(Path(workflow_path).read_text(encoding="utf-8"))

    def _stage_input_image(self, source_path: str, target_name: str = "image1.png") -> None:
        target = Path(COMFY_DIR) / "input" / target_name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target)

    def _apply_default_inputs(
        self,
        workflow: dict[str, Any],
        *,
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

    def _apply_character_sheet_inputs(
        self,
        workflow: dict[str, Any],
        *,
        prompt: str,
        negative_prompt: str,
        seed: int,
        steps: int,
        cfg: float,
        width: int,
        height: int,
        filename_prefix: str,
        pose_image_name: str,
    ) -> dict[str, Any]:
        workflow = copy.deepcopy(workflow)
        workflow["6"]["inputs"]["text"] = prompt
        workflow["5"]["inputs"]["text"] = negative_prompt
        workflow["3"]["inputs"]["seed"] = seed
        workflow["3"]["inputs"]["steps"] = steps
        workflow["3"]["inputs"]["cfg"] = cfg
        workflow["15"]["inputs"]["width"] = width
        workflow["15"]["inputs"]["height"] = height
        workflow["16"]["inputs"]["filename_prefix"] = filename_prefix
        workflow["7"]["inputs"]["image"] = pose_image_name
        return workflow

    def _queue_prompt(self, workflow: dict[str, Any], prompt_id: str) -> None:
        payload = {"prompt": workflow, "prompt_id": prompt_id, "client_id": prompt_id}
        _request_json(
            f"http://127.0.0.1:{self.port}/prompt",
            data=json.dumps(payload).encode("utf-8"),
        )

    def _poll_history(self, prompt_id: str, timeout_seconds: int = 1200) -> dict[str, Any]:
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
        workflow_mode: str = "default",
        workflow_path: str = "",
        filename_prefix: str = "",
        pose_image_path: str = CHARACTER_SHEET_POSE_PATH,
    ) -> bytes:
        self._wait_until_ready()
        mode = str(workflow_mode or "default").strip().lower()
        resolved_workflow = workflow_path or (CHARACTER_SHEET_WORKFLOW_PATH if mode == "character_sheet" else DEFAULT_WORKFLOW_PATH)
        workflow = self._load_workflow(resolved_workflow)
        prompt_id = str(uuid.uuid4())
        resolved_prefix = filename_prefix or f"modal-comfyui-{prompt_id[:8]}"
        if mode == "character_sheet":
            self._stage_input_image(pose_image_path, "image1.png")
            workflow = self._apply_character_sheet_inputs(
                workflow=workflow,
                prompt=prompt,
                negative_prompt=negative_prompt,
                seed=seed,
                steps=steps,
                cfg=cfg,
                width=width,
                height=height,
                filename_prefix=resolved_prefix,
                pose_image_name="image1.png",
            )
        else:
            workflow = self._apply_default_inputs(
                workflow=workflow,
                prompt=prompt,
                negative_prompt=negative_prompt,
                seed=seed,
                steps=steps,
                cfg=cfg,
                width=width,
                height=height,
                filename_prefix=resolved_prefix,
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
        workflow_mode: str = "default",
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
            workflow_mode=workflow_mode,
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
@modal.web_server(COMFY_PORT, startup_timeout=240)
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
    prompt: str = "",
    output_path: str = "modal_comfyui/outputs/render.png",
    output_dir: str = "",
    manifest_path: str = "",
    report_path: str = "",
    negative_prompt: str = "blurry, low quality, distorted hands, artifacts",
    seed: int = 5,
    steps: int = 20,
    cfg: float = 8.0,
    width: int = 512,
    height: int = 512,
    workflow_mode: str = "default",
    filename_prefix: str = "",
    pose_image_path: str = CHARACTER_SHEET_POSE_PATH,
) -> None:
    service = ComfyService()
    if manifest_path:
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8-sig"))
        output_root = Path(output_dir or manifest.get("images_dir") or "modal_comfyui/outputs")
        output_root.mkdir(parents=True, exist_ok=True)
        report_rows: list[dict[str, Any]] = []
        total = len(manifest.get("renders") or [])
        for index, item in enumerate(manifest.get("renders") or [], start=1):
            entity_name = str(item.get("entity_name") or item.get("output_filename") or f"render_{index}").strip()
            if not item.get("should_render", True) and Path(item.get("output_path") or "").exists():
                print(f"RENDER_PROGRESS|{index}|{total}|{entity_name}|skipped_existing", flush=True)
                report_rows.append(
                    {
                        **item,
                        "status": "skipped_existing",
                    }
                )
                continue
            target_name = item.get("output_filename") or f"render_{index:02d}.png"
            target_path = output_root / target_name
            item_workflow_mode = str(item.get("workflow_mode") or workflow_mode or manifest.get("workflow_mode") or "character_sheet").strip().lower()
            print(f"RENDER_PROGRESS|{index}|{total}|{entity_name}|starting", flush=True)
            image_bytes = service.render.remote(
                prompt=item.get("positive_prompt") or prompt,
                negative_prompt=item.get("negative_prompt") or negative_prompt,
                seed=int(item.get("seed") or seed),
                steps=int(item.get("steps") or manifest.get("steps") or steps),
                cfg=float(item.get("cfg") or manifest.get("cfg") or cfg),
                width=int(item.get("width") or manifest.get("width") or width),
                height=int(item.get("height") or manifest.get("height") or height),
                workflow_mode=item_workflow_mode,
                filename_prefix=item.get("filename_prefix") or Path(target_name).stem or filename_prefix,
                pose_image_path=pose_image_path,
            )
            target_path.write_bytes(image_bytes)
            print(f"RENDER_PROGRESS|{index}|{total}|{entity_name}|rendered", flush=True)
            report_rows.append(
                {
                    **item,
                    "status": "rendered",
                    "output_path": str(target_path),
                }
            )
        if report_path:
            report_target = Path(report_path)
            report_target.parent.mkdir(parents=True, exist_ok=True)
            report_target.write_text(json.dumps({"renders": report_rows}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(output_root.resolve())
        return

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    image_bytes = service.render.remote(
        prompt=prompt,
        negative_prompt=negative_prompt,
        seed=seed,
        steps=steps,
        cfg=cfg,
        width=width,
        height=height,
        workflow_mode=workflow_mode,
        filename_prefix=filename_prefix,
        pose_image_path=pose_image_path,
    )
    output.write_bytes(image_bytes)
    print(output.resolve())
