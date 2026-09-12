from __future__ import annotations

import base64
import json
import os
import secrets
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

B2_AUTHORIZE_URL = "https://api.backblazeb2.com/b2api/v4/b2_authorize_account"
B2_KEY_NAME = "saga-phase2-worker-modal"
B2_NAME_PREFIX = "sources/"
MODAL_PROVIDER_SECRET = "saga-phase2-xcore-provider"
MODAL_WORKER_SECRET = "saga-phase2-analysis-worker-runtime"


def required(name: str) -> str:
    value = os.environ.get(name, "")
    if not value.strip():
        raise SystemExit(f"missing required configuration: {name}")
    return value


def normalized_secret(name: str) -> str:
    # The existing Backblaze bootstrap proved these repository secrets may
    # contain line-ending/whitespace noise. Never alter interior key material.
    value = required(name).replace("\r", "").replace("\n", "").strip()
    if not value:
        raise SystemExit(f"empty normalized secret: {name}")
    return value


def json_request(
    url: str,
    *,
    token: str | None = None,
    body: dict[str, Any] | None = None,
    basic: tuple[str, str] | None = None,
) -> dict[str, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = token
    if basic:
        encoded = base64.b64encode(f"{basic[0]}:{basic[1]}".encode()).decode()
        headers["Authorization"] = f"Basic {encoded}"
    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method="POST" if data is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:2000]
        raise RuntimeError(f"HTTP {error.code} from {url}: {detail}") from None
    if not isinstance(payload, dict):
        raise RuntimeError(f"unexpected JSON response from {url}")
    return payload


def modal_account_env() -> dict[str, str]:
    roster = json.loads(required("SAGA_MODAL_TOKENS_JSON"))
    rows = roster.get("accounts") if isinstance(roster, dict) else roster
    if not isinstance(rows, list):
        raise SystemExit("Modal token roster is invalid")
    label = required("MODAL_ACCOUNT").strip()
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


def create_modal_secret(name: str, payload: dict[str, str], env: dict[str, str]) -> None:
    path = Path(tempfile.mkstemp(prefix="saga-modal-secret-", suffix=".json")[1])
    try:
        path.write_text(json.dumps(payload), encoding="utf-8")
        path.chmod(0o600)
        subprocess.run(
            ["modal", "secret", "create", "--force", "--from-json", str(path), name],
            env=env,
            check=True,
        )
    finally:
        path.unlink(missing_ok=True)


