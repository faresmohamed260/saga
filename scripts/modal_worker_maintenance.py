#!/usr/bin/env python3
from __future__ import annotations

# Touchpoint for cache-preserving LTX runtime redeploys, including GPU/capacity changes.
import argparse
import json
import sys

from modal_worker_fleet import ecosystem_config, load_accounts, run


def deploy_only(account, ecosystem_id: str, worker_id: str) -> dict[str, str]:
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
        "prefetch": "skipped",
        "cache": "preserved",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Redeploy a Modal worker without resetting volumes or prefetching models.")
    parser.add_argument("account")
    parser.add_argument("ecosystem")
    parser.add_argument("worker_id")
    args = parser.parse_args()

    accounts = {account.label: account for account in load_accounts()}
    account = accounts.get(args.account)
    if not account:
        raise SystemExit(f"Account not found in roster: {args.account}")
    print(json.dumps(deploy_only(account, args.ecosystem, args.worker_id)))


if __name__ == "__main__":
    main()
