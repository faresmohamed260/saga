from __future__ import annotations

import json
from pathlib import Path

import uvicorn

try:
    from integrations.comfyui.domain_gateway import app
except ImportError:  # pragma: no cover
    from domain_gateway import app

CONFIG = json.loads((Path(__file__).resolve().parent / "gateway_config.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=CONFIG["listen_host"],
        port=int(CONFIG["listen_port"]),
        reload=False,
    )
