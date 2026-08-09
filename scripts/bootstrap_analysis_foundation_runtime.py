from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from packages.modal_runtime import clear_modal_provider_config_cache, save_modal_provider_secret_config


def _load_accounts(path: str) -> list[dict[str, str]]:
    if not str(path or "").strip():
        return []
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("accounts json must be a list of account objects")
    results: list[dict[str, str]] = []
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            continue
        results.append(
            {
                "label": str(item.get("label") or item.get("name") or f"member-{index:02d}").strip(),
                "token_id": str(item.get("token_id") or "").strip(),
                "token_secret": str(item.get("token_secret") or "").strip(),
                "app_name_override": str(item.get("app_name_override") or "").strip(),
            }
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap the active Modal-backed provider config for analysis foundation.")
    parser.add_argument("--provider-name", default="modal_xcore_litbank")
    parser.add_argument("--app-name", default="saga-coref-runtime")
    parser.add_argument("--accounts-json", default="")
    parser.add_argument("--api-url", default="")
    parser.add_argument("--health-url", default="")
    parser.add_argument("--ui-url", default="")
    parser.add_argument("--hf-token", default="")
    parser.add_argument("--request-timeout-seconds", type=int, default=300)
    args = parser.parse_args()

    payload = {
        "app_name": str(args.app_name or "").strip(),
        "api_url": str(args.api_url or "").strip(),
        "health_url": str(args.health_url or "").strip(),
        "ui_url": str(args.ui_url or "").strip(),
        "hf_token": str(args.hf_token or "").strip(),
        "request_timeout_seconds": max(30, int(args.request_timeout_seconds or 300)),
    }
    accounts = _load_accounts(str(args.accounts_json or "").strip())
    if accounts:
        payload["accounts"] = accounts
    summary = save_modal_provider_secret_config(str(args.provider_name or "").strip(), payload)
    clear_modal_provider_config_cache()
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
