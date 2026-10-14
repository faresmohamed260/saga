#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from modal_cross_repo_ownership import assert_cross_repo_modal_ownership

ROOT = Path(__file__).resolve().parents[1]
SAGA_MANIFEST = ROOT / "config" / "modal-project-ownership.json"
RENDERLAB_MANIFEST_URL = (
    "https://raw.githubusercontent.com/faresmohamed260/renderlab/main/"
    "config/modal-project-ownership.json"
)


def fetch_json_with_retry(url: str, attempts: int = 3) -> dict:
    last_error: Exception | None = None
    request = Request(url, headers={"User-Agent": "saga-modal-ownership-verifier"})
    for attempt in range(1, attempts + 1):
        try:
            with urlopen(request, timeout=10) as response:  # noqa: S310 - fixed public GitHub URL
                if response.status != 200:
                    raise RuntimeError(f"HTTP {response.status}")
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as error:
            last_error = error
            if attempt < attempts:
                time.sleep(attempt * 0.75)
    raise RuntimeError(
        f"Unable to read RenderLab protected-main Modal ownership manifest: {last_error}"
    )


saga_manifest = json.loads(SAGA_MANIFEST.read_text(encoding="utf-8"))
renderlab_manifest = fetch_json_with_retry(RENDERLAB_MANIFEST_URL)
assert_cross_repo_modal_ownership(
    saga_manifest=saga_manifest, renderlab_manifest=renderlab_manifest
)
print("S.A.G.A./RenderLab protected-main Modal ownership is reciprocal and complete.")
