from __future__ import annotations

import json
import time

import modal

app = modal.App("saga-worker-account-probe")


@app.function(timeout=30)
def probe() -> dict[str, object]:
    return {"ok": True, "observed_at": int(time.time())}


@app.local_entrypoint()
def main() -> None:
    print(json.dumps(probe.remote(), sort_keys=True))
