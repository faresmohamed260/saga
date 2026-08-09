"""Fail-fast production schema validation owned by deployment migrations."""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


EXPECTED_SCHEMA_REVISION = "202608090400"
REQUIRED_TABLES = frozenset({
    "provider_configs", "provider_statuses", "library_series", "library_books", "library_scenes", "library_records",
    "identity_series", "jobs", "job_logs", "generated_stories", "audiobook_runs", "audiobook_chapters",
    "execution_queue_policies", "execution_queue", "execution_telemetry", "stage_lineage_records",
    "observability_records", "agent_runtime_checkpoints", "agent_runtime_checkpoint_blobs",
    "usage_ledger", "usage_budget_policies",
    "agent_runtime_checkpoint_writes", "deployment_releases", "deployment_release_gate_evidence",
    "deployment_process_heartbeats",
})


class SchemaNotReadyError(RuntimeError):
    pass


def validate_production_schema(engine: Engine, *, vector_table_name: str = "vector_documents", require_revision: bool = True) -> dict[str, object]:
    inspector = inspect(engine)
    schema = "public" if engine.dialect.name == "postgresql" else None
    required = set(REQUIRED_TABLES) | {str(vector_table_name or "vector_documents")}
    existing = set(inspector.get_table_names(schema=schema))
    missing = sorted(required - existing)
    revision = ""
    if "alembic_version" in existing:
        with engine.connect() as connection:
            revision = str(connection.execute(text("select version_num from public.alembic_version limit 1") if schema else text("select version_num from alembic_version limit 1")).scalar() or "")
    errors = []
    if missing:
        errors.append(f"missing tables: {', '.join(missing)}")
    if not missing:
        from packages.persistence_runtime.schema import Base
        expected_columns = {table.name: set(table.columns.keys()) for table in Base.metadata.sorted_tables}
        expected_columns.update({
            "agent_runtime_checkpoints": {"thread_id", "checkpoint_ns", "checkpoint_id", "parent_checkpoint_id", "checkpoint_type", "checkpoint_bytes", "metadata_type", "metadata_bytes", "metadata_json", "created_at"},
            "agent_runtime_checkpoint_blobs": {"thread_id", "checkpoint_ns", "channel", "version", "blob_type", "blob_bytes"},
            "agent_runtime_checkpoint_writes": {"thread_id", "checkpoint_ns", "checkpoint_id", "task_id", "write_idx", "channel", "value_type", "value_bytes", "task_path"},
            str(vector_table_name or "vector_documents"): {"id", "namespace", "document_id", "content", "summary", "metadata", "embedding", "updated_at"},
        })
        column_errors = []
        for table_name, columns in expected_columns.items():
            if table_name == str(vector_table_name or "vector_documents") and engine.dialect.name == "postgresql":
                with engine.connect() as connection:
                    actual = set(connection.execute(text("select column_name from information_schema.columns where table_schema='public' and table_name=:table"), {"table": table_name}).scalars())
            else:
                actual = {item["name"] for item in inspector.get_columns(table_name, schema=schema)}
            missing_columns = sorted(columns - actual)
            if missing_columns:
                column_errors.append(f"{table_name}({', '.join(missing_columns)})")
        if column_errors:
            errors.append("missing columns: " + "; ".join(column_errors))
    if require_revision and revision != EXPECTED_SCHEMA_REVISION:
        errors.append(f"schema revision is '{revision or 'unversioned'}', expected '{EXPECTED_SCHEMA_REVISION}'")
    if errors:
        raise SchemaNotReadyError("Production schema is not ready; run `saga-deploy migrate upgrade`. " + "; ".join(errors))
    return {"ready": True, "revision": revision, "table_count": len(existing), "required_table_count": len(required)}
