import os

import modal

APP_NAME = "saga-qwen-image-edit-2511-gateway"
RUNTIME_APP_NAME = "saga-qwen-image-edit-2511"
RUNTIME_CLASS_NAME = "QwenImageEdit2511Worker"
MODAL_VERSION = "1.4.2"
ECOSYSTEM_ID = "qwen-image-edit-2511"
WORKER_ID = os.environ.get("SAGA_MODAL_WORKER_ID", f"{ECOSYSTEM_ID}-worker")
STATE_DICT_NAME = os.environ.get("SAGA_MODAL_WORKER_STATE_DICT", "saga-qwen-image-edit-2511-worker-state")
worker_state = modal.Dict.from_name(STATE_DICT_NAME, create_if_missing=True)

BASE_MODEL_REPO = "Qwen/Qwen-Image-Edit-2511"
CIVITAI_MODEL_ID = 2246542
CIVITAI_VERSION_ID = 2553500
CIVITAI_MODEL_NAME = "Qwn-Image-Edit-abliterated"
CIVITAI_VERSION_NAME = "v1.6-bf16"
CIVITAI_WEIGHT_NAME = "qwnImageEdit_v16Bf16.safetensors"
CIVITAI_WEIGHT_SHA256 = "4F8CA1242C7FDBE6CFD1835833C66E9CDBCF23EA27C7B811B43BDA316F30A6DA"
LIGHTNING_REPO = "lightx2v/Qwen-Image-Edit-2511-Lightning"
LIGHTNING_WEIGHT_NAME = "Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors"
LIGHTNING_MIN_STEPS = 1
LIGHTNING_MAX_STEPS = 50
LIGHTNING_DEFAULT_STEPS = 4
LIGHTNING_TRUE_CFG_SCALE = 1.0

CREDIT_PATTERNS = ("credit", "credits", "quota", "budget", "billing", "payment", "insufficient", "spending limit", "workspace budget")
UNAVAILABLE_PATTERNS = ("workspace is disabled", "workspace disabled", "unavailable", "not found", "stopped")


def _failure_payload(exc):
    text = f"{type(exc).__name__}: {exc}"
    lowered = text.lower()
    if any(pattern in lowered for pattern in CREDIT_PATTERNS):
        return 402, "WORKER_CREDIT_EXHAUSTED", "credit_exhausted", text
    if any(pattern in lowered for pattern in UNAVAILABLE_PATTERNS):
        return 503, "WORKER_UNAVAILABLE", "unavailable", text
    return 502, "WORKER_RUNTIME_FAILED", "failed", text


image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(f"modal=={MODAL_VERSION}", "fastapi[standard]==0.121.0")
    .env({
        "SAGA_MODAL_WORKER_ID": WORKER_ID,
        "SAGA_MODAL_WORKER_STATE_DICT": STATE_DICT_NAME,
    })
)
app = modal.App(APP_NAME, image=image)


