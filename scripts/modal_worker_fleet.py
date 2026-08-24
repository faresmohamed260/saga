#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CREDIT_WORDS = (
    "credit",
    "credits",
    "quota",
    "budget",
    "payment required",
    "insufficient funds",
    "insufficient balance",
    "spending limit",
    "spend limit",
    "workspace budget",
    "out of funds",
)
DISABLED_WORDS = ("workspace is disabled", "workspace disabled", "disabled workspace")


@dataclass(frozen=True)
class Account:
    label: str
    token_id: str
    token_secret: str


def load_accounts() -> list[Account]:
    raw = os.environ.get("SAGA_MODAL_TOKENS_JSON", "").strip()
    if not raw:
        raise SystemExit("SAGA_MODAL_TOKENS_JSON is not configured")
    payload = json.loads(raw)
    if isinstance(payload, dict):
        rows = payload.get("accounts") or payload.get("tokens") or payload.get("roster") or []
    else:
        rows = payload
    if not isinstance(rows, list):
        raise SystemExit("Modal roster must be a list")
    accounts: list[Account] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or row.get("name") or row.get("account") or f"modal-{index:02d}").strip()
        token_id = str(row.get("token_id") or "").strip()
        token_secret = str(row.get("token_secret") or "").strip()
        combined = str(row.get("api_key") or row.get("token") or "").strip()
        if (not token_id or not token_secret) and "." in combined:
            token_id, token_secret = combined.split(".", 1)
        if token_id and token_secret:
            accounts.append(Account(label, token_id, token_secret))
    return accounts


def env_for(account: Account, extra: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env["MODAL_TOKEN_ID"] = account.token_id
    env["MODAL_TOKEN_SECRET"] = account.token_secret
    if extra:
        env.update({key: str(value) for key, value in extra.items()})
    return env


def run(
    account: Account,
    args: list[str],
    *,
    check: bool = False,
    extra: dict[str, str] | None = None,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        env=env_for(account, extra),
        text=True,
        capture_output=True,
        check=check,
        timeout=timeout,
    )


def json_command(account: Account, args: list[str], *, timeout: int = 90) -> tuple[Any, str]:
    try:
        result = run(account, args, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        return None, f"command timeout: {' '.join(args)}: {exc}"
    output = (result.stdout or "").strip()
    detail = ((result.stderr or "") + " " + output).strip()
    if result.returncode != 0:
        return None, detail
    try:
        return json.loads(output or "null"), detail
    except json.JSONDecodeError:
        return None, detail


def classify(detail: str) -> str:
    text = str(detail or "").lower()
    if any(word in text for word in DISABLED_WORDS):
        return "disabled"
    if any(word in text for word in CREDIT_WORDS):
        return "credit_exhausted"
    return "error"


def probe_compute(account: Account) -> tuple[bool, str]:
    try:
        result = run(
            account,
            ["modal", "run", "-q", "scripts/modal_account_probe.py"],
            timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        return False, f"compute probe timeout: {exc}"
    detail = ((result.stderr or "") + " " + (result.stdout or "")).strip()
    return result.returncode == 0, detail


def inventory_account(account: Account) -> dict[str, Any]:
    apps, apps_detail = json_command(account, ["modal", "app", "list", "--json"])
    if apps is None:
        return {"account": account.label, "state": classify(apps_detail), "detail": apps_detail[-800:]}

    volumes, volumes_detail = json_command(account, ["modal", "volume", "list", "--json"])
    if volumes is None:
        return {"account": account.label, "state": classify(volumes_detail), "detail": volumes_detail[-800:]}

    dicts, dicts_detail = json_command(account, ["modal", "dict", "list", "--json"])
    if dicts is None:
        return {"account": account.label, "state": classify(dicts_detail), "detail": dicts_detail[-800:]}

    probe_ok, probe_detail = probe_compute(account)
    state = "available" if probe_ok else classify(probe_detail)
    return {
        "account": account.label,
        "state": state,
        "apps": len(apps) if isinstance(apps, list) else None,
        "volumes": len(volumes) if isinstance(volumes, list) else None,
        "dicts": len(dicts) if isinstance(dicts, list) else None,
        "computeProbe": "ok" if probe_ok else "failed",
        "probeDetail": "" if probe_ok else probe_detail[-800:],
    }


def inventory_all(accounts: list[Account], max_workers: int) -> list[dict[str, Any]]:
    if not accounts:
        return []
    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(accounts)))) as pool:
        futures = {pool.submit(inventory_account, account): account.label for account in accounts}
        for future in as_completed(futures):
            label = futures[future]
            try:
                rows.append(future.result())
            except Exception as exc:  # noqa: BLE001
                rows.append({"account": label, "state": "error", "detail": f"inventory exception: {type(exc).__name__}: {exc}"})
    order = {account.label: index for index, account in enumerate(accounts)}
    rows.sort(key=lambda row: order.get(str(row.get("account") or ""), 10**9))
    return rows


def names(rows: Any) -> list[str]:
    if not isinstance(rows, list):
        return []
    result = []
    for row in rows:
        if isinstance(row, dict):
            value = row.get("Name") or row.get("name") or row.get("App Name") or row.get("app_name")
            if value:
                result.append(str(value))
    return result


