import os
from pathlib import Path

app = Path('integrations/comfyui/ltx23_app.py')
text = app.read_text(encoding='utf-8')


def once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'app: expected one match, found {count}: {old[:120]!r}')
    text = text.replace(old, new, 1)


# Paid GPU tiers are unavailable on the current credit workspaces. Keep A10 as
# the deployable default, but let ComfyUI use normal smart-memory management.
once(
    'GPU_CHOICES = [x.strip() for x in os.environ.get("MODAL_LTX25_GPU", "H100,L40S,A100-40GB").split(",") if x.strip()]\n',
    'GPU_CHOICES = [x.strip() for x in os.environ.get("MODAL_LTX25_GPU", "A10").split(",") if x.strip()]\n',
)
once(
    '            "--reserve-vram", "2", "--disable-auto-launch", "--preview-method", "none",\n',
    '            "--reserve-vram", "0.5", "--disable-auto-launch", "--preview-method", "none",\n',
)
once(
    '        if any(choice.upper() == "A10" for choice in GPU_CHOICES):\n            launch_command.append("--lowvram")\n',
    '        if str(os.environ.get("MODAL_LTX25_LOWVRAM") or "").strip().lower() in {"1", "true", "yes"}:\n            launch_command.append("--lowvram")\n',
)
once(
    '        _wait_server()\n        self.started_seconds = round(time.perf_counter() - started, 3)\n        _set_worker_state("ready", startup_seconds=self.started_seconds)\n',
    '''        _wait_server()\n        self.started_seconds = round(time.perf_counter() - started, 3)\n        try:\n            import torch\n            self.gpu_name = torch.cuda.get_device_name(0)\n        except Exception:\n            self.gpu_name = GPU_LABEL\n        _set_worker_state("ready", startup_seconds=self.started_seconds, gpu_name=self.gpu_name)\n''',
)
once(
    '            "gpu": GPU_LABEL,\n',
    '            "gpu": GPU_LABEL,\n            "gpu_name": getattr(self, "gpu_name", GPU_LABEL),\n',
)
once(
    '        _set_worker_state("generating")\n',
    '        generation_started = time.perf_counter()\n        _set_worker_state("generating", gpu_name=getattr(self, "gpu_name", GPU_LABEL))\n',
)
once(
    '''                    video_path = _find_new_video(started_at, item)\n                    delivery_width, delivery_height = _delivery_dimensions(resolution, aspect_ratio)\n                    final_path = _finalize_video(\n                        video_path,\n                        width=delivery_width,\n                        height=delivery_height,\n                        frame_rate=int(frame_rate),\n                        duration_seconds=int(duration_seconds),\n                    )\n                    _set_worker_state("finalizing")\n''',
    '''                    video_path = _find_new_video(started_at, item)\n                    delivery_width, delivery_height = _delivery_dimensions(resolution, aspect_ratio)\n                    compute_seconds = round(time.perf_counter() - generation_started, 3)\n                    finalize_started = time.perf_counter()\n                    _set_worker_state(\n                        "finalizing",\n                        gpu_name=getattr(self, "gpu_name", GPU_LABEL),\n                        compute_seconds=compute_seconds,\n                    )\n                    final_path = _finalize_video(\n                        video_path,\n                        width=delivery_width,\n                        height=delivery_height,\n                        frame_rate=int(frame_rate),\n                        duration_seconds=int(duration_seconds),\n                    )\n''',
)
once(
    '                    _set_worker_state("ready")\n                    return {"video": result, "poster": bytes(poster_process.stdout)}\n',
    '''                    finalize_seconds = round(time.perf_counter() - finalize_started, 3)\n                    total_seconds = round(time.perf_counter() - generation_started, 3)\n                    _set_worker_state(\n                        "ready",\n                        gpu_name=getattr(self, "gpu_name", GPU_LABEL),\n                        compute_seconds=compute_seconds,\n                        finalize_seconds=finalize_seconds,\n                        total_seconds=total_seconds,\n                    )\n                    return {"video": result, "poster": bytes(poster_process.stdout)}\n''',
)
app.write_text(text, encoding='utf-8')

gateway = Path('integrations/comfyui/ltx23_gateway.py')
text = gateway.read_text(encoding='utf-8')


def gone(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'gateway: expected one match, found {count}: {old[:120]!r}')
    text = text.replace(old, new, 1)


gone(
    '    api = FastAPI(title="SAGA REDGraft LTX 2.5 Video Gateway", version="0.4.0")\n',
    '    api = FastAPI(title="SAGA REDGraft LTX 2.5 Video Gateway", version="0.5.0")\n',
)
gone(
    '''    def _extract_poster(video: bytes) -> bytes:\n        import subprocess\n\n        command = [\n            "ffmpeg", "-hide_banner", "-loglevel", "error",\n            "-ss", "0.08",\n            "-i", "pipe:0",\n            "-frames:v", "1",\n            "-f", "image2pipe",\n            "-vcodec", "mjpeg",\n            "-q:v", "3",\n            "pipe:1",\n        ]\n        result = subprocess.run(command, input=video, capture_output=True, check=False)\n        if result.returncode != 0 or not result.stdout:\n            detail = result.stderr.decode("utf-8", errors="replace")[-3000:]\n            raise RuntimeError(f"ffmpeg poster extraction failed: {detail}")\n        return bytes(result.stdout)\n''',
    '''    def _extract_poster(video: bytes) -> bytes:\n        import subprocess\n        import tempfile\n\n        # MP4 seek metadata can live at the end of the file. Use a seekable\n        # temporary file rather than stdin so fallback extraction is reliable.\n        with tempfile.NamedTemporaryFile(suffix=".mp4") as source:\n            source.write(video)\n            source.flush()\n            command = [\n                "ffmpeg", "-hide_banner", "-loglevel", "error",\n                "-ss", "0.08",\n                "-i", source.name,\n                "-frames:v", "1",\n                "-f", "image2pipe",\n                "-vcodec", "mjpeg",\n                "-q:v", "3",\n                "pipe:1",\n            ]\n            result = subprocess.run(command, capture_output=True, check=False)\n        if result.returncode != 0 or not result.stdout:\n            detail = result.stderr.decode("utf-8", errors="replace")[-3000:]\n            raise RuntimeError(f"ffmpeg poster extraction failed: {detail}")\n        return bytes(result.stdout)\n''',
)
gateway.write_text(text, encoding='utf-8')

github_env = os.environ.get('GITHUB_ENV')
if github_env:
    with open(github_env, 'a', encoding='utf-8') as handle:
        handle.write('MODAL_LTX25_GPU=A10\n')
        handle.write('MODAL_LTX25_LOWVRAM=0\n')
