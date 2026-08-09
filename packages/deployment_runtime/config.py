"""Environment composition for deployment commands and process roles."""

from __future__ import annotations

import os

from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client


def create_deployment_persistence_client(*, initialize: bool = True):
    profile = PersistenceProfile(
        name="deployment-runtime", provider=str(os.getenv("SAGA_RUNTIME_DB_PROVIDER") or "supabase"),
        mode=str(os.getenv("SAGA_RUNTIME_DB_MODE") or "supabase_postgres"),
        database_url=str(os.getenv("SAGA_RUNTIME_DB_URL") or ""), application_name="saga-deployment-runtime",
        local_storage_root_dir=str(os.getenv("SAGA_RUNTIME_LOCAL_STORAGE_ROOT") or "analysis_outputs/unified_storage"),
    )
    client = create_persistence_client(profile=profile, config=PersistenceRuntimeConfig(
        profile=profile, supabase_api_url=str(os.getenv("SAGA_SUPABASE_URL") or os.getenv("SAGA_SUPABASE_API_URL") or ""),
        supabase_anon_key=str(os.getenv("SAGA_SUPABASE_ANON_KEY") or ""),
        supabase_service_role_key=str(os.getenv("SAGA_SUPABASE_SERVICE_ROLE_KEY") or ""),
    ))
    if initialize:
        client.initialize()
    return client
