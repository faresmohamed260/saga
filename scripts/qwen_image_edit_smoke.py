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


def request_json(url: str, *, method: str = 'GET', data: bytes | None = None, headers: dict[str, str] | None = None, timeout: int = 120):
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('gateway_url')
    parser.add_argument('--timeout', type=int, default=1800)
    parser.add_argument('--max-inference-seconds', type=float, default=300.0)
    args = parser.parse_args()
    base = args.gateway_url.rstrip('/')

    status, _, health = request_json(base + '/health')
    if status != 200 or health.get('ready') is not True:
        raise SystemExit(f'Qwen gateway health failed: HTTP {status}: {health}')
    if health.get('model') != 'Qwen/Qwen-Image-Edit-2511' or health.get('precision') != 'official-bfloat16':
        raise SystemExit(f'Qwen gateway reports wrong model/precision: {health}')
    acceleration = health.get('acceleration') or {}
    if acceleration.get('type') != 'lightning-lora' or acceleration.get('default_steps') != 8:
        raise SystemExit(f'Qwen gateway is not serving the Lightning 8-step profile: {health}')

    body, boundary = multipart(
        {
            'prompt': 'Turn this simple gradient reference into a clean blue editorial poster with a centered white circle.',
            'negative_prompt': ' ',
            'seed': '42',
            'steps': '8',
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
    if submitted.get('inference_steps') != 8 or float(submitted.get('true_cfg_scale') or 0) != 1.0:
        raise SystemExit(f'Qwen submit did not use Lightning 8-step settings: {submitted}')
    call_id = submitted['call_id']
    started = time.monotonic()
    polls = 0
    while time.monotonic() - started < args.timeout:
        polls += 1
        req = urllib.request.Request(base + '/jobs/' + urllib.parse.quote(call_id), headers={'Accept': 'image/*, application/json'})
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
                    result = {
                        'ready': True,
                        'callId': call_id,
                        'polls': polls,
                        'bytes': len(raw),
                        'contentType': content_type,
                        'workerId': submitted.get('worker_id'),
                        'ecosystem': submitted.get('ecosystem'),
                        'inferenceSteps': submitted.get('inference_steps'),
                        'trueCfgScale': submitted.get('true_cfg_scale'),
                        'acceleration': submitted.get('acceleration'),
                        'inferenceSeconds': inference_seconds,
                        'totalSeconds': total_seconds,
                    }
                    print(json.dumps(result))
                    if inference_seconds > args.max_inference_seconds:
                        raise SystemExit(
                            f'Qwen Lightning inference is still too slow: {inference_seconds}s > {args.max_inference_seconds}s threshold'
                        )
                    return
                raise SystemExit(f'Unexpected Qwen poll response: HTTP {response.status} {content_type}: {raw[:500]!r}')
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            if exc.code == 202:
                time.sleep(3)
                continue
            raise SystemExit(f'Qwen poll failed: HTTP {exc.code}: {raw.decode("utf-8", errors="replace")}') from exc
    raise SystemExit(f'Qwen smoke timed out after {args.timeout}s and {polls} polls')


if __name__ == '__main__':
    main()
