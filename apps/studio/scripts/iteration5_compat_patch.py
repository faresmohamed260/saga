from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def replace_once(relative_path: str, old: str, new: str) -> None:
    path = ROOT / relative_path
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{relative_path}: expected one replacement, found {count}\n{old[:600]}")
    path.write_text(text.replace(old, new, 1))


replace_once(
    "integrations/comfyui/ltx23_app.py",
    '''\n\ndef _create_video_poster(video_path: Path) -> bytes:\n    poster_path = video_path.with_name(f"{video_path.stem}-poster.jpg")\n    command = [\n        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",\n        "-ss", "0.08",\n        "-i", str(video_path),\n        "-frames:v", "1",\n        "-q:v", "3",\n        str(poster_path),\n    ]\n    result = subprocess.run(command, capture_output=True, text=True, check=False)\n    if result.returncode != 0 or not poster_path.is_file() or poster_path.stat().st_size <= 0:\n        raise RuntimeError(f"ffmpeg poster extraction failed: {result.stderr[-3000:]}")\n    return poster_path.read_bytes()\n''',
    '',
)
replace_once(
    "integrations/comfyui/ltx23_app.py",
    '    ) -> dict[str, Any]:\n        del negative_prompt  # REDGraft reference recipe uses zeroed negative conditioning.\n',
    '    ) -> bytes:\n        del negative_prompt  # REDGraft reference recipe uses zeroed negative conditioning.\n',
)
replace_once(
    "integrations/comfyui/ltx23_app.py",
    '''                    poster_bytes = _create_video_poster(final_path)\n                    _log(\n                        "ltx25_delivery_ready",\n                        resolution=resolution,\n                        aspect_ratio=aspect_ratio,\n                        frame_rate=int(frame_rate),\n                        duration_seconds=int(duration_seconds),\n                        width=delivery_width,\n                        height=delivery_height,\n                        bytes=final_path.stat().st_size,\n                        poster_bytes=len(poster_bytes),\n                    )\n                    return {\n                        "video": final_path.read_bytes(),\n                        "poster": poster_bytes,\n                        "poster_content_type": "image/jpeg",\n                    }\n''',
    '''                    _log(\n                        "ltx25_delivery_ready",\n                        resolution=resolution,\n                        aspect_ratio=aspect_ratio,\n                        frame_rate=int(frame_rate),\n                        duration_seconds=int(duration_seconds),\n                        width=delivery_width,\n                        height=delivery_height,\n                        bytes=final_path.stat().st_size,\n                    )\n                    return final_path.read_bytes()\n''',
)

replace_once(
    "integrations/comfyui/ltx23_gateway.py",
    '''image = modal.Image.debian_slim(python_version="3.11").pip_install(\n    f"modal=={MODAL_VERSION}",\n    "fastapi[standard]==0.121.0",\n    "python-multipart>=0.0.20,<1",\n)\n''',
    '''image = modal.Image.debian_slim(python_version="3.11").apt_install("ffmpeg").pip_install(\n    f"modal=={MODAL_VERSION}",\n    "fastapi[standard]==0.121.0",\n    "python-multipart>=0.0.20,<1",\n)\n''',
)
replace_once(
    "integrations/comfyui/ltx23_gateway.py",
    '''    def _split_result(result):\n        if isinstance(result, (bytes, bytearray)):\n            return bytes(result), None, None\n        if isinstance(result, dict):\n            video = result.get("video")\n            poster = result.get("poster")\n            poster_type = str(result.get("poster_content_type") or "image/jpeg")\n            if isinstance(video, (bytes, bytearray)) and video:\n                normalized_poster = bytes(poster) if isinstance(poster, (bytes, bytearray)) and poster else None\n                return bytes(video), normalized_poster, poster_type\n        return None, None, None\n''',
    '''    def _extract_poster(video: bytes) -> bytes:\n        import subprocess\n\n        command = [\n            "ffmpeg", "-hide_banner", "-loglevel", "error",\n            "-ss", "0.08",\n            "-i", "pipe:0",\n            "-frames:v", "1",\n            "-f", "image2pipe",\n            "-vcodec", "mjpeg",\n            "-q:v", "3",\n            "pipe:1",\n        ]\n        result = subprocess.run(command, input=video, capture_output=True, check=False)\n        if result.returncode != 0 or not result.stdout:\n            detail = result.stderr.decode("utf-8", errors="replace")[-3000:]\n            raise RuntimeError(f"ffmpeg poster extraction failed: {detail}")\n        return bytes(result.stdout)\n''',
)
replace_once(
    "integrations/comfyui/ltx23_gateway.py",
    '''        video, _, _ = _split_result(result)\n        if not video:\n            raise HTTPException(status_code=502, detail="LTX 2.5 runtime returned an empty video")\n        return Response(content=video, media_type="video/mp4")\n''',
    '''        if not isinstance(result, (bytes, bytearray)) or not result:\n            raise HTTPException(status_code=502, detail="LTX 2.5 runtime returned an empty video")\n        return Response(content=bytes(result), media_type="video/mp4")\n''',
)
replace_once(
    "integrations/comfyui/ltx23_gateway.py",
    '''        _, poster, poster_type = _split_result(result)\n        if not poster:\n            raise HTTPException(status_code=404, detail="LTX 2.5 poster is unavailable")\n        if not str(poster_type or "").startswith("image/"):\n            raise HTTPException(status_code=502, detail="LTX 2.5 poster has an invalid content type")\n        return Response(content=poster, media_type=poster_type)\n''',
    '''        if not isinstance(result, (bytes, bytearray)) or not result:\n            raise HTTPException(status_code=502, detail="LTX 2.5 runtime returned an empty video")\n        try:\n            poster = _extract_poster(bytes(result))\n        except Exception as exc:  # noqa: BLE001\n            print({"event": "ltx25_gateway_poster_extract_failed", "call_id": call_id, "error": repr(exc)}, flush=True)\n            raise HTTPException(status_code=502, detail=f"LTX 2.5 poster extraction failed: {type(exc).__name__}: {exc}") from exc\n        return Response(content=poster, media_type="image/jpeg")\n''',
)

replace_once(
    "apps/studio/scripts/check-video-poster-contract.mjs",
    '''assert.match(runtimeSource, /"poster_content_type": "image\\/jpeg"/);\nassert.match(runtimeSource, /_create_video_poster\\(final_path\\)/);\nassert.match(gatewaySource, /\\/jobs\\/\\{call_id\\}\\/poster/);\n''',
    '''assert.match(runtimeSource, /\\) -> bytes:/);\nassert.doesNotMatch(runtimeSource, /_create_video_poster/);\nassert.match(gatewaySource, /apt_install\\("ffmpeg"\\)/);\nassert.match(gatewaySource, /def _extract_poster\\(video: bytes\\)/);\nassert.match(gatewaySource, /\\/jobs\\/\\{call_id\\}\\/poster/);\n''',
)

print("Iteration 5 compatibility refinement applied")
