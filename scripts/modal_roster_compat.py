from __future__ import annotations

import json
import os
import runpy
import sys
from pathlib import Path
from typing import Any


def _normalize_roster_payload(payload: Any) -> list[dict[str, str]]:
    if isinstance(payload, dict):
        raw_accounts = payload.get("accounts")
        if not isinstance(raw_accounts, list):
            return []
    elif isinstance(payload, list):
        raw_accounts = payload
    else:
        return []

    rows: list[dict[str, str]] = []
    for index, item in enumerate(raw_accounts, start=1):
        if not isinstance(item, dict):
            continue

        token_id = str(item.get("token_id") or "").strip()
        token_secret = str(item.get("token_secret") or "").strip()

        # Legacy accounts.local.json stored the Modal token pair as a single
        # '<token_id>.<token_secret>' api_key. Convert that shape in-memory.
        api_key = str(item.get("api_key") or "").strip()
        if (not token_id or not token_secret) and api_key and "." in api_key:
            candidate_id, candidate_secret = api_key.split(".", 1)
            token_id = token_id or candidate_id.strip()
            token_secret = token_secret or candidate_secret.strip()

        # Email/password-only legacy entries are deliberately ignored. The
        # deployment workflow performs non-interactive API authentication only.
        if not token_id or not token_secret:
            continue

        rows.append(
            {
                "label": str(item.get("label") or item.get("name") or f"member-{index:02d}").strip(),
                "token_id": token_id,
                "token_secret": token_secret,
                "app_name_override": str(item.get("app_name_override") or "").strip(),
            }
        )
    return rows


def normalize_environment() -> int:
    raw = str(os.environ.get("SAGA_MODAL_TOKENS_JSON") or "").strip()
    if not raw:
        return 0
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"SAGA_MODAL_TOKENS_JSON is not valid JSON: {exc}") from exc

    rows = _normalize_roster_payload(payload)
    if not rows:
        raise SystemExit(
            "SAGA_MODAL_TOKENS_JSON did not contain any usable Modal API token pairs. "
            "Supported shapes are [{token_id, token_secret, ...}] or legacy "
            "{accounts: [{api_key: '<token_id>.<token_secret>', ...}]} payloads."
        )

    # Keep credentials only in process memory/environment. Never print them and
    # never write a normalized credential file to disk.
    os.environ["SAGA_MODAL_TOKENS_JSON"] = json.dumps(rows, separators=(",", ":"))
    return len(rows)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/modal_roster_compat.py <target-script>")

    count = normalize_environment()
    target = Path(sys.argv[1]).resolve()
    if not target.is_file():
        raise SystemExit(f"Target script not found: {target}")

    if count:
        print(f"Normalized {count} non-interactive Modal roster credential(s).")
    runpy.run_path(str(target), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