@app.function(image=image, timeout=3600)
@modal.asgi_app()
def web():
    from fastapi import FastAPI, File, Form, HTTPException, UploadFile
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, Response

    api = FastAPI(title="SAGA Qwen Image Edit 2511 Gateway", version="1.2.0")
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

    def _validate_image(image_file, image_bytes, prompt, index=0):
        label = f"Image {index + 1}"
        if not image_file.content_type or not image_file.content_type.startswith("image/"):
            raise HTTPException(status_code=415, detail=f"{label} must be an image")
        if not image_bytes:
            raise HTTPException(status_code=400, detail=f"{label} is empty")
        if len(image_bytes) > 25 * 1024 * 1024:
            raise HTTPException(status_code=413, detail=f"{label} must be 25 MB or smaller")
        if not prompt.strip():
            raise HTTPException(status_code=400, detail="prompt is required")

    def _worker_call(images, prompt, negative_prompt, seed, steps, megapixels):
        worker_cls = modal.Cls.from_name(RUNTIME_APP_NAME, RUNTIME_CLASS_NAME)
        return worker_cls().edit.spawn(
            images=images,
            prompt=prompt.strip(),
            negative_prompt=negative_prompt,
            seed=int(seed),
            steps=max(LIGHTNING_MIN_STEPS, min(int(steps), LIGHTNING_MAX_STEPS)),
            cfg=LIGHTNING_TRUE_CFG_SCALE,
            megapixels=max(0.25, min(float(megapixels), 4.0)),
        )

    def _state():
        try:
            return worker_state.get("worker") or {"state": "sleeping", "worker_id": WORKER_ID, "ecosystem": ECOSYSTEM_ID}
        except Exception:
            return {"state": "unknown", "worker_id": WORKER_ID, "ecosystem": ECOSYSTEM_ID}

    def _submit_state():
        state = str(_state().get("state") or "").strip()
        if state in {"", "sleeping", "unknown"}:
            return "waking"
        if state in {"generating", "finalizing"}:
            return "queued"
        return state

    @api.get("/health")
    async def health():
        return {
            "ready": True,
            "gateway": APP_NAME,
            "runtime_app": RUNTIME_APP_NAME,
            "runtime_class": RUNTIME_CLASS_NAME,
            "async_jobs": True,
            "cancel_jobs": True,
            "multiple_references": True,
            "model": BASE_MODEL_REPO,
            "precision": "civitai-bfloat16",
            "checkpoint": {
                "source": "civitai",
                "model_id": CIVITAI_MODEL_ID,
                "version_id": CIVITAI_VERSION_ID,
                "model_name": CIVITAI_MODEL_NAME,
                "version_name": CIVITAI_VERSION_NAME,
                "weight": CIVITAI_WEIGHT_NAME,
                "sha256": CIVITAI_WEIGHT_SHA256,
            },
            "acceleration": {
                "type": "lightning-lora",
                "repo": LIGHTNING_REPO,
                "weight": LIGHTNING_WEIGHT_NAME,
                "steps": {"min": LIGHTNING_MIN_STEPS, "max": LIGHTNING_MAX_STEPS},
                "default_steps": LIGHTNING_DEFAULT_STEPS,
                "true_cfg_scale": LIGHTNING_TRUE_CFG_SCALE,
            },
            "worker": _state(),
        }

    @api.post("/warm")
    async def warm():
        try:
            worker_cls = modal.Cls.from_name(RUNTIME_APP_NAME, RUNTIME_CLASS_NAME)
            call = worker_cls().warm.spawn()
            return {"status": "waking", "call_id": call.object_id, "worker_id": WORKER_ID, "ecosystem": ECOSYSTEM_ID}
        except Exception as exc:  # noqa: BLE001
            status_code, error_code, state, detail = _failure_payload(exc)
            return JSONResponse(status_code=status_code, content={"error": detail, "errorCode": error_code, "workerState": state, "worker_id": WORKER_ID, "ecosystem": ECOSYSTEM_ID})

    @api.post("/jobs/edit")
    async def submit_edit(
        image_files: list[UploadFile] = File(...),
        prompt: str = Form(...),
        negative_prompt: str = Form(""),
        seed: int = Form(42),
        steps: int = Form(LIGHTNING_DEFAULT_STEPS),
        cfg: float = Form(LIGHTNING_TRUE_CFG_SCALE),
        megapixels: float = Form(1.0),
    ):
        if not image_files:
            raise HTTPException(status_code=400, detail="at least one reference image is required")
        images = []
        for index, image_file in enumerate(image_files):
            image_bytes = await image_file.read()
            _validate_image(image_file, image_bytes, prompt, index)
            images.append({
                "bytes": image_bytes,
                "filename": image_file.filename or f"input-{index + 1}.png",
                "content_type": image_file.content_type or "image/png",
            })
        try:
            effective_steps = max(LIGHTNING_MIN_STEPS, min(int(steps), LIGHTNING_MAX_STEPS))
            call = _worker_call(images, prompt, negative_prompt, seed, effective_steps, megapixels)
            return {
                "status": "queued",
                "call_id": call.object_id,
                "reference_count": len(images),
                "worker_state": _submit_state(),
                "worker_id": WORKER_ID,
                "ecosystem": ECOSYSTEM_ID,
                "inference_steps": effective_steps,
                "true_cfg_scale": LIGHTNING_TRUE_CFG_SCALE,
                "checkpoint_version_id": CIVITAI_VERSION_ID,
                "acceleration": "lightning-lora-bf16",
            }
        except Exception as exc:  # noqa: BLE001
            print({"event": "qwen_gateway_spawn_failed", "error": repr(exc)}, flush=True)
            status_code, error_code, state, detail = _failure_payload(exc)
            return JSONResponse(status_code=status_code, content={
                "error": detail,
                "errorCode": error_code,
                "workerState": state,
                "worker_id": WORKER_ID,
                "ecosystem": ECOSYSTEM_ID,
            })

    @api.get("/jobs/{call_id}")
    async def poll_edit(call_id: str):
        try:
            call = modal.FunctionCall.from_id(call_id)
            result = call.get(timeout=0)
        except TimeoutError:
            current = _state()
            return JSONResponse(status_code=202, content={
                "status": "running",
                "call_id": call_id,
                "worker_state": current.get("state") or "generating",
                "worker_id": WORKER_ID,
                "ecosystem": ECOSYSTEM_ID,
            })
        except modal.exception.OutputExpiredError as exc:
            raise HTTPException(status_code=410, detail="Qwen Image Edit 2511 job result expired") from exc
        except Exception as exc:  # noqa: BLE001
            print({"event": "qwen_gateway_poll_failed", "call_id": call_id, "error": repr(exc)}, flush=True)
            status_code, error_code, state, detail = _failure_payload(exc)
            return JSONResponse(status_code=status_code, content={
                "error": detail,
                "errorCode": error_code,
                "workerState": state,
                "worker_id": WORKER_ID,
                "ecosystem": ECOSYSTEM_ID,
            })
        return Response(content=result, media_type="image/png")

    @api.delete("/jobs/{call_id}")
    async def cancel_edit(call_id: str):
        try:
            call = modal.FunctionCall.from_id(call_id)
            call.cancel(terminate_containers=False)
            return {"status": "cancelled", "call_id": call_id}
        except modal.exception.OutputExpiredError as exc:
            raise HTTPException(status_code=410, detail="Qwen runtime cancel failed: result expired") from exc
        except Exception as exc:  # noqa: BLE001
            print({"event": "qwen_gateway_cancel_failed", "call_id": call_id, "error": repr(exc)}, flush=True)
            raise HTTPException(status_code=502, detail=f"Qwen runtime cancel failed: {type(exc).__name__}: {exc}") from exc

    return api