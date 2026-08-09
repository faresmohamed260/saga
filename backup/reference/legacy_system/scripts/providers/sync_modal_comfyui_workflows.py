"""Push local ComfyUI workflow JSON files to deployed Modal accounts without redeploying code."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from saga.providers.inference_registry import MODAL_COMFYUI_PROVIDER
from saga.providers.modal_admin_service import sync_modal_comfyui_workflows, utc_timestamp, write_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync local ComfyUI workflow JSONs to deployed Modal accounts.")
    parser.add_argument("--provider", default=MODAL_COMFYUI_PROVIDER, help="Inference provider key.")
    parser.add_argument("--labels", default="", help="Comma-separated account labels to target.")
    parser.add_argument("--limit", type=int, default=0, help="Optional max account count to process.")
    parser.add_argument("--character-workflow", default="", help="Optional override path for the character workflow JSON.")
    parser.add_argument("--entity-workflow", default="", help="Optional override path for the entity workflow JSON.")
    parser.add_argument("--output", default="", help="Optional path for the JSON summary report.")
    args = parser.parse_args()

    requested_labels = {label.strip().lower() for label in str(args.labels or "").split(",") if label.strip()}
    summary = sync_modal_comfyui_workflows(
        labels=requested_labels,
        limit=max(0, int(args.limit or 0)),
        character_workflow=Path(str(args.character_workflow)).resolve() if str(args.character_workflow or "").strip() else None,
        entity_workflow=Path(str(args.entity_workflow)).resolve() if str(args.entity_workflow or "").strip() else None,
    )
    output_path = Path(args.output) if str(args.output or "").strip() else PROJECT_ROOT / "analysis_outputs" / "provider_smoke_direct" / f"modal_comfyui_workflow_sync_{utc_timestamp()}.json"
    write_summary(output_path, summary)
    for row in summary.get("results", []):
        print(f"{row.get('account_label')}: {row.get('status')}", flush=True)
    print(output_path.resolve())


if __name__ == "__main__":
    main()
