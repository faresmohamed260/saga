"""Deploy and prefetch the direct Modal ComfyUI runtime across provider accounts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from saga.providers.inference_registry import MODAL_COMFYUI_PROVIDER
from saga.providers.modal_admin_service import rollout_modal_comfyui_pool, utc_timestamp, write_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy and prefetch Modal ComfyUI weights across provider accounts.")
    parser.add_argument("--provider", default=MODAL_COMFYUI_PROVIDER, help="Inference provider key.")
    parser.add_argument("--labels", default="", help="Comma-separated account labels to target.")
    parser.add_argument("--limit", type=int, default=0, help="Optional max account count to process.")
    parser.add_argument("--force-prefetch", action="store_true", help="Force a fresh prefetch even if the account already has cached weights.")
    parser.add_argument("--output", default="", help="Optional path for the JSON summary report.")
    args = parser.parse_args()

    requested_labels = {label.strip().lower() for label in str(args.labels or "").split(",") if label.strip()}
    summary = rollout_modal_comfyui_pool(labels=requested_labels, limit=max(0, int(args.limit or 0)), force_prefetch=bool(args.force_prefetch))
    output_path = Path(args.output) if str(args.output or "").strip() else PROJECT_ROOT / "analysis_outputs" / "provider_smoke_direct" / f"modal_comfyui_prewarm_{utc_timestamp()}.json"
    write_summary(output_path, summary)
    for row in summary.get("results", []):
        print(f"{row.get('account_label')}: {row.get('status')}", flush=True)
    print(output_path.resolve())


if __name__ == "__main__":
    main()
