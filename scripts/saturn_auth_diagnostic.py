#!/usr/bin/env python3
"""Diagnose Saturn API-token authentication without ever printing the credential."""

from __future__ import annotations

import base64
import json
import os
import sys
from typing import Any

import requests

BASE_URL = os.environ.get("SATURN_BASE_URL", "https://app.community.saturnenterprise.io").rstrip("/")
TOKEN = os.environ.get("SATURN_TOKEN", "").strip()
OUT = os.environ.get("SATURN_AUTH_OUTPUT", "/tmp/saturn-auth-diagnostic.json")


def jwt_metadata(token: str) -> dict[str, Any]:
    result: dict[str, Any] = {"looks_like_jwt": token.count(".") == 2, "length": len(token)}
    if not result["looks_like_jwt"]:
        return result
    try:
        part = token.split(".")[1]
        part += "=" * (-len(part) % 4)
        payload = json.loads(base64.urlsafe_b64decode(part.encode()).decode())
        # Deliberately omit subject/user/account identifiers.
        result.update({
            "issuer": payload.get("iss"),
            "audience": payload.get("aud"),
            "is_refresh": payload.get("is_refresh"),
            "has_exp": "exp" in payload,
            "has_scope": "scope" in payload,
        })
    except Exception as exc:
        result["decode_error"] = type(exc).__name__
    return result


def request_with_scheme(scheme: str) -> dict[str, Any]:
    try:
        response = requests.get(
            BASE_URL + "/api/info/servers",
            headers={"Authorization": f"{scheme} {TOKEN}"},
            timeout=20,
        )
        body = response.text[:300]
        return {
            "scheme": scheme,
            "status": response.status_code,
            "authenticated": response.status_code not in {401},
            "body_sample": body,
            "saturn_version": response.headers.get("X-Saturn-Version"),
        }
    except Exception as exc:
        return {"scheme": scheme, "status": None, "authenticated": False, "error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    if not TOKEN:
        print("SATURN_TOKEN is missing", file=sys.stderr)
        return 2

    results = [request_with_scheme("token"), request_with_scheme("Bearer")]
    evidence = {
        "base_url": BASE_URL,
        "token_metadata": jwt_metadata(TOKEN),
        "attempts": results,
    }
    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(evidence, handle, indent=2)
        handle.write("\n")
    print(json.dumps(evidence, indent=2))

    documented = results[0]
    bearer = results[1]
    if documented["authenticated"]:
        print("SATURN_AUTH_SCHEME=token")
        return 0
    if bearer["authenticated"]:
        print("SATURN_AUTH_SCHEME=Bearer")
        return 12
    return 11


if __name__ == "__main__":
    raise SystemExit(main())
