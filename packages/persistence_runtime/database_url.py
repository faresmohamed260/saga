"""Database URL resolution helpers for persistence providers."""

from __future__ import annotations

import os
from urllib.parse import quote_plus


def build_database_url_from_env() -> str:
    def _env(*names: str, default: str = "") -> str:
        for name in names:
            value = str(os.getenv(name, "") or "").strip()
            if value:
                return value
        return default

    explicit_url = _env("SAGA_SUPABASE_DB_URL", "SUPABASE_DB_URL", "DATABASE_URL")
    if explicit_url:
        return explicit_url

    host = _env("SAGA_SUPABASE_DB_HOST", "SUPABASE_DB_HOST", default="127.0.0.1")
    # Supavisor exposes transaction pooling on 6543. The session endpoint on
    # 5432 pins one server connection per independently composed runtime pool.
    port = _env("SAGA_SUPABASE_DB_PORT", "SUPABASE_DB_PORT", default="6543")
    database = _env("SAGA_SUPABASE_DB_NAME", "SUPABASE_DB_NAME", default="postgres")
    password = _env("SAGA_SUPABASE_DB_PASSWORD", "SUPABASE_DB_PASSWORD", "POSTGRES_PASSWORD")
    sslmode = _env("SAGA_SUPABASE_DB_SSLMODE", "SUPABASE_DB_SSLMODE", default="disable")

    explicit_user = _env("SAGA_SUPABASE_DB_USER", "SUPABASE_DB_USER")
    tenant_id = _env("SAGA_SUPABASE_POOLER_TENANT_ID", "SUPABASE_POOLER_TENANT_ID", "POOLER_TENANT_ID")

    username = explicit_user
    if not username and tenant_id:
        username = f"postgres.{tenant_id}"

    if not username or not password:
        return ""

    return (
        "postgresql+psycopg://"
        f"{quote_plus(username)}:{quote_plus(password)}@{host}:{port}/{database}?sslmode={sslmode}"
    )
