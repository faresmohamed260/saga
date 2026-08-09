from __future__ import annotations

from typing import Any

from saga.storage.persistence import SagaRelationalStore


class JobStore:
    """Job and pipeline persistence adapter over the canonical relational store."""

    def __init__(self, relational_store: SagaRelationalStore | None = None) -> None:
        self.relational_store = relational_store or SagaRelationalStore()
        self.session_factory = self.relational_store.session_factory

    def upsert_pipeline_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.relational_store.upsert_pipeline_run(payload)

    def get_pipeline_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.relational_store.get_pipeline_runs(limit=limit)

    def get_latest_pipeline_run(self, *, series_id: str) -> dict[str, Any] | None:
        return self.relational_store.get_latest_pipeline_run(series_id=series_id)

    def upsert_dashboard_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.relational_store.upsert_dashboard_job(payload)

    def get_dashboard_jobs(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.relational_store.get_dashboard_jobs(limit=limit)

    def get_dashboard_job(self, job_id: str) -> dict[str, Any] | None:
        return self.relational_store.get_dashboard_job(job_id)

    def append_dashboard_job_log(self, job_id: str, text: str, *, level: str | None = None) -> None:
        self.relational_store.append_dashboard_job_log(job_id, text, level=level)

    def get_dashboard_job_log_tail(self, job_id: str, limit: int = 120) -> list[str]:
        return self.relational_store.get_dashboard_job_log_tail(job_id, limit=limit)

    def delete_series_run(self, *, series_id: str, run_id: str | None = None) -> dict[str, Any]:
        return self.relational_store.delete_series_run(series_id=series_id, run_id=run_id)

    def delete_dashboard_job(self, job_id: str) -> bool:
        return self.relational_store.delete_dashboard_job(job_id)


SQLiteJobStore = JobStore
