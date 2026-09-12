from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

B2_AUTHORIZE_URL = "https://api.backblazeb2.com/b2api/v4/b2_authorize_account"
B2_KEY_NAME = "saga-phase2-worker-modal"
B2_NAME_PREFIX = "sources/"
SUPABASE_WORKER_KEY_NAME = "saga_phase2_analysis_worker"
MODAL_PROVIDER_SECRET = "saga-phase2-xcore-provider"
MODAL_WORKER_SECRET = "saga-phase2-analysis-worker-runtime"


def required(name: str) -> str:
    value = os.environ.get(name, "")
    if not value.strip():
        raise SystemExit(f"missing required configuration: {name}")
    return value


def normalized_secret(name: str) -> str:
    value = required(name).replace("\r", "").replace("\n", "").strip()
    if not value:
        raise SystemExit(f"empty normalized secret: {name}")
    return value


def request_json(
    url: str,
    *,
    method: str | None = None,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    basic: tuple[str, str] | None = None,
    timeout: int = 60,
) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    final_headers = {"Accept": "application/json"}
    if body is not None:
        final_headers["Content-Type"] = "application/json"
    if headers:
        final_headers.update(headers)
    if basic:
        encoded = base64.b64encode(f"{basic[0]}:{basic[1]}".encode()).decode()
        final_headers["Authorization"] = f"Basic {encoded}"
    request = urllib.request.Request(
        url,
        data=data,
        headers=final_headers,
        method=method or ("POST" if data is not None else "GET"),
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:2000]
        raise RuntimeError(f"HTTP {error.code} from {url}: {detail}") from None


def b2_request(url: str, *, token: str | None = None, body: dict[str, Any] | None = None, basic: tuple[str, str] | None = None) -> dict[str, Any]:
    headers = {"Authorization": token} if token else None
    payload = request_json(url, headers=headers, body=body, basic=basic)
    if not isinstance(payload, dict):
        raise RuntimeError(f"unexpected Backblaze response from {url}")
    return payload


def supabase_management_request(path: str, *, method: str = "GET", body: dict[str, Any] | None = None) -> Any:
    token = normalized_secret("SAGA_SUPABASE_ACCESS_TOKEN")
    return request_json(
        f"https://api.supabase.com{path}",
        method=method,
        headers={"Authorization": f"Bearer {token}"},
        body=body,
    )


def extract_api_key(row: dict[str, Any]) -> str | None:
    for field in ("api_key", "apiKey", "key", "value"):
        value = row.get(field)
        if isinstance(value, str) and value.startswith("sb_secret_"):
            return value
    return None


