#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys


def account_env(label: str) -> dict[str, str]:
    raw = str(os.environ.get("SAGA_MODAL_TOKENS_JSON") or "").strip()
    if not raw:
        raise SystemExit("SAGA_MODAL_TOKENS_JSON is not configured")
    payload = json.loads(raw)
    rows = payload.get("accounts") or payload.get("tokens") or payload.get("roster") or [] if isinstance(payload, dict) else payload
    for index, row in enumerate(rows or [], start=1):
        if not isinstance(row, dict):
            continue
        row_label = str(row.get("label") or row.get("name") or row.get("account") or f"modal-{index:02d}").strip()
        if row_label != label:
            continue
        token_id = str(row.get("token_id") or "").strip()
        token_secret = str(row.get("token_secret") or "").strip()
        combined = str(row.get("api_key") or row.get("token") or "").strip()
        if (not token_id or not token_secret) and "." in combined:
            token_id, token_secret = combined.split(".", 1)
        if not token_id or not token_secret:
            raise SystemExit(f"Modal account {label} is missing credentials")
        env = dict(os.environ)
        env["MODAL_TOKEN_ID"] = token_id
        env["MODAL_TOKEN_SECRET"] = token_secret
        env.setdefault("SAGA_MODAL_WORKER_VOLUME", "saga-qwen-image-edit-2511-cache")
        return env
    raise SystemExit(f"Modal account {label} was not found in SAGA_MODAL_TOKENS_JSON")


def run_checked(args: list[str], env: dict[str, str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, env=env, text=True, capture_output=True, timeout=timeout)
    if result.returncode != 0:
        detail = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
        raise SystemExit(f"Command failed ({' '.join(args)}):\n{detail[-12000:]}")
    return result


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: qwen_civitai_prefetch.py <modal-account-label>")
    account = sys.argv[1]
    if not str(os.environ.get("CIVITAI_API_TOKEN") or "").strip():
        raise SystemExit("CIVITAI_API_TOKEN is not configured")
    env = account_env(account)

    run_checked(
        ["modal", "deploy", "integrations/qwen/qwen_civitai_prefetch.py"],
        env,
        timeout=600,
    )
    code = (
        "import json, modal; "
        "fn=modal.Function.from_name('saga-qwen-civitai-prefetch', 'stage_qwen_civitai_checkpoint'); "
        "result=fn.remote(False); "
        "print(json.dumps(result, sort_keys=True))"
    )
    result = run_checked([sys.executable, "-c", code], env, timeout=7200)
    print(result.stdout.strip())


if __name__ == "__main__":
    main()
