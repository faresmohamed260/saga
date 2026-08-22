import os

import modal

APP_NAME = "saga-flux2-klein-gateway"
RUNTIME_APP_NAME = "saga-flux2-klein-9b"
RUNTIME_CLASS_NAME = "Flux2KleinWorker"
MODAL_VERSION = "1.4.2"

image = modal.Image.debian_slim(python_version="3.11").pip_install(
    f"modal=={MODAL_VERSION}",
    "fastapi[standard]==0.121.0",
)
app = modal.App(APP_NAME, image=image)


@app.function(image=image, timeout=1800)
@modal.asgi_app()
def web():
    from fastapi import FastAPI, File, Form, HTTPException, UploadFile
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, Response

    api = FastAPI(title="SAGA FLUX.2 Klein Gateway", version="0.2.0")
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
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    def _validate_image(image_file, image_bytes, prompt):
        if not image_file.content_type or not image_file.content_type.startswith("image/"):
            raise HTTPException(status_code=415, detail="image_file must be an image")
        if not image_bytes:
            raise HTTPException(status_code=400, detail="image_file is empty")
        if len(image_bytes) > 25 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="image_file must be 25 MB or smaller")
        if not prompt.strip():
            raise HTTPException(status_code=400, detail="prompt is required")

    def _worker_call(image_bytes, image_file, prompt, negative_prompt, seed, steps, cfg, megapixels):
        worker_cls = modal.Cls.from_name(RUNTIME_APP_NAME, RUNTIME_CLASS_NAME)
        return worker_cls().edit.spawn(
            image_bytes=image_bytes,
            filename=image_file.filename or "input.png",
            prompt=prompt.strip(),
            negative_prompt=negative_prompt,
            seed=int(seed),
            steps=max(1, min(int(steps), 50)),
            cfg=float(cfg),
            megapixels=max(0.25, min(float(megapixels), 4.0)),
        )

    @api.get("/health")
    async def health():
        return {
            "ready": True,
            "gateway": APP_NAME,
            "runtime_app": RUNTIME_APP_NAME,
            "runtime_class": RUNTIME_CLASS_NAME,
            "async_jobs": True,
        }

    @api.post("/jobs/edit")
    async def submit_edit(
        image_file: UploadFile = File(...),
        prompt: str = Form(...),
        negative_prompt: str = Form(""),
        seed: int = Form(42),
        steps: int = Form(4),
        cfg: float = Form(1.0),
        megapixels: float = Form(0.5),
    ):
        image_bytes = await image_file.read()
        _validate_image(image_file, image_bytes, prompt)
        try:
            call = _worker_call(image_bytes, image_file, prompt, negative_prompt, seed, steps, cfg, megapixels)
            return {"status": "queued", "call_id": call.object_id}
        except Exception as exc:  # noqa: BLE001
            print({"event": "flux2_gateway_spawn_failed", "error": repr(exc)}, flush=True)
            raise HTTPException(status_code=502, detail=f"FLUX.2 runtime submit failed: {type(exc).__name__}: {exc}") from exc

    @api.get("/jobs/{call_id}")
    async def poll_edit(call_id: str):
        try:
            call = modal.FunctionCall.from_id(call_id)
            result = call.get(timeout=0)
        except TimeoutError:
            return JSONResponse(status_code=202, content={"status": "running", "call_id": call_id})
        except modal.exception.OutputExpiredError as exc:
            raise HTTPException(status_code=410, detail="FLUX.2 job result expired") from exc
        except Exception as exc:  # noqa: BLE001
            print({"event": "flux2_gateway_poll_failed", "call_id": call_id, "error": repr(exc)}, flush=True)
            raise HTTPException(status_code=502, detail=f"FLUX.2 runtime failed: {type(exc).__name__}: {exc}") from exc
        return Response(content=result, media_type="image/png")

    @api.post("/edit")
    async def edit(
        image_file: UploadFile = File(...),
        prompt: str = Form(...),
        negative_prompt: str = Form(""),
        seed: int = Form(42),
        steps: int = Form(4),
        cfg: float = Form(1.0),
        megapixels: float = Form(0.5),
    ):
        image_bytes = await image_file.read()
        _validate_image(image_file, image_bytes, prompt)
        try:
            call = _worker_call(image_bytes, image_file, prompt, negative_prompt, seed, steps, cfg, megapixels)
            result = call.get()
        except Exception as exc:  # noqa: BLE001
            print({"event": "flux2_gateway_edit_failed", "error": repr(exc)}, flush=True)
            raise HTTPException(status_code=502, detail=f"FLUX.2 runtime failed: {type(exc).__name__}: {exc}") from exc
        return Response(content=result, media_type="image/png")

    return api