def provision_supabase_worker_key() -> tuple[str, str]:
    project_ref = required("SAGA_SUPABASE_PROJECT_REF").strip()
    encoded_ref = urllib.parse.quote(project_ref, safe="")
    path = f"/v1/projects/{encoded_ref}/api-keys"
    payload = supabase_management_request(path + "?reveal=true")
    rows: list[dict[str, Any]] = []
    if isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, dict)]
    elif isinstance(payload, dict):
        candidate = payload.get("keys") or payload.get("data") or []
        if isinstance(candidate, list):
            rows = [row for row in candidate if isinstance(row, dict)]

    matching = [
        row
        for row in rows
        if row.get("name") == SUPABASE_WORKER_KEY_NAME and row.get("type") == "secret"
    ]
    key_id = ""
    secret_key: str | None = None
    if matching:
        selected = matching[-1]
        key_id = str(selected.get("id") or "")
        secret_key = extract_api_key(selected)
        if not secret_key and key_id:
            detail = supabase_management_request(
                f"{path}/{urllib.parse.quote(key_id, safe='')}?reveal=true"
            )
            if isinstance(detail, dict):
                secret_key = extract_api_key(detail)
    else:
        created = supabase_management_request(
            path + "?reveal=true",
            method="POST",
            body={
                "type": "secret",
                "name": SUPABASE_WORKER_KEY_NAME,
                "secret_jwt_template": {"role": "service_role"},
            },
        )
        if not isinstance(created, dict):
            raise RuntimeError("Supabase API-key creation returned an unexpected response")
        key_id = str(created.get("id") or "")
        secret_key = extract_api_key(created)

    if not secret_key:
        raise RuntimeError("Supabase worker secret key could not be revealed")

    supabase_url = required("SAGA_SUPABASE_URL").strip().rstrip("/")
    validation_url = f"{supabase_url}/rest/v1/saga_analysis_jobs?select=id&limit=1"
    validation = urllib.request.Request(
        validation_url,
        headers={
            "apikey": secret_key,
            "Accept": "application/json",
            "User-Agent": "saga-phase2-provisioner/1.0",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(validation, timeout=60) as response:
            if response.status != 200:
                raise RuntimeError(f"Supabase worker-key validation returned HTTP {response.status}")
            json.loads(response.read() or b"[]")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"Supabase worker-key validation failed with HTTP {error.code}: {detail}") from None

    return secret_key, key_id


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
    descriptor, raw_path = tempfile.mkstemp(prefix="saga-modal-secret-", suffix=".json")
    os.close(descriptor)
    path = Path(raw_path)
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


def verify_provider(provider_url: str, bearer: str) -> tuple[int, int]:
    with urllib.request.urlopen(provider_url + "health", timeout=120) as response:
        health = json.load(response)
    expected_revision = required("SAGA_XCORE_MODEL_REVISION").strip()
    if health.get("ready") is not True or health.get("model_revision") != expected_revision:
        raise RuntimeError(f"provider health mismatch: {health}")

    text = "Alice entered the garden. She greeted Bob. Bob smiled at Alice."
    body = json.dumps(
        {
            "normalizedInputFingerprint": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "normalizedText": text,
            "sections": [
                {
                    "stable_key": "document:0",
                    "ordinal": 0,
                    "section_kind": "document",
                    "title": None,
                    "source_locator": "hosted-proof:worker-provision",
                    "start_offset": 0,
                    "end_offset": len(text),
                    "normalized_text": text,
                }
            ],
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        provider_url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {bearer}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=900) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:4000]
        raise RuntimeError(f"provider smoke HTTP {error.code}: {detail}") from None
    mentions = result.get("mentions") if isinstance(result, dict) else None
    if not isinstance(mentions, list) or not mentions:
        raise RuntimeError("provider smoke returned no mentions")
    strong_names = [
        row
        for row in mentions
        if isinstance(row, dict)
        and row.get("mentionKind") == "proper_name"
        and row.get("entityType") == "person"
        and row.get("personEvidence") == "strong"
    ]
    if not strong_names:
        raise RuntimeError("provider smoke returned no strong PERSON proper-name evidence")
    return len(mentions), len(strong_names)


def main() -> None:
    b2_key_id = normalized_secret("SAGA_B2_KEY_ID")
    b2_master_key = normalized_secret("SAGA_B2_MASTER_APPLICATION_KEY")
    supabase_worker_key, supabase_worker_key_id = provision_supabase_worker_key()

    bucket_id = required("SAGA_B2_BUCKET_ID").strip()
    auth = b2_request(B2_AUTHORIZE_URL, basic=(b2_key_id, b2_master_key))
    account_id = str(auth["accountId"])
    storage_api = auth["apiInfo"]["storageApi"]
    api_url = str(storage_api["apiUrl"]).rstrip("/")
    auth_token = str(auth["authorizationToken"])

    listed = b2_request(
        f"{api_url}/b2api/v4/b2_list_keys",
        token=auth_token,
        body={"accountId": account_id, "maxKeyCount": 1000},
    )
    for row in listed.get("keys", []):
        if isinstance(row, dict) and row.get("keyName") == B2_KEY_NAME:
            b2_request(
                f"{api_url}/b2api/v4/b2_delete_key",
                token=auth_token,
                body={"applicationKeyId": row["applicationKeyId"]},
            )

    created = b2_request(
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

    scoped_auth = b2_request(B2_AUTHORIZE_URL, basic=(scoped_id, scoped_key))
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
    smoke_mentions, strong_names = verify_provider(provider_url, bearer)

    worker_payload = {
        "SAGA_SUPABASE_URL": required("SAGA_SUPABASE_URL").strip(),
        "SAGA_SUPABASE_SERVICE_ROLE_KEY": supabase_worker_key,
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
        "supabaseWorkerKeyName": SUPABASE_WORKER_KEY_NAME,
        "supabaseWorkerKeyId": supabase_worker_key_id,
        "supabaseWorkerKeyValidated": True,
        "b2KeyName": B2_KEY_NAME,
        "bucketId": bucket_id,
        "namePrefix": B2_NAME_PREFIX,
        "capabilities": sorted(capabilities),
        "providerUrl": provider_url,
        "providerName": worker_payload["SAGA_IDENTITY_PROVIDER_NAME"],
        "providerModel": worker_payload["SAGA_IDENTITY_PROVIDER_MODEL"],
        "providerRevision": worker_payload["SAGA_IDENTITY_PROVIDER_REVISION"],
        "providerSmokeMentionCount": smoke_mentions,
        "providerSmokeStrongNameCount": strong_names,
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
