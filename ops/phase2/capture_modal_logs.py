from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"missing required configuration: {name}")
    return value


def modal_env(label: str) -> dict[str, str]:
    payload = json.loads(required("SAGA_MODAL_TOKENS_JSON"))
    rows = payload.get("accounts") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise SystemExit("Modal token roster is invalid")
    account = next(
        (
            row
            for row in rows
            if isinstance(row, dict)
            and str(row.get("label") or row.get("name") or row.get("account")) == label
        ),
        None,
    )
    if not account:
        raise SystemExit(f"Modal account {label} is unavailable")
    token_id = str(account.get("token_id") or "").strip()
    token_secret = str(account.get("token_secret") or "").strip()
    if not token_id or not token_secret:
        raise SystemExit(f"Modal account {label} has no usable token pair")
    env = dict(os.environ)
    env["MODAL_TOKEN_ID"] = token_id
    env["MODAL_TOKEN_SECRET"] = token_secret
    return env


def main() -> None:
    label = required("MODAL_ACCOUNT")
    app_name = required("MODAL_APP_NAME")
    timeout_seconds = int(os.environ.get("LOG_TIMEOUT_SECONDS", "25"))
    env = modal_env(label)
    try:
        result = subprocess.run(
            ["modal", "app", "logs", app_name, "--timestamps"],
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
        if output:
            print(output[-20000:])
        if result.returncode not in (0,):
            raise SystemExit(result.returncode)
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout.decode() if isinstance(error.stdout, bytes) else (error.stdout or "")
        stderr = error.stderr.decode() if isinstance(error.stderr, bytes) else (error.stderr or "")
        output = "\n".join(part for part in (stdout, stderr) if part).strip()
        if output:
            print(output[-20000:])
        # `modal app logs` follows the stream; timeout is the normal bounded exit.
        return


if __name__ == "__main__":
    main()
