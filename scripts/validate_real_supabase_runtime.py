from __future__ import annotations

import json
import os
import sys
import time
from uuid import uuid4

from packages.persistence_runtime import PersistenceProfile, PersistenceRuntimeConfig, create_persistence_client


def _require_env(name: str) -> str:
    value = str(os.getenv(name, "") or "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def run_validation() -> dict[str, object]:
    _require_env("SAGA_SUPABASE_DB_URL")
    _require_env("SAGA_SUPABASE_SERVICE_ROLE_KEY")
    _require_env("SAGA_SUPABASE_API_URL")

    run_suffix = uuid4().hex[:10]
    provider_name = f"runtime-validation-{run_suffix}"
    namespace = f"runtime-validation.{run_suffix}"
    bucket_name = f"runtime-validation-{run_suffix}"
    object_path = f"health/{run_suffix}/note.txt"
    report_filename = f"report-{run_suffix}.json"

    profile = PersistenceProfile(
        name="real-supabase-validation",
        provider="supabase",
        mode="supabase_postgres",
        application_name="saga-real-supabase-validation",
    )
    client = create_persistence_client(
        config=PersistenceRuntimeConfig(profile=profile),
        profile=profile,
    )
    client.initialize()

    started_at = int(time.time())

    config_row = client.provider_configs.upsert_provider_config(
        provider_name,
        {"runtime_state": {"active_token_name": "member-01", "active_api_url": "https://image.example/api"}},
    )
    status_row = client.provider_configs.upsert_provider_status(
        provider_name,
        "member-01",
        {
            "last_health_ok": True,
            "last_request_ok": True,
            "api_url": "https://image.example/api",
            "app_name": "real-supabase-validation",
        },
    )
    operational = client.provider_configs.get_provider_operational_state(provider_name)

    vector_upsert = client.vectors.upsert_documents(
        namespace,
        [
            {
                "document_id": f"doc-{run_suffix}",
                "content": "Victor Frankenstein creates the creature from assembled body parts.",
                "summary": "Victor Frankenstein creates the creature.",
                "metadata": {"characters": ["Victor Frankenstein", "Creature"], "chapter": 1},
                "embedding": [0.91, 0.04, 0.12, 0.33],
            }
        ],
    )
    vector_results = client.vectors.query_documents(
        namespace,
        query_vector=[0.9, 0.03, 0.1, 0.31],
        top_k=1,
        metadata_filters={"chapter": 1},
    )

    ensured = client.objects.ensure_bucket(bucket_name, public=False)
    uploaded = client.objects.upload_text(
        bucket_name,
        object_path,
        "real supabase runtime validation",
        content_type="text/plain; charset=utf-8",
    )
    downloaded = client.objects.download_text(bucket_name, object_path)

    artifact = client.artifacts.store_json(
        artifact_type="runtime_report",
        filename=report_filename,
        payload={"ok": True, "provider": provider_name, "validated_at": started_at},
        provider_name=provider_name,
        report_kind="real-supabase-validation",
        metadata={"validation_run": run_suffix},
    )

    delete_object = client.objects.delete_object(bucket_name, object_path)
    delete_vectors = client.vectors.delete_documents(namespace, [f"doc-{run_suffix}"])

    return {
        "provider_config_provider": config_row["provider_name"],
        "provider_status_label": status_row["label"],
        "operational_ready_labels": operational["ready_labels"],
        "operational_diagnostics": operational["runtime_state"]["diagnostics"],
        "vector_document_count": vector_upsert["document_count"],
        "vector_top_result": vector_results[0]["document_id"] if vector_results else "",
        "bucket_name": ensured["bucket_name"],
        "object_bytes_written": uploaded["bytes_written"],
        "downloaded_text": downloaded,
        "artifact_bucket": artifact["bucket_name"],
        "artifact_object_path": artifact["object_path"],
        "object_delete_message": str(delete_object.get("message") or ""),
        "object_deleted": bool(delete_object.get("deleted")) or "Successfully deleted" in str(delete_object.get("message") or ""),
        "vectors_deleted": delete_vectors["deleted_count"],
    }


def main() -> int:
    result = run_validation()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REAL_SUPABASE_VALIDATION_FAILED: {exc}", file=sys.stderr)
        raise
