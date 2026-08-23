import os
import re

import modal

APP_NAME = "saga-ltx25-gateway"
RUNTIME_APP_NAME = "saga-ltx25-video"
RUNTIME_CLASS_NAME = "LTX25Worker"
MODAL_VERSION = "1.4.2"

image = modal.Image.debian_slim(python_version="3.11").pip_install(
    f"modal=={MODAL_VERSION}",
    "fastapi[standard]==0.121.0",
    "python-multipart>=0.0.20,<1",
)
app = modal.App(APP_NAME, image=image)


@app.function(image=image, timeout=4200)
@modal.asgi_app()
def web():
    from fastapi import FastAPI, File, Form, HTTPException, UploadFile
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, Response

    api = FastAPI(title="SAGA REDGraft LTX 2.5 Video Gateway", version="0.3.0")
    origins = [
        origin.strip()
        for origin in os.environ.get(
            "SAGA_STUDIO_ALLOWED_ORIGINS",
            "https://studio.faresuniform.uk,http://localhost:5173",
        ).split(",")
        if origin.strip()
    ]
    api.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    def _worker():
        return modal.Cls.from_name(RUNTIME_APP_NAME, RUNTIME_CLASS_NAME)()

    @api.get("/health")
    async def health():
        try:
            runtime = _worker().health.remote()
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"LTX 2.5 runtime health failed: {type(exc).__name__}: {exc}") from exc
        return {
            "ready": bool(runtime.get("ready")),
            "gateway": APP_NAME,
            "runtime_app": RUNTIME_APP_NAME,
            "runtime_class": RUNTIME_CLASS_NAME,
            "async_jobs": True,
            "cancel_jobs": True,
            "runtime": runtime,
        }

    @api.post("/jobs/video")
    async def submit_video(
        prompt: str = Form(...),
        negative_prompt: str = Form(""),
        seed: int = Form(42),
        resolution: str = Form("480p"),
        duration_seconds: int = Form(5),
        audio_enabled: bool = Form(True),
        aspect_ratio: str = Form("16:9"),
        frame_rate: int = Form(24),
        image_file: UploadFile | None = File(None),
    ):
        prompt = prompt.strip()
        if not prompt:
            raise HTTPException(status_code=400, detail="prompt is required")
        if resolution not in {"480p", "720p", "1080p", "2K", "4K"}:
            raise HTTPException(status_code=400, detail="unsupported video resolution")
        if not 5 <= int(duration_seconds) <= 30:
            raise HTTPException(status_code=400, detail="duration_seconds must be between 5 and 30")
        ratio_match = re.fullmatch(r"(\d+(?:\.\d+)?):(\d+(?:\.\d+)?)", str(aspect_ratio).strip())
        if not ratio_match:
            raise HTTPException(status_code=400, detail="aspect_ratio must be W:H")
        ratio_value = float(ratio_match.group(1)) / float(ratio_match.group(2))
        if not 0.4 <= ratio_value <= 2.5:
            raise HTTPException(status_code=400, detail="aspect_ratio is outside the supported range")
        if int(frame_rate) not in {24, 25, 30}:
            raise HTTPException(status_code=400, detail="frame_rate must be 24, 25, or 30")

        image_bytes = None
        if image_file is not None:
            if not image_file.content_type or not image_file.content_type.startswith("image/"):
                raise HTTPException(status_code=415, detail="image_file must be an image")
            image_bytes = await image_file.read()
            if not image_bytes:
                raise HTTPException(status_code=400, detail="image_file is empty")
            if len(image_bytes) > 25 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="image_file must be 25 MB or smaller")

        normalized_aspect = str(aspect_ratio).strip()
        normalized_frame_rate = int(frame_rate)
        try:
            call = _worker().generate.spawn(
                prompt=prompt,
                negative_prompt=negative_prompt,
                seed=int(seed),
                resolution=resolution,
                duration_seconds=int(duration_seconds),
                audio_enabled=bool(audio_enabled),
                aspect_ratio=normalized_aspect,
                frame_rate=normalized_frame_rate,
                source_image=image_bytes,
            )
            return {
                "status": "queued",
                "call_id": call.object_id,
                "kind": "video",
                "mode": "image-to-video" if image_bytes else "text-to-video",
                "model": "REDGraft LTX 2.5 · Sulphur2 INT8 ConvRot",
                "resolution": resolution,
                "aspect_ratio": normalized_aspect,
                "frame_rate": normalized_frame_rate,
            }
        except Exception as exc:  # noqa: BLE001
            print({"event": "ltx25_gateway_spawn_failed", "error": repr(exc)}, flush=True)
            raise HTTPException(status_code=502, detail=f"LTX 2.5 runtime submit failed: {type(exc).__name__}: {exc}") from exc

    @api.get("/jobs/{call_id}")
    async def poll_video(call_id: str):
        try:
            call = modal.FunctionCall.from_id(call_id)
            result = call.get(timeout=0)
        except TimeoutError:
            return JSONResponse(status_code=202, content={"status": "running", "call_id": call_id})
        except modal.exception.OutputExpiredError as exc:
            raise HTTPException(status_code=410, detail="LTX 2.5 job result expired") from exc
        except Exception as exc:  # noqa: BLE001
            print({"event": "ltx25_gateway_poll_failed", "call_id": call_id, "error": repr(exc)}, flush=True)
            raise HTTPException(status_code=502, detail=f"LTX 2.5 runtime failed: {type(exc).__name__}: {exc}") from exc
        if not isinstance(result, (bytes, bytearray)) or not result:
            raise HTTPException(status_code=502, detail="LTX 2.5 runtime returned an empty video")
        return Response(content=bytes(result), media_type="video/mp4")

    @api.delete("/jobs/{call_id}")
    async def cancel_video(call_id: str):
        try:
            call = modal.FunctionCall.from_id(call_id)
            call.cancel(terminate_containers=False)
            return {"status": "cancelled", "call_id": call_id}
        except modal.exception.OutputExpiredError as exc:
            raise HTTPException(status_code=410, detail="LTX 2.5 job result expired") from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"LTX 2.5 cancel failed: {type(exc).__name__}: {exc}") from exc

    return api
