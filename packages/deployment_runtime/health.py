"""Liveness and dependency-aware readiness checks."""

from __future__ import annotations

import time
from collections.abc import Callable

from sqlalchemy import text

from packages.deployment_runtime.contracts import DependencyStatus, ReadinessReport
from packages.persistence_runtime import SchemaNotReadyError, validate_production_schema


def check_readiness(*, persistence, service: str, release_id: str = "", extra_probes: dict[str, Callable[[], None]] | None = None) -> ReadinessReport:
    dependencies: list[DependencyStatus] = []
    revision = ""
    started = time.perf_counter()
    try:
        with persistence.engine.connect() as connection:
            connection.execute(text("select 1"))
        if str(persistence.profile.mode) == "test_harness":
            revision = "test_harness"
        else:
            schema = validate_production_schema(persistence.engine, vector_table_name=persistence.profile.vector_table_name)
            revision = str(schema["revision"])
        dependencies.append(DependencyStatus(name="supabase_postgres", status="ready", latency_ms=_elapsed_ms(started)))
    except (SchemaNotReadyError, Exception) as exc:
        dependencies.append(DependencyStatus(name="supabase_postgres", status="unavailable", latency_ms=_elapsed_ms(started), detail=f"{type(exc).__name__}: {str(exc)[:240]}"))
    for name, probe in dict(extra_probes or {}).items():
        probe_started = time.perf_counter()
        try:
            probe()
            dependencies.append(DependencyStatus(name=name, status="ready", latency_ms=_elapsed_ms(probe_started)))
        except Exception as exc:
            dependencies.append(DependencyStatus(name=name, status="degraded", latency_ms=_elapsed_ms(probe_started), detail=f"{type(exc).__name__}: {str(exc)[:240]}"))
    return ReadinessReport(ready=all(item.status == "ready" for item in dependencies), service=service, release_id=release_id, schema_revision=revision, dependencies=dependencies)


def _elapsed_ms(started: float) -> int:
    return max(0, round((time.perf_counter() - started) * 1000))
