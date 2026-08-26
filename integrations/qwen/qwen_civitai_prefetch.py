from __future__ import annotations

import hashlib
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import modal

APP_NAME = "saga-qwen-civitai-prefetch"
CACHE_DIR = "/cache"
CACHE_VOLUME_NAME = os.environ.get("SAGA_MODAL_WORKER_VOLUME", "saga-qwen-image-edit-2511-cache")
CIVITAI_VERSION_ID = 2553500
CIVITAI_FILE_ID = 2443737
CIVITAI_WEIGHT_NAME = "qwnImageEdit_v16Bf16.safetensors"
CIVITAI_WEIGHT_SHA256 = "4F8CA1242C7FDBE6CFD1835833C66E9CDBCF23EA27C7B811B43BDA316F30A6DA"
CIVITAI_EXPECTED_BYTES = 40861031560
CIVITAI_DIR = Path(CACHE_DIR) / "qwen-image-edit-2511-civitai-v16-bf16"
CIVITAI_WEIGHT_PATH = CIVITAI_DIR / CIVITAI_WEIGHT_NAME
CIVITAI_HASH_MARKER = CIVITAI_DIR / f"{CIVITAI_WEIGHT_NAME}.sha256"

cache_volume = modal.Volume.from_name(CACHE_VOLUME_NAME, create_if_missing=True)
_token = str(os.environ.get("CIVITAI_API_TOKEN") or "").strip()
RUNTIME_SECRETS = [modal.Secret.from_dict({"CIVITAI_API_TOKEN": _token})] if _token else []

image = modal.Image.debian_slim(python_version="3.11")
app = modal.App(APP_NAME, image=image)


def _token_or_raise() -> str:
    token = str(os.environ.get("CIVITAI_API_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("CIVITAI_API_TOKEN is required for Qwen checkpoint staging")
    return token


def _clean_error_body(exc: urllib.error.HTTPError) -> str:
    try:
        body = exc.read(2048).decode("utf-8", errors="replace").strip()
    except Exception:
        body = ""
    # Never include the request URL: the authenticated compatibility URL contains the token.
    return body[:1000] or "no response body"


@app.function(
    image=image,
    timeout=7200,
    volumes={CACHE_DIR: cache_volume},
    secrets=RUNTIME_SECRETS,
)
def stage_qwen_civitai_checkpoint(force: bool = False) -> dict[str, object]:
    expected = CIVITAI_WEIGHT_SHA256.upper()
    if not force and CIVITAI_WEIGHT_PATH.is_file() and CIVITAI_HASH_MARKER.is_file():
        marker = CIVITAI_HASH_MARKER.read_text(encoding="utf-8").strip().upper()
        if marker == expected and CIVITAI_WEIGHT_PATH.stat().st_size == CIVITAI_EXPECTED_BYTES:
            return {
                "ready": True,
                "cached": True,
                "versionId": CIVITAI_VERSION_ID,
                "fileId": CIVITAI_FILE_ID,
                "weight": CIVITAI_WEIGHT_NAME,
                "sha256": expected,
                "bytes": CIVITAI_EXPECTED_BYTES,
            }

    CIVITAI_DIR.mkdir(parents=True, exist_ok=True)
    temporary = CIVITAI_WEIGHT_PATH.with_suffix(CIVITAI_WEIGHT_PATH.suffix + ".partial")
    if temporary.exists():
        temporary.unlink()

    query = urllib.parse.urlencode({
        "fileId": CIVITAI_FILE_ID,
        "token": _token_or_raise(),
    })
    request = urllib.request.Request(
        f"https://civitai.com/api/download/models/{CIVITAI_VERSION_ID}?{query}",
        headers={
            "Accept": "application/octet-stream",
            "User-Agent": "saga-qwen-checkpoint-prefetch/2.0",
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
        status = int(exc.code)
        detail = _clean_error_body(exc)
        raise RuntimeError(f"Civitai checkpoint download failed with HTTP {status}: {detail}") from None
    except urllib.error.URLError as exc:
        if temporary.exists():
            temporary.unlink()
        reason = str(getattr(exc, "reason", "network error"))[:500]
        raise RuntimeError(f"Civitai checkpoint download failed: {reason}") from None
    except Exception as exc:
        if temporary.exists():
            temporary.unlink()
        raise RuntimeError(f"Civitai checkpoint download failed: {type(exc).__name__}: {str(exc)[:500]}") from None

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
    return {
        "ready": True,
        "cached": False,
        "versionId": CIVITAI_VERSION_ID,
        "fileId": CIVITAI_FILE_ID,
        "weight": CIVITAI_WEIGHT_NAME,
        "sha256": expected,
        "bytes": downloaded,
        "elapsedSeconds": round(time.perf_counter() - started, 3),
    }
