from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

WORKER_APP = "saga-phase2-analysis-worker"
PROVIDER_APP = "saga-phase2-xcore-provider"
SMOKE_OUTPUT = Path("phase2-worker-live-smoke.txt")


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"missing required configuration: {name}")
    return value


def token_roster() -> list[dict[str, Any]]:
    payload = json.loads(required("SAGA_MODAL_TOKENS_JSON"))
    rows = payload.get("accounts") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise SystemExit("Modal token roster is invalid")
    return [row for row in rows if isinstance(row, dict)]


def modal_env(label: str) -> dict[str, str]:
    account = next(
        (
            row
            for row in token_roster()
            if str(row.get("label") or row.get("name") or row.get("account")) == label
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


def stop_compromised_apps() -> None:
    compromised = os.environ.get("SAGA_COMPROMISED_MODAL_ACCOUNT", "").strip()
    selected = required("MODAL_ACCOUNT")
    if not compromised or compromised == selected:
        return
    try:
        env = modal_env(compromised)
    except SystemExit:
        return
    for app_name in (WORKER_APP, PROVIDER_APP):
        subprocess.run(
            ["modal", "app", "stop", "--yes", app_name],
            env=env,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )


def main() -> None:
    selected = required("MODAL_ACCOUNT")
    env = modal_env(selected)

    # Reduce the blast radius of the credential pair that was surfaced in an
    # earlier diagnostic log. The token itself must still be revoked by the
    # workspace owner because Modal does not expose API-token deletion via CLI.
    stop_compromised_apps()

    subprocess.run(
        ["modal", "deploy", "ops/phase2/analysis_worker_modal.py"],
        env=env,
        check=True,
        timeout=900,
    )
    result = subprocess.run(
        ["modal", "run", "ops/phase2/analysis_worker_modal.py::run_once"],
        env=env,
        text=True,
        capture_output=True,
        timeout=1200,
        check=False,
    )
    combined = "\n".join(
        part for part in ((result.stdout or "").strip(), (result.stderr or "").strip()) if part
    )
    SMOKE_OUTPUT.write_text(combined + ("\n" if combined else ""), encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"live worker smoke failed with exit code {result.returncode}: {combined[-8000:]}")
    required_markers = ("source_ingestion_iteration", "character_identity_iteration")
    missing = [marker for marker in required_markers if marker not in combined]
    if missing:
        raise RuntimeError(f"live worker smoke omitted required markers: {', '.join(missing)}")
    print(
        json.dumps(
            {
                "ok": True,
                "modalAccount": selected,
                "workerApp": WORKER_APP,
                "requiredMarkers": list(required_markers),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
