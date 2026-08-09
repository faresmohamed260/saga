"""Stop legacy Modal apps across configured inference-provider accounts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from saga.providers.inference_registry import MODAL_COMFYUI_PROVIDER, MODAL_KOKORO_PROVIDER, MODAL_XCORE_PROVIDER
from saga.providers.modal_admin_service import LEGACY_APP_NAMES, cleanup_modal_legacy_apps, utc_timestamp, write_summary

PROVIDER_CHOICES = (MODAL_COMFYUI_PROVIDER, MODAL_KOKORO_PROVIDER, MODAL_XCORE_PROVIDER)


def main() -> None:
    parser = argparse.ArgumentParser(description="Stop legacy Modal apps across configured provider accounts.")
    parser.add_argument(
        "--provider",
        default="all",
        choices=("all", *PROVIDER_CHOICES),
        help="Inference provider key to inspect, or 'all' to inspect every Modal-backed provider.",
    )
    parser.add_argument("--labels", default="", help="Comma-separated account labels to target.")
    parser.add_argument("--limit", type=int, default=0, help="Optional max account count to process per provider.")
    parser.add_argument("--execute", action="store_true", help="Actually stop the matching apps. Defaults to dry-run.")
    parser.add_argument("--app-names", default="", help="Optional comma-separated legacy app names to target.")
    parser.add_argument("--output", default="", help="Optional path for the JSON summary report.")
    args = parser.parse_args()

    requested_labels = {label.strip().lower() for label in str(args.labels or "").split(",") if label.strip()}
    requested_app_names = {name.strip() for name in str(args.app_names or "").split(",") if name.strip()} or set(LEGACY_APP_NAMES)
    summary = cleanup_modal_legacy_apps(
        labels=requested_labels,
        limit=max(0, int(args.limit or 0)),
        execute=bool(args.execute),
        app_names=requested_app_names,
    )
    output_path = Path(args.output) if str(args.output or "").strip() else PROJECT_ROOT / "analysis_outputs" / "provider_smoke_direct" / f"modal_legacy_cleanup_{utc_timestamp()}.json"
    write_summary(output_path, summary)
    for row in summary.get("results", []):
        print(f"{row.get('account_label')}: {row.get('status')}", flush=True)
    print(output_path.resolve())


if __name__ == "__main__":
    main()
