#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zlib


EXPECTED_MODEL = 'Qwen/Qwen-Image-Edit-2511'
EXPECTED_PRECISION = 'civitai-bfloat16'
EXPECTED_CHECKPOINT_VERSION_ID = 2553500
EXPECTED_CHECKPOINT_FILE_ID = 2443737
EXPECTED_STEPS = 4
EXPECTED_PLACEMENT = 'civitai-bf16-lightning-4xA10-sharded'


def png(width: int = 256, height: int = 256) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack('>I', len(data)) + body + struct.pack('>I', zlib.crc32(body) & 0xFFFFFFFF)

    signature = b'\x89PNG\r\n\x1a\n'
    header = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            row.extend((48 + x * 96 // width, 62 + y * 72 // height, 112))
        rows.append(bytes(row))
    return signature + chunk(b'IHDR', header) + chunk(b'IDAT', zlib.compress(b''.join(rows), 9)) + chunk(b'IEND', b'')


def multipart(fields: dict[str, str], filename: str, payload: bytes) -> tuple[bytes, str]:
    boundary = f'saga-qwen-smoke-{uuid.uuid4().hex}'
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        )
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="image_files"; filename="{filename}"\r\nContent-Type: image/png\r\n\r\n'.encode()
        + payload + b'\r\n'
    )
    parts.append(f'--{boundary}--\r\n'.encode())
    return b''.join(parts), boundary


