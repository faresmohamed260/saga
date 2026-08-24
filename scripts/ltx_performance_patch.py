from pathlib import Path

app = Path('integrations/comfyui/ltx23_app.py')
s = app.read_text(encoding='utf-8')

def one(old, new):
    global s
    if s.count(old) != 1:
        raise SystemExit(f'app: expected one match, got {s.count(old)}: {old[:90]!r}')
    s = s.replace(old, new, 1)

one(
    'GPU_CHOICES = [x.strip() for x in os.environ.get("MODAL_LTX25_GPU", "L40S,A100-40GB").split(",") if x.strip()]\n',
    'GPU_CHOICES = [x.strip() for x in os.environ.get("MODAL_LTX25_GPU", "H100,L40S,A100-40GB").split(",") if x.strip()]\n',
)
one(
    'WORKER_MAX_CONTAINERS = int(os.environ.get("MODAL_LTX25_MAX_CONTAINERS", "1"))\n',
    'WORKER_MAX_CONTAINERS = int(os.environ.get("MODAL_LTX25_MAX_CONTAINERS", "2"))\n',
)
one(
    '    ) -> bytes:\n        del negative_prompt  # REDGraft reference recipe uses zeroed negative conditioning.\n',
    '    ) -> dict[str, bytes]:\n        del negative_prompt  # REDGraft reference recipe uses zeroed negative conditioning.\n',
)
one(
    '                    result = final_path.read_bytes()\n                    _set_worker_state("ready")\n                    return result\n',
    '''                    result = final_path.read_bytes()\n                    poster_process = subprocess.run(\n                        [\n                            "ffmpeg", "-hide_banner", "-loglevel", "error",\n                            "-ss", "0.08", "-i", str(final_path),\n                            "-frames:v", "1", "-f", "image2pipe",\n                            "-vcodec", "mjpeg", "-q:v", "3", "pipe:1",\n                        ],\n                        capture_output=True,\n                        check=False,\n                    )\n                    if poster_process.returncode != 0 or not poster_process.stdout:\n                        detail = poster_process.stderr.decode("utf-8", errors="replace")[-3000:]\n                        raise RuntimeError(f"ffmpeg poster extraction failed: {detail}")\n                    _set_worker_state("ready")\n                    return {"video": result, "poster": bytes(poster_process.stdout)}\n''',
)
one(
    '    ) -> bytes:\n        try:\n            return self._generate_impl(\n',
    '    ) -> dict[str, bytes]:\n        try:\n            return self._generate_impl(\n',
)
app.write_text(s, encoding='utf-8')

gateway = Path('integrations/comfyui/ltx23_gateway.py')
g = gateway.read_text(encoding='utf-8')

def gone(old, new):
    global g
    if g.count(old) != 1:
        raise SystemExit(f'gateway: expected one match, got {g.count(old)}: {old[:90]!r}')
    g = g.replace(old, new, 1)

gone(
    '''        if not isinstance(result, (bytes, bytearray)) or not result:\n            raise HTTPException(status_code=502, detail="LTX 2.5 runtime returned an empty video")\n        return Response(content=bytes(result), media_type="video/mp4")\n\n    @api.get("/jobs/{call_id}/poster")\n''',
    '''        video = result.get("video") if isinstance(result, dict) else result\n        if not isinstance(video, (bytes, bytearray)) or not video:\n            raise HTTPException(status_code=502, detail="LTX 2.5 runtime returned an empty video")\n        return Response(content=bytes(video), media_type="video/mp4")\n\n    @api.get("/jobs/{call_id}/poster")\n''',
)
gone(
    '''        if not isinstance(result, (bytes, bytearray)) or not result:\n            raise HTTPException(status_code=502, detail="LTX 2.5 runtime returned an empty video")\n        try:\n            poster = _extract_poster(bytes(result))\n        except Exception as exc:  # noqa: BLE001\n            print({"event": "ltx25_gateway_poster_extract_failed", "call_id": call_id, "error": repr(exc)}, flush=True)\n            raise HTTPException(status_code=502, detail=f"LTX 2.5 poster extraction failed: {type(exc).__name__}: {exc}") from exc\n        return Response(content=poster, media_type="image/jpeg")\n''',
    '''        if isinstance(result, dict):\n            poster = result.get("poster")\n            if isinstance(poster, (bytes, bytearray)) and poster:\n                return Response(content=bytes(poster), media_type="image/jpeg")\n            result = result.get("video")\n        if not isinstance(result, (bytes, bytearray)) or not result:\n            raise HTTPException(status_code=502, detail="LTX 2.5 runtime returned an empty video")\n        try:\n            poster = _extract_poster(bytes(result))\n        except Exception as exc:  # noqa: BLE001\n            print({"event": "ltx25_gateway_poster_extract_failed", "call_id": call_id, "error": repr(exc)}, flush=True)\n            raise HTTPException(status_code=502, detail=f"LTX 2.5 poster extraction failed: {type(exc).__name__}: {exc}") from exc\n        return Response(content=poster, media_type="image/jpeg")\n''',
)
gateway.write_text(g, encoding='utf-8')
