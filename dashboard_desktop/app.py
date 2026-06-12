from __future__ import annotations

from pathlib import Path

import webview

from .bridge import DashboardBridge


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = ROOT / "dashboard_app" / "dist" / "index.html"


def run() -> None:
    if not FRONTEND_DIST.exists():
        raise RuntimeError(
            f"Dashboard frontend build not found: {FRONTEND_DIST}. Run `npm run build` in dashboard_app first."
        )
    window = webview.create_window(
        "S.A.G.A. Dashboard",
        FRONTEND_DIST.as_uri(),
        js_api=DashboardBridge(),
        width=1440,
        height=980,
        min_size=(1100, 760),
    )
    webview.start(debug=False)