def request_json(
    url: str,
    *,
    method: str = 'GET',
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 120,
):
    req = urllib.request.Request(url, method=method, data=data, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
            return response.status, response.headers, json.loads(raw.decode('utf-8'))
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            body = json.loads(raw.decode('utf-8'))
        except Exception:
            body = {'raw': raw.decode('utf-8', errors='replace')}
        return exc.code, exc.headers, body


def validate_health(health: dict) -> None:
    if health.get('model') != EXPECTED_MODEL or health.get('precision') != EXPECTED_PRECISION:
        raise SystemExit(f'Qwen gateway reports wrong model/precision: {health}')
    checkpoint = health.get('checkpoint') or {}
    if int(checkpoint.get('version_id') or 0) != EXPECTED_CHECKPOINT_VERSION_ID:
        raise SystemExit(f'Qwen gateway reports wrong Civitai checkpoint version: {health}')
    worker = health.get('worker') or {}
    checkpoint_file_id = checkpoint.get('file_id') or worker.get('checkpoint_file_id')
    if int(checkpoint_file_id or 0) != EXPECTED_CHECKPOINT_FILE_ID:
        raise SystemExit(f'Qwen worker reports wrong Civitai checkpoint file: {health}')
    acceleration = health.get('acceleration') or {}
    if acceleration.get('type') != 'lightning-lora' or acceleration.get('default_steps') != EXPECTED_STEPS:
        raise SystemExit(f'Qwen gateway is not serving the Lightning 4-step profile: {health}')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('gateway_url')
    parser.add_argument('--timeout', type=int, default=1800)
    parser.add_argument('--max-inference-seconds', type=float, default=300.0)
    parser.add_argument('--health-log-interval', type=float, default=15.0)
    args = parser.parse_args()
    base = args.gateway_url.rstrip('/')

    status, _, health = request_json(base + '/health')
    if status != 200 or health.get('ready') is not True:
        raise SystemExit(f'Qwen gateway health failed: HTTP {status}: {health}')
    validate_health(health)

    body, boundary = multipart(
        {
            'prompt': 'Turn this simple gradient reference into a clean blue editorial poster with a centered white circle.',
            'negative_prompt': ' ',
            'seed': '42',
            'steps': str(EXPECTED_STEPS),
            'cfg': '1.0',
            'megapixels': '0.25',
        },
        'qwen-smoke-reference.png',
        png(),
    )
    submit_started = time.monotonic()
    status, _, submitted = request_json(
        base + '/jobs/edit',
        method='POST',
        data=body,
        headers={'Content-Type': f'multipart/form-data; boundary={boundary}', 'Accept': 'application/json'},
        timeout=180,
    )
    if status != 200 or not submitted.get('call_id'):
        raise SystemExit(f'Qwen submit failed: HTTP {status}: {submitted}')
    if submitted.get('inference_steps') != EXPECTED_STEPS or float(submitted.get('true_cfg_scale') or 0) != 1.0:
        raise SystemExit(f'Qwen submit did not use Lightning 4-step settings: {submitted}')

    call_id = submitted['call_id']
    started = time.monotonic()
    polls = 0
    last_health_log = 0.0
    last_state = None
    state_timeline: list[dict[str, object]] = []

    while time.monotonic() - started < args.timeout:
        polls += 1
        elapsed = time.monotonic() - started
        if elapsed - last_health_log >= args.health_log_interval or last_state is None:
            health_status, _, current_health = request_json(base + '/health', timeout=60)
            current_state = ((current_health.get('worker') or {}).get('state') if health_status == 200 else 'health-error') or 'unknown'
            if current_state != last_state:
                state_timeline.append({'state': current_state, 'seconds': round(elapsed, 3)})
                print(json.dumps({'event': 'qwen-smoke-state', 'state': current_state, 'seconds': round(elapsed, 3)}), flush=True)
                last_state = current_state
            last_health_log = elapsed

        req = urllib.request.Request(
            base + '/jobs/' + urllib.parse.quote(call_id),
            headers={'Accept': 'image/*, application/json'},
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as response:
                raw = response.read()
                content_type = str(response.headers.get('content-type') or '').lower()
                if response.status == 202:
                    time.sleep(3)
                    continue
                if response.status == 200 and content_type.startswith('image/'):
                    if not raw.startswith(b'\x89PNG\r\n\x1a\n'):
                        raise SystemExit(f'Qwen returned non-PNG image bytes: {raw[:16]!r}')
                    inference_seconds = round(time.monotonic() - started, 3)
                    total_seconds = round(time.monotonic() - submit_started, 3)
                    final_status, _, final_health = request_json(base + '/health', timeout=60)
                    worker = final_health.get('worker') if final_status == 200 else {}
                    worker = worker or {}
                    if worker.get('placement') != EXPECTED_PLACEMENT:
                        raise SystemExit(f'Qwen generation completed on the wrong runtime placement: {worker}')
                    if int(worker.get('checkpoint_file_id') or 0) != EXPECTED_CHECKPOINT_FILE_ID:
                        raise SystemExit(f'Qwen generation completed on the wrong Civitai file: {worker}')
                    result = {
                        'ready': True,
                        'callId': call_id,
                        'polls': polls,
                        'bytes': len(raw),
                        'contentType': content_type,
                        'workerId': submitted.get('worker_id'),
                        'ecosystem': submitted.get('ecosystem'),
                        'checkpointVersionId': EXPECTED_CHECKPOINT_VERSION_ID,
                        'checkpointFileId': EXPECTED_CHECKPOINT_FILE_ID,
                        'inferenceSteps': submitted.get('inference_steps'),
                        'trueCfgScale': submitted.get('true_cfg_scale'),
                        'acceleration': submitted.get('acceleration'),
                        'workerPlacement': worker.get('placement'),
                        'inferenceSeconds': inference_seconds,
                        'totalSeconds': total_seconds,
                        'workerReportedGenerationSeconds': worker.get('last_generation_seconds'),
                        'workerReportedStartupSeconds': worker.get('startup_seconds'),
                        'workerReportedTransformerLoadSeconds': worker.get('transformer_load_seconds'),
                        'stateTimeline': state_timeline,
                    }
                    print(json.dumps(result), flush=True)
                    if inference_seconds > args.max_inference_seconds:
                        raise SystemExit(
                            f'Qwen fallback inference is still too slow: {inference_seconds}s > {args.max_inference_seconds}s threshold'
                        )
                    return
                raise SystemExit(f'Unexpected Qwen poll response: HTTP {response.status} {content_type}: {raw[:500]!r}')
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            if exc.code == 202:
                time.sleep(3)
                continue
            raise SystemExit(f'Qwen poll failed: HTTP {exc.code}: {raw.decode("utf-8", errors="replace")}') from exc

    raise SystemExit(
        f'Qwen fallback smoke timed out after {args.timeout}s and {polls} polls; state timeline={json.dumps(state_timeline)}'
    )


if __name__ == '__main__':
    main()
