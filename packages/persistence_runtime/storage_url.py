"""Supabase Storage endpoint resolution helpers."""

from __future__ import annotations

import os


def build_storage_api_url_from_env() -> str:
    candidates = [
        os.getenv("SAGA_SUPABASE_STORAGE_API_URL", ""),
        os.getenv("SUPABASE_STORAGE_API_URL", ""),
    ]
    for candidate in candidates:
        value = str(candidate or "").strip().rstrip("/")
        if value:
            return value

    base_candidates = [
        os.getenv("SAGA_SUPABASE_API_URL", ""),
        os.getenv("SUPABASE_API_URL", ""),
        os.getenv("SUPABASE_PUBLIC_URL", ""),
    ]
    for candidate in base_candidates:
        value = str(candidate or "").strip().rstrip("/")
        if value:
            if value.endswith("/storage/v1"):
                return value
            return f"{value}/storage/v1"
    return ""


def resolve_supabase_service_role_key(*, explicit: str = "") -> str:
    candidates = [
        explicit,
        os.getenv("SAGA_SUPABASE_SERVICE_ROLE_KEY", ""),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
        os.getenv("SERVICE_ROLE_KEY", ""),
        os.getenv("SUPABASE_SERVICE_KEY", ""),
    ]
    for candidate in candidates:
        value = str(candidate or "").strip()
        if value:
            return value
    return ""