def main() -> None:
    b2_key_id = normalized_secret("SAGA_B2_KEY_ID")
    b2_master_key = normalized_secret("SAGA_B2_MASTER_APPLICATION_KEY")
    service_role = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.environ.get("SUPABASE_SECRET_KEY", "").strip()
    )
    if not service_role:
        raise SystemExit("missing Supabase privileged server credential")

    bucket_id = required("SAGA_B2_BUCKET_ID").strip()
    auth = json_request(B2_AUTHORIZE_URL, basic=(b2_key_id, b2_master_key))
    account_id = str(auth["accountId"])
    storage_api = auth["apiInfo"]["storageApi"]
    api_url = str(storage_api["apiUrl"]).rstrip("/")
    auth_token = str(auth["authorizationToken"])

    listed = json_request(
        f"{api_url}/b2api/v4/b2_list_keys",
        token=auth_token,
        body={"accountId": account_id, "maxKeyCount": 1000},
    )
    for row in listed.get("keys", []):
        if isinstance(row, dict) and row.get("keyName") == B2_KEY_NAME:
            json_request(
                f"{api_url}/b2api/v4/b2_delete_key",
                token=auth_token,
                body={"applicationKeyId": row["applicationKeyId"]},
            )

    created = json_request(
        f"{api_url}/b2api/v4/b2_create_key",
        token=auth_token,
        body={
            "accountId": account_id,
            "capabilities": ["listAllBucketNames", "listFiles", "readFiles"],
            "keyName": B2_KEY_NAME,
            "bucketIds": [bucket_id],
            "namePrefix": B2_NAME_PREFIX,
        },
    )
    scoped_id = str(created["applicationKeyId"])
    scoped_key = str(created["applicationKey"])

    scoped_auth = json_request(B2_AUTHORIZE_URL, basic=(scoped_id, scoped_key))
    allowed = scoped_auth["apiInfo"]["storageApi"].get("allowed") or {}
    buckets = allowed.get("buckets") or []
    bucket_ids = {
        str(row.get("id")) for row in buckets if isinstance(row, dict) and row.get("id")
    }
    if bucket_ids != {bucket_id}:
        raise SystemExit("scoped B2 key bucket restriction mismatch")
    if allowed.get("namePrefix") != B2_NAME_PREFIX:
        raise SystemExit("scoped B2 key prefix restriction mismatch")
    capabilities = {str(value) for value in allowed.get("capabilities") or []}
    if not {"listFiles", "readFiles"}.issubset(capabilities):
        raise SystemExit("scoped B2 key capabilities mismatch")

    modal_env = modal_account_env()
    bearer = secrets.token_urlsafe(48)
    create_modal_secret(
        MODAL_PROVIDER_SECRET,
        {"SAGA_IDENTITY_PROVIDER_TOKEN": bearer},
        modal_env,
    )

    modal_env["SAGA_XCORE_MODEL_REVISION"] = required("SAGA_XCORE_MODEL_REVISION").strip()
    subprocess.run(
        ["modal", "deploy", "ops/phase2/xcore_provider.py"],
        env=modal_env,
        check=True,
    )
    url_code = (
        "import modal; "
        "fn=modal.Function.from_name('saga-phase2-xcore-provider','web'); "
        "print(fn.get_web_url())"
    )
    resolved = subprocess.run(
        ["python", "-c", url_code],
        env=modal_env,
        text=True,
        capture_output=True,
        check=True,
    )
    provider_url = resolved.stdout.strip().splitlines()[-1].rstrip("/") + "/"

    worker_payload = {
        "SAGA_SUPABASE_URL": required("SAGA_SUPABASE_URL").strip(),
        "SAGA_SUPABASE_SERVICE_ROLE_KEY": service_role,
        "SAGA_B2_BUCKET": required("SAGA_B2_BUCKET").strip(),
        "SAGA_B2_ENDPOINT": required("SAGA_B2_ENDPOINT").strip(),
        "SAGA_B2_REGION": required("SAGA_B2_REGION").strip(),
        "SAGA_B2_APPLICATION_KEY_ID": scoped_id,
        "SAGA_B2_APPLICATION_KEY": scoped_key,
        "SAGA_IDENTITY_PROVIDER_URL": provider_url,
        "SAGA_IDENTITY_PROVIDER_NAME": required("SAGA_IDENTITY_PROVIDER_NAME").strip(),
        "SAGA_IDENTITY_PROVIDER_MODEL": required("SAGA_IDENTITY_PROVIDER_MODEL").strip(),
        "SAGA_IDENTITY_PROVIDER_REVISION": required("SAGA_IDENTITY_PROVIDER_REVISION").strip(),
        "SAGA_IDENTITY_PROVIDER_BEARER_TOKEN": bearer,
    }
    create_modal_secret(MODAL_WORKER_SECRET, worker_payload, modal_env)

    proof = {
        "b2KeyName": B2_KEY_NAME,
        "bucketId": bucket_id,
        "namePrefix": B2_NAME_PREFIX,
        "capabilities": sorted(capabilities),
        "providerUrl": provider_url,
        "providerName": worker_payload["SAGA_IDENTITY_PROVIDER_NAME"],
        "providerModel": worker_payload["SAGA_IDENTITY_PROVIDER_MODEL"],
        "providerRevision": worker_payload["SAGA_IDENTITY_PROVIDER_REVISION"],
        "modalAccount": required("MODAL_ACCOUNT").strip(),
        "approvedAppSha": required("APPROVED_APP_SHA").strip(),
    }
    Path("phase2-worker-provision.json").write_text(
        json.dumps(proof, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": True, **proof}, sort_keys=True))


if __name__ == "__main__":
    main()