def reset_account(account: Account) -> None:
    apps, _ = json_command(account, ["modal", "app", "list", "--json"])
    for name in names(apps):
        result = run(account, ["modal", "app", "stop", "-y", name])
        if result.returncode != 0 and "not found" not in (result.stderr or "").lower():
            raise RuntimeError(f"Could not stop app {name}: {(result.stderr or result.stdout)[-500:]}")
    volumes, _ = json_command(account, ["modal", "volume", "list", "--json"])
    for name in names(volumes):
        result = run(account, ["modal", "volume", "delete", "--allow-missing", "-y", name])
        if result.returncode != 0:
            raise RuntimeError(f"Could not delete volume {name}: {(result.stderr or result.stdout)[-500:]}")
    dicts, _ = json_command(account, ["modal", "dict", "list", "--json"])
    for name in names(dicts):
        result = run(account, ["modal", "dict", "delete", "--allow-missing", "-y", name])
        if result.returncode != 0:
            raise RuntimeError(f"Could not delete dict {name}: {(result.stderr or result.stdout)[-500:]}")


def ecosystem_config(ecosystem_id: str) -> dict[str, Any]:
    payload = json.loads((ROOT / "config/modal-worker-ecosystems.json").read_text(encoding="utf-8"))
    for item in payload.get("ecosystems", []):
        if item.get("id") == ecosystem_id:
            return item
    raise SystemExit(f"Unknown ecosystem: {ecosystem_id}")


def deploy(account: Account, ecosystem_id: str, worker_id: str) -> dict[str, Any]:
    ecosystem = ecosystem_config(ecosystem_id)
    extra = {
        "SAGA_MODAL_WORKER_ID": worker_id,
        "SAGA_MODAL_WORKER_STATE_DICT": ecosystem["stateDict"],
        "SAGA_MODAL_WORKER_VOLUME": ecosystem["volume"],
    }
    for entrypoint in (ecosystem["runtimeEntrypoint"], ecosystem["gatewayEntrypoint"]):
        result = run(account, ["modal", "deploy", entrypoint], extra=extra)
        if result.returncode != 0:
            raise RuntimeError(f"Deploy failed for {entrypoint}: {(result.stderr or result.stdout)[-1200:]}")

    prefetch = "prefetch_klein" if ecosystem_id == "flux2-klein-9b" else "prefetch_ltx25"
    prefetch_argument = "False" if ecosystem_id == "flux2-klein-9b" else "True"
    code = (
        "import modal, json; "
        f"fn=modal.Function.from_name({ecosystem['runtimeApp']!r}, {prefetch!r}); "
        f"result=fn.remote({prefetch_argument}); "
        "print(json.dumps({'ready': bool(result.get('ready')), 'model': result.get('model')}))"
    )
    result = run(account, [sys.executable, "-c", code], extra=extra, timeout=7200)
    if result.returncode != 0:
        raise RuntimeError(f"Prefetch failed: {(result.stderr or result.stdout)[-1200:]}")

    url_code = (
        "import modal; "
        f"fn=modal.Function.from_name({ecosystem['gatewayApp']!r}, {ecosystem['gatewayFunction']!r}); "
        "print(fn.get_web_url())"
    )
    url_result = run(account, [sys.executable, "-c", url_code], extra=extra, timeout=120)
    if url_result.returncode != 0:
        raise RuntimeError(f"Could not resolve gateway URL: {(url_result.stderr or url_result.stdout)[-800:]}")
    return {
        "gatewayUrl": (url_result.stdout or "").strip().splitlines()[-1],
        "ecosystem": ecosystem_id,
        "workerId": worker_id,
        "account": account.label,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    inventory = sub.add_parser("inventory")
    inventory.add_argument("--out", default="modal-worker-inventory.json")
    inventory.add_argument("--workers", type=int, default=8)
    reset = sub.add_parser("reset")
    reset.add_argument("account")
    deploy_cmd = sub.add_parser("deploy")
    deploy_cmd.add_argument("account")
    deploy_cmd.add_argument("ecosystem")
    deploy_cmd.add_argument("worker_id")
    args = parser.parse_args()

    accounts = load_accounts()
    by_label = {account.label: account for account in accounts}
    if args.command == "inventory":
        rows = inventory_all(accounts, args.workers)
        Path(args.out).write_text(json.dumps({"count": len(rows), "accounts": rows}, indent=2), encoding="utf-8")
        counts: dict[str, int] = {}
        for row in rows:
            state = str(row.get("state") or "unknown")
            counts[state] = counts.get(state, 0) + 1
        print(json.dumps({"count": len(rows), "states": counts}, sort_keys=True))
        return

    account = by_label.get(args.account)
    if not account:
        raise SystemExit(f"Account not found in roster: {args.account}")
    if args.command == "reset":
        reset_account(account)
        print(json.dumps({"account": account.label, "reset": True}))
        return
    if args.command == "deploy":
        print(json.dumps(deploy(account, args.ecosystem, args.worker_id)))


if __name__ == "__main__":
    main()
