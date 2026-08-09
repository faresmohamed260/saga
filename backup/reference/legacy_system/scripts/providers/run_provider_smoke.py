"""CLI entrypoint for direct inference-provider smoke tests.

This script lives under ``scripts/providers`` so provider-level operational
checks sit next to the rest of the provider integration layer rather than in
the top-level scripts bucket.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from saga.providers.inference_smoke import run_provider_smoke


def _print_json(payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(text.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a direct provider-level smoke test.")
    parser.add_argument("--capability", required=True, choices=["speech", "image", "coref"])
    parser.add_argument("--provider", default="", help="Optional explicit provider key.")
    parser.add_argument("--output-root", default="", help="Optional output root for smoke artifacts.")
    parser.add_argument("--image-manifest", default="", help="Optional manifest.json path for multi-image smoke input.")
    parser.add_argument("--deploy-first", action="store_true", help="Redeploy the selected Modal image provider account before the smoke run.")
    parser.add_argument("--account-label", default="", help="Optional Modal account label to target for deploy-first image smoke.")
    args = parser.parse_args()

    payload = run_provider_smoke(
        capability=args.capability,
        provider_name=str(args.provider or "").strip() or None,
        output_root=str(args.output_root or "").strip() or None,
        image_manifest_path=str(args.image_manifest or "").strip() or None,
        deploy_first=bool(args.deploy_first),
        account_label=str(args.account_label or "").strip() or None,
    )
    _print_json(payload)


if __name__ == "__main__":
    main()
