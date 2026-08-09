"""Store implementations for the persistence runtime."""

from __future__ import annotations

import json
import math
import time
import threading
import uuid
from pathlib import Path
from typing import Any

import requests
from sqlalchemy import delete, inspect, select, text
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from packages.persistence_runtime.schema import (
    AudiobookChapterRow,
    AudiobookRunRow,
    ExecutionQueuePolicyRow,
    ExecutionQueueRow,
    ExecutionTelemetryRow,
    ObservabilityRecordRow,
    UsageBudgetPolicyRow,
    UsageLedgerRow,
    DeploymentReleaseGateEvidenceRow,
    DeploymentProcessHeartbeatRow,
    DeploymentReleaseRow,
    IdentitySeriesRow,
    JobLogRow,
    JobRow,
    StageLineageRow,
    LibraryBookRow,
    LibraryRecordRow,
    LibrarySceneRow,
    LibrarySeriesRow,
    ProviderConfigRow,
    ProviderStatusRow,
    StoryRow,
)
from packages.persistence_runtime.schema import utcnow
from packages.persistence_runtime.conventions import validate_vector_document_contract, validate_vector_namespace
from packages.persistence_runtime.contracts import (
    ProviderConfigRecord,
    ProviderOperationalRuntimeState,
    ProviderOperationalStatePayload,
    ProviderStatusRecord,
    ProviderStatusSnapshot,
)


def _json(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict(payload or {})


def _now_ms() -> int:
    return int(time.time() * 1000)


def _required(value: str, field: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field} is required.")
    return normalized


def _capabilities(values: list[str] | None) -> list[str]:
    return sorted({str(value or "").strip() for value in list(values or []) if str(value or "").strip()})


def _queue_policy(payload: dict[str, Any] | None) -> dict[str, Any]:
    raw = dict(payload or {})
    return {
        "global_limit": max(1, int(raw.get("global_limit") or 1)),
        "per_series_limit": max(1, int(raw.get("per_series_limit") or 1)),
        "default_capability_limit": max(1, int(raw.get("default_capability_limit") or raw.get("global_limit") or 1)),
        "capability_limits": {str(key): max(1, int(value)) for key, value in dict(raw.get("capability_limits") or {}).items()},
    }


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{float(value):.12g}" for value in values) + "]"


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def _safe_relative_path(object_path: str) -> Path:
    candidate = Path(str(object_path or "").strip())
    if candidate.is_absolute():
        raise ValueError(f"Absolute object paths are not allowed: {object_path}")
    normalized = Path()
    for part in candidate.parts:
        if not part or part == ".":
            continue
        if part == "..":
            raise ValueError(f"Parent traversal is not allowed: {object_path}")
        normalized = normalized / part
    if not str(normalized):
        raise ValueError("object_path is required")
    return normalized


class ProviderConfigStore:
    def __init__(self, session_factory: sessionmaker) -> None:
        self.session_factory = session_factory

    def upsert_provider_config(self, provider_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.session_factory() as session:
            row = session.get(ProviderConfigRow, provider_name)
            if row is None:
                row = ProviderConfigRow(provider_name=provider_name, payload=_json(payload))
                session.add(row)
            else:
                row.payload = _json(payload)
            session.commit()
            return self._provider_config_dict(row)

    def get_provider_config(self, provider_name: str) -> dict[str, Any] | None:
        with self.session_factory() as session:
            row = session.get(ProviderConfigRow, provider_name)
            return self._provider_config_dict(row) if row else None

    def list_provider_configs(self) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            rows = session.execute(select(ProviderConfigRow).order_by(ProviderConfigRow.provider_name.asc())).scalars().all()
            return [self._provider_config_dict(row) for row in rows]

    def get_provider_operational_state(self, provider_name: str) -> dict[str, Any]:
        normalized_provider_name = self._normalize_provider_name(provider_name)
        config = self.get_provider_config(normalized_provider_name)
        statuses = self.list_provider_statuses(normalized_provider_name)
        runtime_state = self._provider_runtime_state((config or {}).get("payload") if config else {}, statuses)
        healthy_labels = [
            str(item.get("label") or "").strip()
            for item in statuses
            if bool(((item.get("status") or {}).get("last_health_ok")))
        ]
        ready_labels = [
            str(item.get("label") or "").strip()
            for item in statuses
            if bool(((item.get("status") or {}).get("last_request_ok")))
        ]
        error_labels = [
            str(item.get("label") or "").strip()
            for item in statuses
            if str(((item.get("status") or {}).get("last_error") or "")).strip()
        ]
        return ProviderOperationalStatePayload(
            provider_name=normalized_provider_name,
            found=bool(config is not None or statuses),
            config=ProviderConfigRecord.model_validate(config) if config is not None else None,
            runtime_state=runtime_state,
            statuses=[ProviderStatusRecord.model_validate(item) for item in statuses],
            status_count=len(statuses),
            healthy_labels=[label for label in healthy_labels if label],
            ready_labels=[label for label in ready_labels if label],
            error_labels=[label for label in error_labels if label],
        ).model_dump()

    def upsert_provider_status(self, provider_name: str, label: str, payload: dict[str, Any]) -> dict[str, Any]:
        normalized_provider_name = self._normalize_provider_name(provider_name)
        normalized_label = self._normalize_status_label(label)
        with self.session_factory() as session:
            row = session.execute(
                select(ProviderStatusRow).where(
                    ProviderStatusRow.provider_name == normalized_provider_name,
                    ProviderStatusRow.label == normalized_label,
                )
            ).scalar_one_or_none()
            if row is None:
                row = ProviderStatusRow(provider_name=normalized_provider_name, label=normalized_label, payload=_json(payload))
                session.add(row)
            else:
                row.payload = _json(payload)
            session.commit()
            return self._provider_status_dict(row)

    def replace_provider_statuses(self, provider_name: str, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized_provider_name = self._normalize_provider_name(provider_name)
        normalized_payloads = self._normalize_status_payloads(payloads)
        with self.session_factory() as session:
            session.execute(delete(ProviderStatusRow).where(ProviderStatusRow.provider_name == normalized_provider_name))
            rows: list[ProviderStatusRow] = []
            for item in normalized_payloads:
                row = ProviderStatusRow(
                    provider_name=normalized_provider_name,
                    label=str(item.get("label") or "").strip(),
                    payload=_json(item),
                )
                session.add(row)
                rows.append(row)
            session.commit()
            return [self._provider_status_dict(row) for row in rows]

    def list_provider_statuses(self, provider_name: str | None = None) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            stmt = select(ProviderStatusRow)
            if provider_name:
                stmt = stmt.where(ProviderStatusRow.provider_name == self._normalize_provider_name(provider_name))
            rows = session.execute(stmt.order_by(ProviderStatusRow.provider_name.asc(), ProviderStatusRow.label.asc())).scalars().all()
            return [self._provider_status_dict(row) for row in rows]

    @staticmethod
    def _provider_config_dict(row: ProviderConfigRow) -> dict[str, Any]:
        return ProviderConfigRecord(
            provider_name=row.provider_name,
            payload=dict(row.payload or {}),
            updated_at=row.updated_at.isoformat() if row.updated_at else "",
        ).model_dump()

    @staticmethod
    def _provider_status_dict(row: ProviderStatusRow) -> dict[str, Any]:
        payload = dict(row.payload or {})
        return ProviderStatusRecord(
            provider_name=row.provider_name,
            label=row.label,
            payload=payload,
            status=ProviderConfigStore._provider_status_snapshot(payload),
            updated_at=row.updated_at.isoformat() if row.updated_at else "",
        ).model_dump()

    @staticmethod
    def _normalize_provider_name(provider_name: str) -> str:
        normalized = str(provider_name or "").strip()
        if not normalized:
            raise ValueError("provider_name is required.")
        return normalized

    @staticmethod
    def _normalize_status_label(label: str) -> str:
        normalized = str(label or "").strip()
        if not normalized:
            raise ValueError("provider status label is required.")
        return normalized

    @classmethod
    def _normalize_status_payloads(cls, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized_rows: list[dict[str, Any]] = []
        seen_labels: set[str] = set()
        for item in payloads:
            payload = dict(item or {})
            label = cls._normalize_status_label(str(payload.get("label") or ""))
            if label in seen_labels:
                raise ValueError(f"Duplicate provider status label '{label}'.")
            seen_labels.add(label)
            payload["label"] = label
            normalized_rows.append(payload)
        return normalized_rows

    @staticmethod
    def _provider_status_snapshot(payload: dict[str, Any]) -> ProviderStatusSnapshot:
        return ProviderStatusSnapshot.model_validate(
            {
                "app_name": str(payload.get("app_name") or "").strip(),
                "api_url": str(payload.get("api_url") or "").strip(),
                "ui_url": str(payload.get("ui_url") or "").strip(),
                "health_url": str(payload.get("health_url") or "").strip(),
                "warm_until": int(payload.get("warm_until") or 0),
                "last_seen_at": int(payload.get("last_seen_at") or 0),
                "last_health_ok": payload.get("last_health_ok"),
                "last_health_checked_at": int(payload.get("last_health_checked_at") or 0),
                "last_request_ok": payload.get("last_request_ok"),
                "last_request_checked_at": int(payload.get("last_request_checked_at") or 0),
                "last_error": str(payload.get("last_error") or "").strip(),
                "last_error_at": int(payload.get("last_error_at") or 0),
                "live_payload_checked_at": int(payload.get("live_payload_checked_at") or 0),
            }
        )

    @staticmethod
    def _provider_runtime_state(payload: dict[str, Any], statuses: list[dict[str, Any]] | None = None) -> ProviderOperationalRuntimeState:
        raw_payload = dict(payload or {})
        diagnostics: list[str] = []
        status_rows = [dict(item or {}) for item in (statuses or []) if isinstance(item, dict)]
        status_by_label = {
            str(item.get("label") or "").strip(): item
            for item in status_rows
            if str(item.get("label") or "").strip()
        }
        runtime_state_raw = raw_payload.get("runtime_state")
        if runtime_state_raw not in (None, {}) and not isinstance(runtime_state_raw, dict):
            diagnostics.append("runtime_state_invalid_type")
        runtime_state = runtime_state_raw if isinstance(runtime_state_raw, dict) else {}
        state_payload = dict(runtime_state or {})
        active_label = str(state_payload.get("active_token_name") or state_payload.get("active_label") or "").strip()
        active_status = status_by_label.get(active_label) if active_label else None
        status_payload = dict((active_status or {}).get("payload") or {})
        normalized_active_api_url = str(state_payload.get("active_api_url") or "").strip()
        normalized_active_ui_url = str(state_payload.get("active_ui_url") or "").strip()
        normalized_active_health_url = str(state_payload.get("active_health_url") or "").strip()
        normalized_active_app_name = str(state_payload.get("active_app_name") or "").strip()
        if active_label and active_status is None:
            diagnostics.append("active_label_missing_status")
        if active_status is not None:
            status_api_url = str(status_payload.get("api_url") or "").strip()
            status_ui_url = str(status_payload.get("ui_url") or "").strip()
            status_health_url = str(status_payload.get("health_url") or "").strip()
            status_app_name = str(status_payload.get("app_name") or "").strip()
            if normalized_active_api_url and status_api_url and normalized_active_api_url != status_api_url:
                diagnostics.append("active_api_url_mismatch")
            if normalized_active_ui_url and status_ui_url and normalized_active_ui_url != status_ui_url:
                diagnostics.append("active_ui_url_mismatch")
            if normalized_active_health_url and status_health_url and normalized_active_health_url != status_health_url:
                diagnostics.append("active_health_url_mismatch")
            if normalized_active_app_name and status_app_name and normalized_active_app_name != status_app_name:
                diagnostics.append("active_app_name_mismatch")
            if not normalized_active_api_url and status_api_url:
                normalized_active_api_url = status_api_url
            if not normalized_active_ui_url and status_ui_url:
                normalized_active_ui_url = status_ui_url
            if not normalized_active_health_url and status_health_url:
                normalized_active_health_url = status_health_url
            if not normalized_active_app_name and status_app_name:
                normalized_active_app_name = status_app_name
        return ProviderOperationalRuntimeState(
            app_name=str(state_payload.get("app_name") or "").strip(),
            runtime_generation=max(0, int(state_payload.get("runtime_generation") or 0)),
            next_index=max(0, int(state_payload.get("next_index") or 0)),
            active_label=active_label,
            active_api_url=normalized_active_api_url,
            active_ui_url=normalized_active_ui_url,
            active_health_url=normalized_active_health_url,
            active_app_name=normalized_active_app_name,
            active_status_found=active_status is not None,
            status_labels=sorted(status_by_label.keys()),
            status_count=len(status_by_label),
            diagnostics=diagnostics,
            payload=state_payload,
        )


class LibraryStore:
    def __init__(self, session_factory: sessionmaker) -> None:
        self.session_factory = session_factory

    def upsert_series(self, series_id: str, *, title: str = "", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.session_factory() as session:
            row = session.get(LibrarySeriesRow, series_id)
            if row is None:
                row = LibrarySeriesRow(series_id=series_id, title=title, metadata_json=_json(metadata))
                session.add(row)
            else:
                row.title = title
                row.metadata_json = _json(metadata)
            session.commit()
            return self._series_dict(row)

    def list_series(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            rows = session.execute(select(LibrarySeriesRow).order_by(LibrarySeriesRow.series_id.asc())).scalars().all()
            return [self._series_dict(row) for row in rows[:limit]]

    def upsert_book(
        self,
        book_id: str,
        *,
        series_id: str = "",
        title: str = "",
        book_index: int | None = None,
        source_uri: str = "",
        source_type: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self.session_factory() as session:
            row = session.get(LibraryBookRow, book_id)
            if row is None:
                row = LibraryBookRow(
                    book_id=book_id,
                    series_id=series_id,
                    title=title,
                    book_index=book_index,
                    source_uri=source_uri,
                    source_type=source_type,
                    metadata_json=_json(metadata),
                )
                session.add(row)
            else:
                row.series_id = series_id
                row.title = title
                row.book_index = book_index
                row.source_uri = source_uri
                row.source_type = source_type
                row.metadata_json = _json(metadata)
            session.commit()
            return self._book_dict(row)

    def list_books(self, *, series_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            stmt = select(LibraryBookRow)
            if series_id:
                stmt = stmt.where(LibraryBookRow.series_id == series_id)
            rows = session.execute(stmt.order_by(LibraryBookRow.series_id.asc(), LibraryBookRow.book_index.asc(), LibraryBookRow.book_id.asc())).scalars().all()
            return [self._book_dict(row) for row in rows[:limit]]

    def upsert_scene(
        self,
        scene_id: str,
        *,
        book_id: str,
        chapter_index: int,
        scene_index: int,
        summary: str = "",
        text: str = "",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self.session_factory() as session:
            row = session.get(LibrarySceneRow, scene_id)
            if row is None:
                row = LibrarySceneRow(
                    scene_id=scene_id,
                    book_id=book_id,
                    chapter_index=chapter_index,
                    scene_index=scene_index,
                    summary=summary,
                    text=text,
                    payload=_json(payload),
                )
                session.add(row)
            else:
                row.book_id = book_id
                row.chapter_index = chapter_index
                row.scene_index = scene_index
                row.summary = summary
                row.text = text
                row.payload = _json(payload)
            session.commit()
            return self._scene_dict(row)

    def list_scenes(self, *, book_id: str, limit: int = 500) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            rows = session.execute(
                select(LibrarySceneRow)
                .where(LibrarySceneRow.book_id == book_id)
                .order_by(LibrarySceneRow.chapter_index.asc(), LibrarySceneRow.scene_index.asc())
            ).scalars().all()
            return [self._scene_dict(row) for row in rows[:limit]]

    def upsert_record(
        self,
        record_id: str,
        *,
        record_type: str,
        series_id: str = "",
        book_id: str = "",
        scene_id: str = "",
        title: str = "",
        ordinal: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self.session_factory() as session:
            row = session.get(LibraryRecordRow, record_id)
            if row is None:
                row = LibraryRecordRow(
                    record_id=record_id,
                    record_type=record_type,
                    series_id=series_id,
                    book_id=book_id,
                    scene_id=scene_id,
                    title=title,
                    ordinal=ordinal,
                    payload=_json(payload),
                )
                session.add(row)
            else:
                row.record_type = record_type
                row.series_id = series_id
                row.book_id = book_id
                row.scene_id = scene_id
                row.title = title
                row.ordinal = ordinal
                row.payload = _json(payload)
            session.commit()
            return self._record_dict(row)

    def list_records(
        self,
        *,
        record_type: str | None = None,
        series_id: str | None = None,
        book_id: str | None = None,
        scene_id: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            stmt = select(LibraryRecordRow)
            if record_type:
                stmt = stmt.where(LibraryRecordRow.record_type == record_type)
            if series_id:
                stmt = stmt.where(LibraryRecordRow.series_id == series_id)
            if book_id:
                stmt = stmt.where(LibraryRecordRow.book_id == book_id)
            if scene_id:
                stmt = stmt.where(LibraryRecordRow.scene_id == scene_id)
            rows = session.execute(
                stmt.order_by(LibraryRecordRow.record_type.asc(), LibraryRecordRow.ordinal.asc(), LibraryRecordRow.record_id.asc())
            ).scalars().all()
            return [self._record_dict(row) for row in rows[:limit]]

    def delete_records(
        self,
        *,
        record_type: str | None = None,
        series_id: str | None = None,
        book_id: str | None = None,
        scene_id: str | None = None,
    ) -> int:
        with self.session_factory() as session:
            stmt = delete(LibraryRecordRow)
            if record_type:
                stmt = stmt.where(LibraryRecordRow.record_type == record_type)
            if series_id:
                stmt = stmt.where(LibraryRecordRow.series_id == series_id)
            if book_id:
                stmt = stmt.where(LibraryRecordRow.book_id == book_id)
            if scene_id:
                stmt = stmt.where(LibraryRecordRow.scene_id == scene_id)
            result = session.execute(stmt)
            session.commit()
            return int(result.rowcount or 0)

    @staticmethod
    def _series_dict(row: LibrarySeriesRow) -> dict[str, Any]:
        return {
            "series_id": row.series_id,
            "title": row.title,
            "metadata": dict(row.metadata_json or {}),
            "updated_at": row.updated_at.isoformat() if row.updated_at else "",
        }

    @staticmethod
    def _book_dict(row: LibraryBookRow) -> dict[str, Any]:
        return {
            "book_id": row.book_id,
            "series_id": row.series_id,
            "title": row.title,
            "book_index": row.book_index,
            "source_uri": row.source_uri,
            "source_type": row.source_type,
            "metadata": dict(row.metadata_json or {}),
            "updated_at": row.updated_at.isoformat() if row.updated_at else "",
        }

    @staticmethod
    def _scene_dict(row: LibrarySceneRow) -> dict[str, Any]:
        return {
            "scene_id": row.scene_id,
            "book_id": row.book_id,
            "chapter_index": row.chapter_index,
            "scene_index": row.scene_index,
            "summary": row.summary,
            "text": row.text,
            "payload": dict(row.payload or {}),
            "updated_at": row.updated_at.isoformat() if row.updated_at else "",
        }

    @staticmethod
    def _record_dict(row: LibraryRecordRow) -> dict[str, Any]:
        return {
            "record_id": row.record_id,
            "record_type": row.record_type,
            "series_id": row.series_id,
            "book_id": row.book_id,
            "scene_id": row.scene_id,
            "title": row.title,
            "ordinal": row.ordinal,
            "payload": dict(row.payload or {}),
            "updated_at": row.updated_at.isoformat() if row.updated_at else "",
        }


class IdentityStore:
    def __init__(self, session_factory: sessionmaker) -> None:
        self.session_factory = session_factory

    def upsert_identity_series(self, series_id: str, *, provider_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.session_factory() as session:
            row = session.get(IdentitySeriesRow, series_id)
            if row is None:
                row = IdentitySeriesRow(series_id=series_id, provider_name=provider_name, payload=_json(payload))
                session.add(row)
            else:
                row.provider_name = provider_name
                row.payload = _json(payload)
            session.commit()
            return self._identity_dict(row)

    def get_identity_series(self, series_id: str) -> dict[str, Any] | None:
        with self.session_factory() as session:
            row = session.get(IdentitySeriesRow, series_id)
            return self._identity_dict(row) if row else None

    @staticmethod
    def _identity_dict(row: IdentitySeriesRow) -> dict[str, Any]:
        return {
            "series_id": row.series_id,
            "provider_name": row.provider_name,
            "payload": dict(row.payload or {}),
            "updated_at": row.updated_at.isoformat() if row.updated_at else "",
        }


class JobStore:
    def __init__(self, session_factory: sessionmaker) -> None:
        self.session_factory = session_factory

    def create_job(self, job_id: str, *, job_type: str, status: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.session_factory() as session:
            row = JobRow(job_id=job_id, job_type=job_type, status=status, payload=_json(payload))
            session.merge(row)
            session.commit()
            return self.get_job(job_id) or {}

    def update_job(self, job_id: str, *, status: str | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
        with self.session_factory() as session:
            row = session.get(JobRow, job_id)
            if row is None:
                return None
            if status is not None:
                row.status = status
            if payload is not None:
                row.payload = _json(payload)
            session.commit()
            return self.get_job(job_id)

    def add_job_log(self, job_id: str, *, stage: str, message: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.session_factory() as session:
            row = JobLogRow(job_id=job_id, stage=stage, message=message, payload=_json(payload))
            session.add(row)
            session.commit()
            return self._job_log_dict(row)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self.session_factory() as session:
            row = session.get(JobRow, job_id)
            if row is None:
                return None
            logs = session.execute(
                select(JobLogRow).where(JobLogRow.job_id == job_id).order_by(JobLogRow.id.asc())
            ).scalars().all()
            payload = self._job_dict(row)
            payload["logs"] = [self._job_log_dict(item) for item in logs]
            return payload

    def list_jobs(self, *, job_type: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            stmt = select(JobRow)
            if job_type:
                stmt = stmt.where(JobRow.job_type == job_type)
            rows = session.execute(stmt.order_by(JobRow.updated_at.desc())).scalars().all()
            return [self._job_dict(row) for row in rows[:limit]]

    @staticmethod
    def _job_dict(row: JobRow) -> dict[str, Any]:
        return {
            "job_id": row.job_id,
            "job_type": row.job_type,
            "status": row.status,
            "payload": dict(row.payload or {}),
            "updated_at": row.updated_at.isoformat() if row.updated_at else "",
        }

    @staticmethod
    def _job_log_dict(row: JobLogRow) -> dict[str, Any]:
        return {
            "id": row.id,
            "job_id": row.job_id,
            "stage": row.stage,
            "message": row.message,
            "payload": dict(row.payload or {}),
            "created_at": row.created_at.isoformat() if row.created_at else "",
        }


class ExecutionQueueStore:
    ACTIVE_STATUSES = ("leased", "cancel_requested")
    CLAIMABLE_STATUSES = ("queued", "retry_wait")

    def __init__(self, session_factory: sessionmaker) -> None:
        self.session_factory = session_factory
        self._claim_lock = threading.RLock()

    def set_policy(self, queue_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = _queue_policy(payload)
        with self.session_factory.begin() as session:
            session.merge(ExecutionQueuePolicyRow(queue_name=_required(queue_name, "queue_name"), payload=normalized))
        return {"queue_name": queue_name, "payload": normalized}

    def get_policy(self, queue_name: str) -> dict[str, Any] | None:
        with self.session_factory() as session:
            row = session.get(ExecutionQueuePolicyRow, queue_name)
            return {"queue_name": row.queue_name, "payload": dict(row.payload or {}), "updated_at": row.updated_at.isoformat() if row.updated_at else ""} if row else None

    def enqueue(
        self, queue_id: str, *, run_id: str, queue_name: str, series_id: str = "", priority: int = 0,
        capabilities: list[str] | None = None, payload: dict[str, Any] | None = None, available_at_ms: int = 0,
        max_attempts: int = 3, backoff_seconds: int = 5,
    ) -> dict[str, Any]:
        now = _now_ms()
        with self.session_factory.begin() as session:
            existing = session.execute(select(ExecutionQueueRow).where(ExecutionQueueRow.run_id == _required(run_id, "run_id"))).scalar_one_or_none()
            if existing is not None:
                return self._item_dict(existing)
            if session.get(ExecutionQueuePolicyRow, queue_name) is None:
                session.add(ExecutionQueuePolicyRow(queue_name=queue_name, payload=_queue_policy({})))
            row = ExecutionQueueRow(
                queue_id=_required(queue_id, "queue_id"), run_id=run_id, queue_name=_required(queue_name, "queue_name"),
                series_id=str(series_id or "").strip(), status="queued", priority=int(priority),
                capabilities=_capabilities(capabilities), payload=_json(payload), available_at_ms=max(now, int(available_at_ms or 0)),
                max_attempts=max(1, int(max_attempts)), backoff_seconds=max(0, int(backoff_seconds)),
            )
            session.add(row)
            session.flush()
            self._emit(session, row, "queue.enqueued", status="queued")
            return self._item_dict(row)

    def claim(self, queue_name: str, *, worker_id: str, lease_seconds: int = 120, now_ms: int | None = None) -> dict[str, Any] | None:
        with self._claim_lock:
            return self._claim_locked(queue_name, worker_id=worker_id, lease_seconds=lease_seconds, now_ms=now_ms)

    def requeue(
        self, queue_id: str, *, payload: dict[str, Any] | None = None, priority: int | None = None,
        max_attempts: int | None = None, now_ms: int | None = None,
    ) -> dict[str, Any] | None:
        now = int(now_ms or _now_ms())
        with self.session_factory.begin() as session:
            row = session.execute(
                select(ExecutionQueueRow).where(ExecutionQueueRow.queue_id == queue_id).with_for_update()
            ).scalar_one_or_none()
            if row is None:
                return None
            if row.status not in {"dead_letter", "cancelled"}:
                raise ValueError(f"Queue item '{queue_id}' cannot be requeued from status '{row.status}'.")
            if payload is not None:
                row.payload = _json(payload)
            if priority is not None:
                row.priority = int(priority)
            if max_attempts is not None:
                row.max_attempts = max(1, int(max_attempts))
            row.status = "queued"
            row.available_at_ms = now
            row.attempt_count = 0
            row.cancellation_requested_at_ms = 0
            row.last_error = {}
            self._clear_lease(row)
            self._emit(session, row, "queue.requeued", status="queued", timestamp_ms=now)
            return self._item_dict(row)

    def _claim_locked(self, queue_name: str, *, worker_id: str, lease_seconds: int = 120, now_ms: int | None = None) -> dict[str, Any] | None:
        now = int(now_ms or _now_ms())
        with self.session_factory.begin() as session:
            policy = self._locked_policy(session, queue_name)
            self._recover_expired(session, queue_name, now)
            active = session.execute(select(ExecutionQueueRow).where(
                ExecutionQueueRow.queue_name == queue_name,
                ExecutionQueueRow.status.in_(self.ACTIVE_STATUSES),
                ExecutionQueueRow.lease_expires_at_ms > now,
            )).scalars().all()
            limits = _queue_policy(policy.payload or {})
            if len(active) >= limits["global_limit"]:
                return None
            candidates = session.execute(
                select(ExecutionQueueRow).where(
                    ExecutionQueueRow.queue_name == queue_name,
                    ExecutionQueueRow.status.in_(self.CLAIMABLE_STATUSES),
                    ExecutionQueueRow.available_at_ms <= now,
                ).order_by(ExecutionQueueRow.priority.desc(), ExecutionQueueRow.created_at.asc()).with_for_update(skip_locked=True)
            ).scalars().all()
            for row in candidates:
                if not self._within_limits(row, active, limits):
                    continue
                row.status = "leased"
                row.lease_owner = _required(worker_id, "worker_id")
                row.lease_token = uuid.uuid4().hex
                row.heartbeat_at_ms = now
                row.lease_expires_at_ms = now + max(1, int(lease_seconds)) * 1000
                row.attempt_count += 1
                self._emit(session, row, "queue.claimed", status="leased", worker_id=worker_id, payload={"attempt": row.attempt_count, "lease_expires_at_ms": row.lease_expires_at_ms})
                session.flush()
                return self._item_dict(row)
            return None

    def heartbeat(self, queue_id: str, *, worker_id: str, lease_token: str, lease_seconds: int = 120, now_ms: int | None = None) -> dict[str, Any] | None:
        now = int(now_ms or _now_ms())
        with self.session_factory.begin() as session:
            row = self._leased_row(session, queue_id, worker_id, lease_token, now)
            if row is None:
                return None
            row.heartbeat_at_ms = now
            row.lease_expires_at_ms = now + max(1, int(lease_seconds)) * 1000
            self._emit(session, row, "queue.heartbeat", status=row.status, worker_id=worker_id)
            return self._item_dict(row)

    def complete(self, queue_id: str, *, worker_id: str, lease_token: str, status: str = "succeeded", payload: dict[str, Any] | None = None, now_ms: int | None = None) -> dict[str, Any] | None:
        now = int(now_ms or _now_ms())
        with self.session_factory.begin() as session:
            row = self._leased_row(session, queue_id, worker_id, lease_token, now)
            if row is None:
                return None
            row.status = "cancelled" if row.cancellation_requested_at_ms else str(status or "succeeded")
            row.payload = {**dict(row.payload or {}), **dict(payload or {})}
            self._clear_lease(row)
            self._emit(session, row, "queue.completed", status=row.status, worker_id=worker_id, timestamp_ms=now)
            return self._item_dict(row)

    def fail(self, queue_id: str, *, worker_id: str, lease_token: str, error: dict[str, Any], retryable: bool = True, now_ms: int | None = None) -> dict[str, Any] | None:
        now = int(now_ms or _now_ms())
        with self.session_factory.begin() as session:
            row = self._leased_row(session, queue_id, worker_id, lease_token, now)
            if row is None:
                return None
            row.last_error = _json(error)
            if row.cancellation_requested_at_ms:
                row.status = "cancelled"
            elif retryable and row.attempt_count < row.max_attempts:
                row.status = "retry_wait"
                row.available_at_ms = now + row.backoff_seconds * (2 ** max(0, row.attempt_count - 1)) * 1000
            else:
                row.status = "dead_letter"
            self._clear_lease(row)
            self._emit(session, row, "queue.failed", status=row.status, worker_id=worker_id, timestamp_ms=now, payload={"retryable": retryable, "error": row.last_error})
            return self._item_dict(row)

    def request_cancel(self, queue_id: str, *, reason: str = "", now_ms: int | None = None) -> dict[str, Any] | None:
        now = int(now_ms or _now_ms())
        with self.session_factory.begin() as session:
            row = session.execute(select(ExecutionQueueRow).where(ExecutionQueueRow.queue_id == queue_id).with_for_update()).scalar_one_or_none()
            if row is None:
                return None
            if row.status in {"succeeded", "cancelled", "dead_letter"}:
                return self._item_dict(row)
            row.cancellation_requested_at_ms = now
            if row.status in self.CLAIMABLE_STATUSES:
                row.status = "cancelled"
                self._clear_lease(row)
            else:
                row.status = "cancel_requested"
            self._emit(session, row, "queue.cancellation_requested", status=row.status, timestamp_ms=now, payload={"reason": str(reason or "")})
            return self._item_dict(row)

    def is_cancellation_requested(self, queue_id: str) -> bool:
        row = self.get(queue_id)
        return bool(row and (row["cancellation_requested_at_ms"] or row["status"] in {"cancel_requested", "cancelled"}))

    def recover_expired(self, queue_name: str, *, now_ms: int | None = None) -> list[dict[str, Any]]:
        now = int(now_ms or _now_ms())
        with self.session_factory.begin() as session:
            self._locked_policy(session, queue_name)
            return [self._item_dict(row) for row in self._recover_expired(session, queue_name, now)]

    def get(self, queue_id: str) -> dict[str, Any] | None:
        with self.session_factory() as session:
            row = session.get(ExecutionQueueRow, queue_id)
            return self._item_dict(row) if row else None

    def list(self, *, queue_name: str | None = None, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            stmt = select(ExecutionQueueRow)
            if queue_name:
                stmt = stmt.where(ExecutionQueueRow.queue_name == queue_name)
            if status:
                stmt = stmt.where(ExecutionQueueRow.status == status)
            rows = session.execute(stmt.order_by(ExecutionQueueRow.created_at.desc())).scalars().all()
            return [self._item_dict(row) for row in rows[:max(1, int(limit))]]

    def emit_event(self, *, queue_name: str, queue_id: str, run_id: str, event_type: str, status: str = "", worker_id: str = "", timestamp_ms: int | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        with self.session_factory.begin() as session:
            row = ExecutionTelemetryRow(queue_name=queue_name, queue_id=queue_id, run_id=run_id, event_type=event_type, status=status, worker_id=worker_id, timestamp_ms=int(timestamp_ms or _now_ms()), payload=_json(payload))
            session.add(row)
            session.flush()
            return self._event_dict(row)

    def list_events(self, *, run_id: str = "", queue_name: str = "", limit: int = 1000) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            stmt = select(ExecutionTelemetryRow)
            if run_id:
                stmt = stmt.where(ExecutionTelemetryRow.run_id == run_id)
            if queue_name:
                stmt = stmt.where(ExecutionTelemetryRow.queue_name == queue_name)
            rows = session.execute(stmt.order_by(ExecutionTelemetryRow.id.asc())).scalars().all()
            return [self._event_dict(row) for row in rows[-max(1, int(limit)):]]

    def purge_terminal(self, queue_name: str, *, run_ids: list[str]) -> dict[str, int]:
        normalized_queue = _required(queue_name, "queue_name")
        normalized_runs = sorted({_required(run_id, "run_id") for run_id in run_ids})
        if not normalized_runs:
            return {"queue_items": 0, "events": 0, "policies": 0}
        terminal_statuses = ("succeeded", "cancelled", "dead_letter")
        with self.session_factory.begin() as session:
            terminal_runs = list(session.execute(
                select(ExecutionQueueRow.run_id).where(
                    ExecutionQueueRow.queue_name == normalized_queue,
                    ExecutionQueueRow.run_id.in_(normalized_runs),
                    ExecutionQueueRow.status.in_(terminal_statuses),
                )
            ).scalars())
            if not terminal_runs:
                return {"queue_items": 0, "events": 0, "policies": 0}
            events = session.execute(delete(ExecutionTelemetryRow).where(
                ExecutionTelemetryRow.queue_name == normalized_queue,
                ExecutionTelemetryRow.run_id.in_(terminal_runs),
            )).rowcount or 0
            queue_items = session.execute(delete(ExecutionQueueRow).where(
                ExecutionQueueRow.queue_name == normalized_queue,
                ExecutionQueueRow.run_id.in_(terminal_runs),
                ExecutionQueueRow.status.in_(terminal_statuses),
            )).rowcount or 0
            remaining = session.execute(select(ExecutionQueueRow.queue_id).where(
                ExecutionQueueRow.queue_name == normalized_queue,
            ).limit(1)).scalar_one_or_none()
            policies = 0
            if remaining is None:
                policies = session.execute(delete(ExecutionQueuePolicyRow).where(
                    ExecutionQueuePolicyRow.queue_name == normalized_queue,
                )).rowcount or 0
            return {"queue_items": int(queue_items), "events": int(events), "policies": int(policies)}

    def _locked_policy(self, session: Session, queue_name: str) -> ExecutionQueuePolicyRow:
        row = session.execute(select(ExecutionQueuePolicyRow).where(ExecutionQueuePolicyRow.queue_name == queue_name).with_for_update()).scalar_one_or_none()
        if row is None:
            row = ExecutionQueuePolicyRow(queue_name=_required(queue_name, "queue_name"), payload=_queue_policy({}))
            session.add(row)
            session.flush()
        return row

    def _recover_expired(self, session: Session, queue_name: str, now: int) -> list[ExecutionQueueRow]:
        rows = session.execute(select(ExecutionQueueRow).where(
            ExecutionQueueRow.queue_name == queue_name,
            ExecutionQueueRow.status.in_(self.ACTIVE_STATUSES),
            ExecutionQueueRow.lease_expires_at_ms > 0,
            ExecutionQueueRow.lease_expires_at_ms <= now,
        ).with_for_update()).scalars().all()
        for row in rows:
            if row.cancellation_requested_at_ms:
                row.status = "cancelled"
            elif row.attempt_count >= row.max_attempts:
                row.status = "dead_letter"
            else:
                row.status = "retry_wait"
                row.available_at_ms = now + row.backoff_seconds * (2 ** max(0, row.attempt_count - 1)) * 1000
            self._clear_lease(row)
            self._emit(session, row, "queue.lease_expired", status=row.status, timestamp_ms=now)
        return rows

    @staticmethod
    def _within_limits(row: ExecutionQueueRow, active: list[ExecutionQueueRow], limits: dict[str, Any]) -> bool:
        if row.series_id and len([item for item in active if item.series_id == row.series_id]) >= limits["per_series_limit"]:
            return False
        capability_limits = dict(limits.get("capability_limits") or {})
        for capability in list(row.capabilities or []):
            limit = int(capability_limits.get(capability) or limits.get("default_capability_limit") or limits["global_limit"])
            if len([item for item in active if capability in list(item.capabilities or [])]) >= limit:
                return False
        return True

    @staticmethod
    def _leased_row(session: Session, queue_id: str, worker_id: str, lease_token: str, now_ms: int) -> ExecutionQueueRow | None:
        row = session.execute(select(ExecutionQueueRow).where(ExecutionQueueRow.queue_id == queue_id).with_for_update()).scalar_one_or_none()
        if (
            row is None
            or row.status not in ExecutionQueueStore.ACTIVE_STATUSES
            or row.lease_owner != worker_id
            or row.lease_token != lease_token
            or row.lease_expires_at_ms <= now_ms
        ):
            return None
        return row

    @staticmethod
    def _clear_lease(row: ExecutionQueueRow) -> None:
        row.lease_owner = ""
        row.lease_token = ""
        row.lease_expires_at_ms = 0
        row.heartbeat_at_ms = 0

    @staticmethod
    def _emit(session: Session, item: ExecutionQueueRow, event_type: str, *, status: str, worker_id: str = "", timestamp_ms: int | None = None, payload: dict[str, Any] | None = None) -> None:
        session.add(ExecutionTelemetryRow(queue_name=item.queue_name, queue_id=item.queue_id, run_id=item.run_id, event_type=event_type, status=status, worker_id=worker_id, timestamp_ms=int(timestamp_ms or _now_ms()), payload=_json(payload)))

    @staticmethod
    def _item_dict(row: ExecutionQueueRow) -> dict[str, Any]:
        return {name: getattr(row, name) for name in (
            "queue_id", "run_id", "queue_name", "series_id", "status", "priority", "available_at_ms", "lease_owner", "lease_token",
            "lease_expires_at_ms", "heartbeat_at_ms", "cancellation_requested_at_ms", "attempt_count", "max_attempts", "backoff_seconds",
        )} | {"capabilities": list(row.capabilities or []), "payload": dict(row.payload or {}), "last_error": dict(row.last_error or {}), "created_at": row.created_at.isoformat() if row.created_at else "", "updated_at": row.updated_at.isoformat() if row.updated_at else ""}

    @staticmethod
    def _event_dict(row: ExecutionTelemetryRow) -> dict[str, Any]:
        return {"id": row.id, "queue_name": row.queue_name, "queue_id": row.queue_id, "run_id": row.run_id, "event_type": row.event_type, "status": row.status, "worker_id": row.worker_id, "timestamp_ms": row.timestamp_ms, "payload": dict(row.payload or {})}


class LineageStore:
    """Append-only stage execution history; no mutation or deletion surface is exposed."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self.session_factory = session_factory

    def append(self, record: dict[str, Any]) -> dict[str, Any]:
        payload = dict(record or {})
        row = StageLineageRow(
            execution_id=_required(payload.get("execution_id"), "execution_id"),
            run_id=_required(payload.get("run_id"), "run_id"),
            series_id=_required(payload.get("series_id"), "series_id"),
            stage=_required(payload.get("stage"), "stage"),
            attempt=max(1, int(payload.get("attempt") or 1)),
            status=_required(payload.get("status"), "status"),
            execution_mode=str(payload.get("execution_mode") or "executed"),
            input_fingerprint=_required(payload.get("input_fingerprint"), "input_fingerprint"),
            output_fingerprint=str(payload.get("output_fingerprint") or ""),
            lineage_fingerprint=_required(payload.get("lineage_fingerprint"), "lineage_fingerprint"),
            parent_fingerprints=_json(payload.get("parent_fingerprints")),
            versions=_json(payload.get("versions")),
            payload=_json(payload.get("payload")),
        )
        with self.session_factory.begin() as session:
            session.add(row)
            session.flush()
            return self._record_dict(row)

    def get(self, execution_id: str) -> dict[str, Any] | None:
        with self.session_factory() as session:
            row = session.get(StageLineageRow, execution_id)
            return self._record_dict(row) if row else None

    def find_latest_accepted(
        self, *, series_id: str, stage: str, input_fingerprint: str, output_fingerprint: str = "",
    ) -> dict[str, Any] | None:
        with self.session_factory() as session:
            stmt = select(StageLineageRow).where(
                StageLineageRow.series_id == series_id,
                StageLineageRow.stage == stage,
                StageLineageRow.input_fingerprint == input_fingerprint,
                StageLineageRow.status == "accepted",
            )
            if output_fingerprint:
                stmt = stmt.where(StageLineageRow.output_fingerprint == output_fingerprint)
            row = session.execute(stmt.order_by(StageLineageRow.created_at.desc())).scalars().first()
            return self._record_dict(row) if row else None

    def list(self, *, run_id: str = "", series_id: str = "", stage: str = "", limit: int = 1000) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            stmt = select(StageLineageRow)
            if run_id:
                stmt = stmt.where(StageLineageRow.run_id == run_id)
            if series_id:
                stmt = stmt.where(StageLineageRow.series_id == series_id)
            if stage:
                stmt = stmt.where(StageLineageRow.stage == stage)
            rows = session.execute(stmt.order_by(StageLineageRow.created_at.asc())).scalars().all()
            return [self._record_dict(row) for row in rows[-max(1, int(limit)):]]

    @staticmethod
    def _record_dict(row: StageLineageRow) -> dict[str, Any]:
        return {
            "execution_id": row.execution_id,
            "run_id": row.run_id,
            "series_id": row.series_id,
            "stage": row.stage,
            "attempt": row.attempt,
            "status": row.status,
            "execution_mode": row.execution_mode,
            "input_fingerprint": row.input_fingerprint,
            "output_fingerprint": row.output_fingerprint,
            "lineage_fingerprint": row.lineage_fingerprint,
            "parent_fingerprints": dict(row.parent_fingerprints or {}),
            "versions": dict(row.versions or {}),
            "payload": dict(row.payload or {}),
            "created_at": row.created_at.isoformat() if row.created_at else "",
        }


class ObservabilityStore:
    """Append-only, idempotent operational history with bounded query surfaces."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self.session_factory = session_factory

    def append(self, record: dict[str, Any]) -> dict[str, Any]:
        return self.append_many([record])[0]

    def append_many(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = [self._row(item) for item in records]
        with self.session_factory.begin() as session:
            for row in normalized:
                values = {column.name: getattr(row, column.name) for column in ObservabilityRecordRow.__table__.columns if column.name != "created_at"}
                dialect = session.get_bind().dialect.name
                if dialect == "postgresql":
                    session.execute(postgresql_insert(ObservabilityRecordRow).values(**values).on_conflict_do_nothing(index_elements=["observation_id"]))
                elif dialect == "sqlite":
                    session.execute(sqlite_insert(ObservabilityRecordRow).values(**values).on_conflict_do_nothing(index_elements=["observation_id"]))
                elif session.get(ObservabilityRecordRow, row.observation_id) is None:
                    session.add(row)
            session.flush()
            rows = [session.get(ObservabilityRecordRow, row.observation_id) for row in normalized]
            return [self._record_dict(row) for row in rows if row is not None]

    def list(
        self, *, kind: str = "", run_id: str = "", series_id: str = "", component: str = "",
        provider: str = "", name: str = "", since_ms: int = 0, until_ms: int = 0, limit: int = 1000,
    ) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            stmt = select(ObservabilityRecordRow)
            for value, column in ((kind, ObservabilityRecordRow.kind), (run_id, ObservabilityRecordRow.run_id),
                                  (series_id, ObservabilityRecordRow.series_id), (component, ObservabilityRecordRow.component),
                                  (provider, ObservabilityRecordRow.provider), (name, ObservabilityRecordRow.name)):
                if value:
                    stmt = stmt.where(column == value)
            if since_ms:
                stmt = stmt.where(ObservabilityRecordRow.timestamp_ms >= int(since_ms))
            if until_ms:
                stmt = stmt.where(ObservabilityRecordRow.timestamp_ms <= int(until_ms))
            rows = session.execute(
                stmt.order_by(ObservabilityRecordRow.timestamp_ms.desc()).limit(max(1, int(limit)))
            ).scalars().all()
            return [self._record_dict(row) for row in reversed(rows)]

    def delete_before(self, timestamp_ms: int, *, kind: str = "") -> int:
        with self.session_factory.begin() as session:
            stmt = delete(ObservabilityRecordRow).where(ObservabilityRecordRow.timestamp_ms < int(timestamp_ms))
            if kind:
                stmt = stmt.where(ObservabilityRecordRow.kind == kind)
            result = session.execute(stmt)
            return max(0, int(result.rowcount or 0))

    @staticmethod
    def _row(record: dict[str, Any]) -> ObservabilityRecordRow:
        payload = dict(record or {})
        return ObservabilityRecordRow(
            observation_id=_required(payload.get("observation_id"), "observation_id"),
            kind=_required(payload.get("kind"), "kind"), timestamp_ms=int(payload.get("timestamp_ms") or _now_ms()),
            run_id=str(payload.get("run_id") or ""), series_id=str(payload.get("series_id") or ""),
            component=str(payload.get("component") or ""), stage=str(payload.get("stage") or ""),
            provider=str(payload.get("provider") or ""), name=_required(payload.get("name"), "name"),
            status=str(payload.get("status") or ""), value=payload.get("value"), unit=str(payload.get("unit") or ""),
            dimensions=_json(payload.get("dimensions")), payload=_json(payload.get("payload")),
        )

    @staticmethod
    def _record_dict(row: ObservabilityRecordRow) -> dict[str, Any]:
        return {
            "observation_id": row.observation_id, "kind": row.kind, "timestamp_ms": row.timestamp_ms,
            "run_id": row.run_id, "series_id": row.series_id, "component": row.component, "stage": row.stage,
            "provider": row.provider, "name": row.name, "status": row.status, "value": row.value, "unit": row.unit,
            "dimensions": dict(row.dimensions or {}), "payload": dict(row.payload or {}),
            "created_at": row.created_at.isoformat() if row.created_at else "",
        }


class UsageLedgerStore:
    """Append-only usage accounting with transactionally serialized budget admission."""

    _lock = threading.RLock()
    _METRICS = ("request_count", "input_tokens", "output_tokens", "cached_input_tokens", "compute_seconds", "image_count", "audio_seconds", "cost_usd")

    def __init__(self, session_factory: sessionmaker) -> None:
        self.session_factory = session_factory

    def configure_policy(self, policy: dict[str, Any]) -> dict[str, Any]:
        payload = dict(policy or {})
        policy_id = _required(payload.get("policy_id"), "policy_id")
        with self.session_factory.begin() as session:
            row = session.get(UsageBudgetPolicyRow, policy_id) or UsageBudgetPolicyRow(policy_id=policy_id)
            row.scope_type = _required(payload.get("scope_type"), "scope_type")
            row.scope_value = str(payload.get("scope_value") or "")
            row.window_seconds = max(0, int(payload.get("window_seconds") or 0))
            row.limits = _json(payload.get("limits"))
            row.hard_limit = bool(payload.get("hard_limit", True))
            row.enabled = bool(payload.get("enabled", True))
            session.add(row)
            session.flush()
            return self._policy_dict(row)

    def list_policies(self, *, enabled: bool | None = None, limit: int = 1000) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            stmt = select(UsageBudgetPolicyRow)
            if enabled is not None:
                stmt = stmt.where(UsageBudgetPolicyRow.enabled.is_(bool(enabled)))
            rows = session.execute(stmt.order_by(UsageBudgetPolicyRow.policy_id).limit(max(1, int(limit)))).scalars().all()
            return [self._policy_dict(row) for row in rows]

    def reserve(self, entry: dict[str, Any]) -> dict[str, Any]:
        row = self._entry_row(entry)
        if row.entry_kind != "reservation":
            raise ValueError("Usage reservation entries must use entry_kind='reservation'.")
        with self._lock, self.session_factory.begin() as session:
            existing = session.get(UsageLedgerRow, row.entry_id)
            if existing is not None:
                return {"authorized": True, "entry": self._entry_dict(existing), "policies": []}
            policies = self._applicable_policies(session, row)
            self._lock_policies(session, policies)
            breaches = self._breaches(session, row, policies)
            hard = [item for item in breaches if item["hard_limit"]]
            if hard:
                return {"authorized": False, "entry": None, "policies": breaches}
            session.add(row)
            session.flush()
            return {"authorized": True, "entry": self._entry_dict(row), "policies": breaches}

    def settle(self, *, reservation_id: str, release_entry: dict[str, Any], charge_entry: dict[str, Any]) -> dict[str, Any]:
        release_row, charge_row = self._entry_row(release_entry), self._entry_row(charge_entry)
        if release_row.entry_kind != "reservation_release" or charge_row.entry_kind != "charge":
            raise ValueError("Settlement requires reservation_release and charge entries.")
        if release_row.reservation_id != reservation_id or charge_row.reservation_id != reservation_id:
            raise ValueError("Settlement reservation IDs must match.")
        with self._lock, self.session_factory.begin() as session:
            reservation = session.execute(select(UsageLedgerRow).where(UsageLedgerRow.reservation_id == reservation_id, UsageLedgerRow.entry_kind == "reservation")).scalar_one_or_none()
            if reservation is None:
                raise ValueError(f"Unknown usage reservation '{reservation_id}'.")
            existing_charge = session.get(UsageLedgerRow, charge_row.entry_id)
            if existing_charge is not None:
                return {"release": self._entry_dict(session.get(UsageLedgerRow, release_row.entry_id)), "charge": self._entry_dict(existing_charge)}
            if session.get(UsageLedgerRow, release_row.entry_id) is None:
                session.add(release_row)
            session.add(charge_row)
            session.flush()
            return {"release": self._entry_dict(release_row), "charge": self._entry_dict(charge_row)}

    def release(self, entry: dict[str, Any]) -> dict[str, Any]:
        row = self._entry_row(entry)
        if row.entry_kind != "reservation_release":
            raise ValueError("Usage release entries must use entry_kind='reservation_release'.")
        with self._lock, self.session_factory.begin() as session:
            existing = session.get(UsageLedgerRow, row.entry_id)
            if existing is None:
                session.add(row)
                session.flush()
                existing = row
            return self._entry_dict(existing)

    def list(self, *, run_id: str = "", provider: str = "", account_alias: str = "", entry_kind: str = "", since_ms: int = 0, limit: int = 1000) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            stmt = select(UsageLedgerRow)
            for value, column in ((run_id, UsageLedgerRow.run_id), (provider, UsageLedgerRow.provider), (account_alias, UsageLedgerRow.account_alias), (entry_kind, UsageLedgerRow.entry_kind)):
                if value:
                    stmt = stmt.where(column == value)
            if since_ms:
                stmt = stmt.where(UsageLedgerRow.timestamp_ms >= int(since_ms))
            rows = session.execute(stmt.order_by(UsageLedgerRow.timestamp_ms.desc()).limit(max(1, int(limit)))).scalars().all()
            return [self._entry_dict(row) for row in reversed(rows)]

    def _applicable_policies(self, session: Session, row: UsageLedgerRow) -> list[UsageBudgetPolicyRow]:
        policies = session.execute(select(UsageBudgetPolicyRow).where(UsageBudgetPolicyRow.enabled.is_(True))).scalars().all()
        values = {"global": "", "run": row.run_id, "provider": row.provider, "account": row.account_alias, "model": row.model}
        return [policy for policy in policies if policy.scope_type in values and (not policy.scope_value or policy.scope_value == values[policy.scope_type])]

    @staticmethod
    def _lock_policies(session: Session, policies: list[UsageBudgetPolicyRow]) -> None:
        if session.get_bind().dialect.name == "postgresql":
            for policy in sorted(policies, key=lambda item: item.policy_id):
                session.execute(text("select pg_advisory_xact_lock(hashtext(:key))"), {"key": f"usage-budget:{policy.policy_id}"})

    def _breaches(self, session: Session, candidate: UsageLedgerRow, policies: list[UsageBudgetPolicyRow]) -> list[dict[str, Any]]:
        now = candidate.timestamp_ms
        results = []
        for policy in policies:
            cutoff = now - max(0, policy.window_seconds) * 1000 if policy.window_seconds else 0
            stmt = select(UsageLedgerRow)
            if cutoff:
                stmt = stmt.where(UsageLedgerRow.timestamp_ms >= cutoff)
            scope_columns = {"run": (UsageLedgerRow.run_id, candidate.run_id), "provider": (UsageLedgerRow.provider, candidate.provider),
                             "account": (UsageLedgerRow.account_alias, candidate.account_alias), "model": (UsageLedgerRow.model, candidate.model)}
            scope = scope_columns.get(policy.scope_type)
            if scope is not None:
                scope_column, candidate_value = scope
                stmt = stmt.where(scope_column == (policy.scope_value or candidate_value))
            rows = session.execute(stmt).scalars().all()
            released = {row.reservation_id for row in rows if row.entry_kind == "reservation_release"}
            active = [
                row
                for row in rows
                if row.entry_kind != "reservation"
                or not row.expires_at_ms
                or row.expires_at_ms >= now
                or row.reservation_id in released
            ]
            exceeded = []
            for metric, limit in dict(policy.limits or {}).items():
                if metric not in self._METRICS:
                    continue
                projected = sum(float(getattr(row, metric) or 0) for row in active) + float(getattr(candidate, metric) or 0)
                if projected > float(limit):
                    exceeded.append({"metric": metric, "projected": projected, "limit": float(limit)})
            if exceeded:
                results.append({"policy_id": policy.policy_id, "hard_limit": policy.hard_limit, "exceeded": exceeded})
        return results

    @staticmethod
    def _entry_row(entry: dict[str, Any]) -> UsageLedgerRow:
        payload = dict(entry or {})
        values = {name: float(payload.get(name) or 0) for name in UsageLedgerStore._METRICS}
        return UsageLedgerRow(
            entry_id=_required(payload.get("entry_id"), "entry_id"), reservation_id=_required(payload.get("reservation_id"), "reservation_id"),
            entry_kind=_required(payload.get("entry_kind"), "entry_kind"), timestamp_ms=int(payload.get("timestamp_ms") or _now_ms()),
            expires_at_ms=max(0, int(payload.get("expires_at_ms") or 0)), release_id=str(payload.get("release_id") or ""),
            run_id=str(payload.get("run_id") or ""), series_id=str(payload.get("series_id") or ""), stage=str(payload.get("stage") or ""),
            agent=str(payload.get("agent") or ""), component=str(payload.get("component") or ""), provider=str(payload.get("provider") or ""),
            account_alias=str(payload.get("account_alias") or ""), model=str(payload.get("model") or ""), operation=str(payload.get("operation") or ""),
            cost_status=str(payload.get("cost_status") or "unpriced"), pricing_version=str(payload.get("pricing_version") or ""),
            evidence=_json(payload.get("evidence")), **values,
        )

    @staticmethod
    def _entry_dict(row: UsageLedgerRow | None) -> dict[str, Any] | None:
        if row is None:
            return None
        result = {column: getattr(row, column) for column in (
            "entry_id", "reservation_id", "entry_kind", "timestamp_ms", "expires_at_ms", "release_id", "run_id", "series_id", "stage", "agent",
            "component", "provider", "account_alias", "model", "operation", "request_count", "input_tokens", "output_tokens", "cached_input_tokens",
            "compute_seconds", "image_count", "audio_seconds", "cost_usd", "cost_status", "pricing_version",
        )}
        result["evidence"] = dict(row.evidence or {})
        result["created_at"] = row.created_at.isoformat() if row.created_at else ""
        return result

    @staticmethod
    def _policy_dict(row: UsageBudgetPolicyRow) -> dict[str, Any]:
        return {"policy_id": row.policy_id, "scope_type": row.scope_type, "scope_value": row.scope_value, "window_seconds": row.window_seconds,
                "limits": dict(row.limits or {}), "hard_limit": row.hard_limit, "enabled": row.enabled,
                "created_at": row.created_at.isoformat() if row.created_at else "", "updated_at": row.updated_at.isoformat() if row.updated_at else ""}


class DeploymentStore:
    def __init__(self, session_factory: sessionmaker) -> None:
        self.session_factory = session_factory
        self._promotion_lock = threading.RLock()

    def record_release(self, release: dict[str, Any]) -> dict[str, Any]:
        payload = dict(release or {})
        row = DeploymentReleaseRow(
            release_id=_required(payload.get("release_id"), "release_id"),
            version=_required(payload.get("version"), "version"),
            git_sha=_required(payload.get("git_sha"), "git_sha"),
            image_digest=str(payload.get("image_digest") or ""),
            status=_required(payload.get("status"), "status"),
            manifest=_json(payload.get("manifest")),
        )
        with self.session_factory.begin() as session:
            if session.get(DeploymentReleaseRow, row.release_id) is not None:
                raise ValueError(f"Release '{row.release_id}' already exists.")
            session.add(row)
            session.flush()
            return self._release_dict(row)

    def set_release_status(self, release_id: str, *, status: str) -> dict[str, Any] | None:
        with self.session_factory.begin() as session:
            row = session.get(DeploymentReleaseRow, release_id)
            if row is None:
                return None
            row.status = _required(status, "status")
            row.promoted_at = utcnow() if status == "production" else row.promoted_at
            session.flush()
            return self._release_dict(row)

    def promote_release(self, release_id: str, *, expected_status: str = "staging") -> dict[str, Any]:
        with self._promotion_lock:
            with self.session_factory.begin() as session:
                if session.bind is not None and session.bind.dialect.name == "postgresql":
                    session.execute(text("select pg_advisory_xact_lock(hashtext('saga_release_promotion'))"))
                target = session.execute(
                    select(DeploymentReleaseRow).where(DeploymentReleaseRow.release_id == release_id).with_for_update()
                ).scalar_one_or_none()
                if target is None:
                    raise ValueError(f"Unknown release '{release_id}'.")
                if target.status != expected_status:
                    raise ValueError(f"Invalid release transition {target.status} -> production.")
                active = session.execute(
                    select(DeploymentReleaseRow).where(DeploymentReleaseRow.status == "production").with_for_update()
                ).scalars().all()
                for row in active:
                    if row.release_id != release_id:
                        row.status = "rolled_back"
                session.flush()
                target.status = "production"
                target.promoted_at = utcnow()
                session.flush()
                return self._release_dict(target)

    def get_release(self, release_id: str) -> dict[str, Any] | None:
        with self.session_factory() as session:
            row = session.get(DeploymentReleaseRow, release_id)
            return self._release_dict(row) if row else None

    def list_releases(self, *, status: str = "", limit: int = 100) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            stmt = select(DeploymentReleaseRow)
            if status:
                stmt = stmt.where(DeploymentReleaseRow.status == status)
            rows = session.execute(stmt.order_by(DeploymentReleaseRow.created_at.desc()).limit(max(1, int(limit)))).scalars().all()
            return [self._release_dict(row) for row in rows]

    def record_release_gate_evidence(self, evidence: dict[str, Any]) -> dict[str, Any]:
        payload = dict(evidence or {})
        row = DeploymentReleaseGateEvidenceRow(
            evidence_id=_required(payload.get("evidence_id"), "evidence_id"),
            release_id=_required(payload.get("release_id"), "release_id"),
            gate=_required(payload.get("gate"), "gate"),
            status=_required(payload.get("status"), "status"),
            observed_at_ms=max(1, int(payload.get("observed_at_ms") or 0)),
            expires_at_ms=max(0, int(payload.get("expires_at_ms") or 0)),
            source=_required(payload.get("source"), "source"),
            evidence_sha256=_required(payload.get("evidence_sha256"), "evidence_sha256"),
            details=_json(payload.get("details")),
            artifact_reference=_json(payload.get("artifact_reference")),
        )
        with self.session_factory.begin() as session:
            existing = session.get(DeploymentReleaseGateEvidenceRow, row.evidence_id)
            if existing is not None:
                if existing.evidence_sha256 != row.evidence_sha256:
                    raise ValueError(f"Release gate evidence '{row.evidence_id}' is immutable.")
                return self._gate_evidence_dict(existing)
            if session.get(DeploymentReleaseRow, row.release_id) is None:
                raise ValueError(f"Unknown release '{row.release_id}'.")
            session.add(row)
            session.flush()
            return self._gate_evidence_dict(row)

    def list_release_gate_evidence(
        self, *, release_id: str, gate: str = "", limit: int = 1000
    ) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            stmt = select(DeploymentReleaseGateEvidenceRow).where(
                DeploymentReleaseGateEvidenceRow.release_id == _required(release_id, "release_id")
            )
            if gate:
                stmt = stmt.where(DeploymentReleaseGateEvidenceRow.gate == gate)
            rows = session.execute(
                stmt.order_by(
                    DeploymentReleaseGateEvidenceRow.observed_at_ms.desc(),
                    DeploymentReleaseGateEvidenceRow.created_at.desc(),
                ).limit(max(1, int(limit)))
            ).scalars().all()
            return [self._gate_evidence_dict(row) for row in rows]

    def heartbeat(self, process: dict[str, Any]) -> dict[str, Any]:
        payload = dict(process or {})
        process_id = _required(payload.get("process_id"), "process_id")
        with self.session_factory.begin() as session:
            row = session.get(DeploymentProcessHeartbeatRow, process_id)
            if row is None:
                row = DeploymentProcessHeartbeatRow(process_id=process_id)
                session.add(row)
            row.role = _required(payload.get("role"), "role")
            row.release_id = str(payload.get("release_id") or "")
            row.status = _required(payload.get("status"), "status")
            row.metadata_json = _json(payload.get("metadata"))
            row.last_seen_ms = int(payload.get("last_seen_ms") or _now_ms())
            session.flush()
            return self._heartbeat_dict(row)

    def list_heartbeats(self, *, role: str = "", since_ms: int = 0, limit: int = 1000) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            stmt = select(DeploymentProcessHeartbeatRow)
            if role:
                stmt = stmt.where(DeploymentProcessHeartbeatRow.role == role)
            if since_ms:
                stmt = stmt.where(DeploymentProcessHeartbeatRow.last_seen_ms >= int(since_ms))
            rows = session.execute(stmt.order_by(DeploymentProcessHeartbeatRow.last_seen_ms.desc()).limit(max(1, int(limit)))).scalars().all()
            return [self._heartbeat_dict(row) for row in rows]

    @staticmethod
    def _release_dict(row: DeploymentReleaseRow) -> dict[str, Any]:
        return {"release_id": row.release_id, "version": row.version, "git_sha": row.git_sha, "image_digest": row.image_digest,
                "status": row.status, "manifest": dict(row.manifest or {}), "created_at": row.created_at.isoformat() if row.created_at else "",
                "promoted_at": row.promoted_at.isoformat() if row.promoted_at else ""}

    @staticmethod
    def _gate_evidence_dict(row: DeploymentReleaseGateEvidenceRow) -> dict[str, Any]:
        return {
            "evidence_id": row.evidence_id,
            "release_id": row.release_id,
            "gate": row.gate,
            "status": row.status,
            "observed_at_ms": row.observed_at_ms,
            "expires_at_ms": row.expires_at_ms,
            "source": row.source,
            "evidence_sha256": row.evidence_sha256,
            "details": dict(row.details or {}),
            "artifact_reference": dict(row.artifact_reference or {}),
            "created_at": row.created_at.isoformat() if row.created_at else "",
        }

    @staticmethod
    def _heartbeat_dict(row: DeploymentProcessHeartbeatRow) -> dict[str, Any]:
        return {"process_id": row.process_id, "role": row.role, "release_id": row.release_id, "status": row.status,
                "metadata": dict(row.metadata_json or {}), "last_seen_ms": row.last_seen_ms,
                "updated_at": row.updated_at.isoformat() if row.updated_at else ""}


class StoryStore:
    def __init__(self, session_factory: sessionmaker) -> None:
        self.session_factory = session_factory

    def upsert_story(
        self,
        story_id: str,
        *,
        series_id: str = "",
        book_id: str = "",
        title: str = "",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self.session_factory() as session:
            row = session.get(StoryRow, story_id)
            if row is None:
                row = StoryRow(story_id=story_id, series_id=series_id, book_id=book_id, title=title, payload=_json(payload))
                session.add(row)
            else:
                row.series_id = series_id
                row.book_id = book_id
                row.title = title
                row.payload = _json(payload)
            session.commit()
            return self._story_dict(row)

    def list_stories(self, *, series_id: str | None = None, book_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            stmt = select(StoryRow)
            if series_id:
                stmt = stmt.where(StoryRow.series_id == series_id)
            if book_id:
                stmt = stmt.where(StoryRow.book_id == book_id)
            rows = session.execute(stmt.order_by(StoryRow.updated_at.desc())).scalars().all()
            return [self._story_dict(row) for row in rows[:limit]]

    @staticmethod
    def _story_dict(row: StoryRow) -> dict[str, Any]:
        return {
            "story_id": row.story_id,
            "series_id": row.series_id,
            "book_id": row.book_id,
            "title": row.title,
            "payload": dict(row.payload or {}),
            "updated_at": row.updated_at.isoformat() if row.updated_at else "",
        }


class AudiobookStore:
    def __init__(self, session_factory: sessionmaker) -> None:
        self.session_factory = session_factory

    def upsert_run(
        self,
        run_id: str,
        *,
        series_id: str = "",
        book_id: str = "",
        title: str = "",
        status: str = "staged",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self.session_factory() as session:
            row = session.get(AudiobookRunRow, run_id)
            if row is None:
                row = AudiobookRunRow(
                    run_id=run_id,
                    series_id=series_id,
                    book_id=book_id,
                    title=title,
                    status=status,
                    payload=_json(payload),
                )
                session.add(row)
            else:
                row.series_id = series_id
                row.book_id = book_id
                row.title = title
                row.status = status
                row.payload = _json(payload)
            session.commit()
            return self.get_run(run_id) or {}

    def upsert_chapter(
        self,
        chapter_id: str,
        *,
        run_id: str,
        book_index: int,
        chapter_index: int,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self.session_factory() as session:
            row = session.get(AudiobookChapterRow, chapter_id)
            if row is None:
                row = AudiobookChapterRow(
                    chapter_id=chapter_id,
                    run_id=run_id,
                    book_index=book_index,
                    chapter_index=chapter_index,
                    payload=_json(payload),
                )
                session.add(row)
            else:
                row.run_id = run_id
                row.book_index = book_index
                row.chapter_index = chapter_index
                row.payload = _json(payload)
            session.commit()
            return self._chapter_dict(row)

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self.session_factory() as session:
            row = session.get(AudiobookRunRow, run_id)
            if row is None:
                return None
            chapters = session.execute(
                select(AudiobookChapterRow)
                .where(AudiobookChapterRow.run_id == run_id)
                .order_by(AudiobookChapterRow.book_index.asc(), AudiobookChapterRow.chapter_index.asc())
            ).scalars().all()
            payload = self._run_dict(row)
            payload["chapters"] = [self._chapter_dict(item) for item in chapters]
            return payload

    def list_runs(self, *, series_id: str | None = None, book_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            stmt = select(AudiobookRunRow)
            if series_id:
                stmt = stmt.where(AudiobookRunRow.series_id == series_id)
            if book_id:
                stmt = stmt.where(AudiobookRunRow.book_id == book_id)
            rows = session.execute(stmt.order_by(AudiobookRunRow.updated_at.desc())).scalars().all()
            return [self._run_dict(row) for row in rows[:limit]]

    @staticmethod
    def _run_dict(row: AudiobookRunRow) -> dict[str, Any]:
        return {
            "run_id": row.run_id,
            "series_id": row.series_id,
            "book_id": row.book_id,
            "title": row.title,
            "status": row.status,
            "payload": dict(row.payload or {}),
            "updated_at": row.updated_at.isoformat() if row.updated_at else "",
        }

    @staticmethod
    def _chapter_dict(row: AudiobookChapterRow) -> dict[str, Any]:
        return {
            "chapter_id": row.chapter_id,
            "run_id": row.run_id,
            "book_index": row.book_index,
            "chapter_index": row.chapter_index,
            "payload": dict(row.payload or {}),
            "updated_at": row.updated_at.isoformat() if row.updated_at else "",
        }


class VectorDocumentStore:
    def __init__(self, engine: Engine, *, table_name: str = "vector_documents", metric: str = "cosine", provider_label: str = "supabase") -> None:
        self.engine = engine
        self.table_name = table_name
        self.metric = metric
        self.provider_label = str(provider_label or "supabase").strip() or "supabase"

    def initialize(self) -> None:
        inspector = inspect(self.engine)
        if inspector.has_table(self.table_name):
            return
        if self.engine.dialect.name == "postgresql":
            with self.engine.begin() as conn:
                conn.execute(text("create extension if not exists vector"))
                conn.execute(
                    text(
                        f"""
                        create table if not exists {self.table_name} (
                          id bigserial primary key,
                          namespace text not null,
                          document_id text not null,
                          content text not null default '',
                          summary text not null default '',
                          metadata jsonb not null default '{{}}'::jsonb,
                          embedding vector not null,
                          updated_at timestamptz not null default now(),
                          constraint uq_{self.table_name}_namespace_document unique (namespace, document_id)
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        f"create index if not exists ix_{self.table_name}_namespace on {self.table_name} (namespace)"
                    )
                )
            return
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    f"""
                    create table if not exists {self.table_name} (
                      id integer primary key autoincrement,
                      namespace text not null,
                      document_id text not null,
                      content text not null default '',
                      summary text not null default '',
                      metadata_json text not null default '{{}}',
                      embedding_json text not null,
                      updated_at text not null default current_timestamp,
                      unique(namespace, document_id)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    f"create index if not exists ix_{self.table_name}_namespace on {self.table_name} (namespace)"
                )
            )

    def upsert_documents(self, namespace: str, documents: list[dict[str, Any]]) -> dict[str, Any]:
        namespace_value = validate_vector_namespace(namespace)
        normalized_documents = [validate_vector_document_contract(namespace_value, document) for document in documents]
        if self.engine.dialect.name == "postgresql":
            with self.engine.begin() as conn:
                for document in normalized_documents:
                    conn.execute(
                        text(
                            f"""
                            insert into {self.table_name} (namespace, document_id, content, summary, metadata, embedding, updated_at)
                            values (
                              :namespace,
                              :document_id,
                              :content,
                              :summary,
                              cast(:metadata as jsonb),
                              cast(:embedding as vector),
                              now()
                            )
                            on conflict (namespace, document_id) do update set
                              content = excluded.content,
                              summary = excluded.summary,
                              metadata = excluded.metadata,
                              embedding = excluded.embedding,
                              updated_at = now()
                            """
                        ),
                        {
                            "namespace": namespace_value,
                            "document_id": str(document.get("document_id") or "").strip(),
                            "content": str(document.get("content") or document.get("text") or ""),
                            "summary": str(document.get("summary") or ""),
                            "metadata": json.dumps(document.get("metadata") or {}),
                            "embedding": _vector_literal([float(value) for value in (document.get("embedding") or [])]),
                        },
                    )
            return {"namespace": namespace_value, "document_count": len(normalized_documents), "provider": self.provider_label}
        with self.engine.begin() as conn:
            for document in normalized_documents:
                conn.execute(
                    text(
                        f"""
                        insert into {self.table_name} (namespace, document_id, content, summary, metadata_json, embedding_json, updated_at)
                        values (:namespace, :document_id, :content, :summary, :metadata_json, :embedding_json, current_timestamp)
                        on conflict(namespace, document_id) do update set
                          content = excluded.content,
                          summary = excluded.summary,
                          metadata_json = excluded.metadata_json,
                          embedding_json = excluded.embedding_json,
                          updated_at = current_timestamp
                        """
                    ),
                    {
                        "namespace": namespace_value,
                        "document_id": str(document.get("document_id") or "").strip(),
                        "content": str(document.get("content") or document.get("text") or ""),
                        "summary": str(document.get("summary") or ""),
                        "metadata_json": json.dumps(document.get("metadata") or {}),
                        "embedding_json": json.dumps([float(value) for value in (document.get("embedding") or [])]),
                    },
                )
        return {"namespace": namespace_value, "document_count": len(normalized_documents), "provider": self.provider_label}

    def list_documents(
        self,
        namespace: str,
        *,
        metadata_filters: dict[str, Any] | None = None,
        limit: int = 10000,
    ) -> list[dict[str, Any]]:
        namespace_value = validate_vector_namespace(namespace)
        filters = dict(metadata_filters or {})
        if self.engine.dialect.name == "postgresql":
            sql = f"""
                select
                  namespace,
                  document_id,
                  content,
                  summary,
                  metadata,
                  embedding::text as embedding_text
                from {self.table_name}
                where namespace = :namespace
            """
            params: dict[str, Any] = {
                "namespace": namespace_value,
                "limit": max(1, int(limit)),
            }
            if filters:
                sql += " and metadata @> cast(:filters as jsonb)"
                params["filters"] = json.dumps(filters)
            sql += " order by document_id asc limit :limit"
            with self.engine.begin() as conn:
                rows = conn.execute(text(sql), params).mappings().all()
            return [
                {
                    "namespace": row["namespace"],
                    "document_id": row["document_id"],
                    "content": row["content"],
                    "summary": row["summary"],
                    "metadata": dict(row["metadata"] or {}),
                    "embedding": self._parse_embedding_text(str(row["embedding_text"] or "")),
                }
                for row in rows
            ]

        with self.engine.begin() as conn:
            rows = conn.execute(
                text(
                    f"""
                    select namespace, document_id, content, summary, metadata_json, embedding_json
                    from {self.table_name}
                    where namespace = :namespace
                    order by document_id asc
                    """
                ),
                {"namespace": namespace_value},
            ).mappings().all()
        documents: list[dict[str, Any]] = []
        for row in rows:
            metadata = json.loads(str(row["metadata_json"] or "{}"))
            if any(metadata.get(key) != value for key, value in filters.items()):
                continue
            documents.append(
                {
                    "namespace": row["namespace"],
                    "document_id": row["document_id"],
                    "content": row["content"],
                    "summary": row["summary"],
                    "metadata": metadata,
                    "embedding": [float(value) for value in json.loads(str(row["embedding_json"] or "[]"))],
                }
            )
            if len(documents) >= max(1, int(limit)):
                break
        return documents

    def query_documents(
        self,
        namespace: str,
        *,
        query_vector: list[float],
        top_k: int = 6,
        metadata_filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        namespace_value = validate_vector_namespace(namespace)
        filters = dict(metadata_filters or {})
        if self.engine.dialect.name == "postgresql":
            sql = f"""
                select
                  namespace,
                  document_id,
                  content,
                  summary,
                  metadata,
                  1 - (embedding <=> cast(:query_vector as vector)) as score
                from {self.table_name}
                where namespace = :namespace
            """
            params: dict[str, Any] = {
                "namespace": namespace_value,
                "query_vector": _vector_literal([float(value) for value in query_vector]),
                "top_k": max(1, int(top_k)),
            }
            if filters:
                sql += " and metadata @> cast(:filters as jsonb)"
                params["filters"] = json.dumps(filters)
            sql += " order by embedding <=> cast(:query_vector as vector) limit :top_k"
            with self.engine.begin() as conn:
                rows = conn.execute(text(sql), params).mappings().all()
            return [
                {
                    "namespace": row["namespace"],
                    "document_id": row["document_id"],
                    "content": row["content"],
                    "summary": row["summary"],
                    "metadata": dict(row["metadata"] or {}),
                    "score": float(row["score"] or 0.0),
                }
                for row in rows
            ]

        with self.engine.begin() as conn:
            rows = conn.execute(
                text(
                    f"select namespace, document_id, content, summary, metadata_json, embedding_json from {self.table_name} where namespace = :namespace"
                ),
                {"namespace": namespace_value},
            ).mappings().all()
        candidates: list[dict[str, Any]] = []
        for row in rows:
            metadata = json.loads(str(row["metadata_json"] or "{}"))
            if any(metadata.get(key) != value for key, value in filters.items()):
                continue
            embedding = [float(value) for value in json.loads(str(row["embedding_json"] or "[]"))]
            candidates.append(
                {
                    "namespace": row["namespace"],
                    "document_id": row["document_id"],
                    "content": row["content"],
                    "summary": row["summary"],
                    "metadata": metadata,
                    "score": _cosine_similarity(query_vector, embedding),
                }
            )
        candidates.sort(key=lambda item: item["score"], reverse=True)
        return candidates[: max(1, int(top_k))]

    def delete_documents(self, namespace: str, document_ids: list[str] | None = None) -> dict[str, Any]:
        namespace_value = validate_vector_namespace(namespace)
        ids = [str(value).strip() for value in (document_ids or []) if str(value).strip()]
        sql = f"delete from {self.table_name} where namespace = :namespace"
        params: dict[str, Any] = {"namespace": namespace_value}
        if ids:
            if self.engine.dialect.name == "postgresql":
                sql += " and document_id = any(:document_ids)"
                params["document_ids"] = ids
            else:
                placeholders = ", ".join(f":doc_{index}" for index, _ in enumerate(ids))
                sql += f" and document_id in ({placeholders})"
                for index, value in enumerate(ids):
                    params[f"doc_{index}"] = value
        with self.engine.begin() as conn:
            result = conn.execute(text(sql), params)
        return {"namespace": namespace_value, "deleted_count": int(result.rowcount or 0)}

    @staticmethod
    def _parse_embedding_text(value: str) -> list[float]:
        raw = str(value or "").strip()
        if not raw:
            return []
        if raw.startswith("[") and raw.endswith("]"):
            raw = raw[1:-1]
        if not raw:
            return []
        return [float(item.strip()) for item in raw.split(",") if item.strip()]


class LocalObjectStorageStore:
    def __init__(self, root_dir: str) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_root_dir = (self.root_dir / ".runtime_metadata").resolve()
        self.metadata_root_dir.mkdir(parents=True, exist_ok=True)

    def ensure_bucket(self, bucket_name: str, *, public: bool = False) -> dict[str, Any]:
        target = self._resolve_bucket(bucket_name)
        target.mkdir(parents=True, exist_ok=True)
        return {"bucket_name": bucket_name, "public": bool(public), "exists": target.exists(), "provider": "local"}

    def upload_bytes(
        self,
        bucket_name: str,
        object_path: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
        upsert: bool = True,
    ) -> dict[str, Any]:
        target = self._resolve_object(bucket_name, object_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and not upsert:
            raise FileExistsError(f"Object already exists: {bucket_name}/{object_path}")
        target.write_bytes(data)
        payload = {
            "bucket_name": bucket_name,
            "object_path": str(_safe_relative_path(object_path)).replace("\\", "/"),
            "bytes_written": len(data),
            "content_type": content_type,
            "provider": "local",
        }
        self._write_metadata(bucket_name, object_path, payload)
        return payload

    def upload_text(
        self,
        bucket_name: str,
        object_path: str,
        text: str,
        *,
        content_type: str = "text/plain; charset=utf-8",
        upsert: bool = True,
    ) -> dict[str, Any]:
        return self.upload_bytes(bucket_name, object_path, str(text or "").encode("utf-8"), content_type=content_type, upsert=upsert)

    def upload_json(self, bucket_name: str, object_path: str, payload: dict[str, Any], *, upsert: bool = True) -> dict[str, Any]:
        return self.upload_bytes(
            bucket_name,
            object_path,
            json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
            content_type="application/json",
            upsert=upsert,
        )

    def download_bytes(self, bucket_name: str, object_path: str) -> bytes:
        return self._resolve_object(bucket_name, object_path).read_bytes()

    def download_text(self, bucket_name: str, object_path: str, *, encoding: str = "utf-8") -> str:
        return self.download_bytes(bucket_name, object_path).decode(encoding)

    def get_object_info(self, bucket_name: str, object_path: str) -> dict[str, Any]:
        target = self._resolve_object(bucket_name, object_path)
        if not target.exists():
            raise FileNotFoundError(f"Object not found: {bucket_name}/{object_path}")
        relative = str(_safe_relative_path(object_path)).replace("\\", "/")
        metadata = self._read_metadata(bucket_name, object_path)
        return {
            "bucket_name": bucket_name,
            "object_path": relative,
            "name": target.name,
            "size": target.stat().st_size,
            "content_type": str(metadata.get("content_type") or "").strip(),
            "provider": "local",
        }

    def list_objects(self, bucket_name: str, *, prefix: str = "", limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        bucket_dir = self._resolve_bucket(bucket_name)
        if not bucket_dir.exists():
            return []
        prefix_text = str(_safe_relative_path(prefix)).replace("\\", "/") if str(prefix or "").strip() else ""
        results: list[dict[str, Any]] = []
        for path in sorted(bucket_dir.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(bucket_dir).as_posix()
            if prefix_text and not relative.startswith(prefix_text):
                continue
            metadata = self._read_metadata(bucket_name, relative)
            results.append(
                {
                    "name": Path(relative).name,
                    "path": relative,
                    "size": path.stat().st_size,
                    "content_type": str(metadata.get("content_type") or "").strip(),
                    "provider": "local",
                }
            )
        return results[offset: offset + max(1, int(limit))]

    def delete_object(self, bucket_name: str, object_path: str) -> dict[str, Any]:
        target = self._resolve_object(bucket_name, object_path)
        existed = target.exists()
        if existed:
            target.unlink()
        metadata_path = self._resolve_metadata_path(bucket_name, object_path)
        if metadata_path.exists():
            metadata_path.unlink()
        return {"bucket_name": bucket_name, "object_path": str(_safe_relative_path(object_path)).replace("\\", "/"), "deleted": existed, "provider": "local"}

    def _resolve_bucket(self, bucket_name: str) -> Path:
        safe_bucket = str(bucket_name or "").strip()
        if not safe_bucket:
            raise ValueError("bucket_name is required")
        target = (self.root_dir / safe_bucket).resolve()
        target.relative_to(self.root_dir)
        return target

    def _resolve_object(self, bucket_name: str, object_path: str) -> Path:
        bucket_dir = self._resolve_bucket(bucket_name)
        relative = _safe_relative_path(object_path)
        target = (bucket_dir / relative).resolve()
        target.relative_to(bucket_dir)
        return target

    def _resolve_metadata_path(self, bucket_name: str, object_path: str) -> Path:
        bucket_dir = (self.metadata_root_dir / self._resolve_bucket(bucket_name).name).resolve()
        bucket_dir.mkdir(parents=True, exist_ok=True)
        relative = _safe_relative_path(object_path)
        target = (bucket_dir / relative).resolve()
        target.relative_to(bucket_dir)
        return target.with_suffix(f"{target.suffix}.metadata.json")

    def _write_metadata(self, bucket_name: str, object_path: str, payload: dict[str, Any]) -> None:
        metadata_path = self._resolve_metadata_path(bucket_name, object_path)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_metadata(self, bucket_name: str, object_path: str) -> dict[str, Any]:
        metadata_path = self._resolve_metadata_path(bucket_name, object_path)
        if not metadata_path.exists():
            return {}
        try:
            return json.loads(metadata_path.read_text(encoding="utf-8"))
        except Exception:
            return {}


class SupabaseObjectStorageStore:
    def __init__(self, *, base_url: str, service_role_key: str, timeout_seconds: int = 60) -> None:
        self.base_url = str(base_url or "").rstrip("/")
        self.service_role_key = str(service_role_key or "").strip()
        self.timeout_seconds = max(5, int(timeout_seconds))
        if not self.base_url:
            raise ValueError("Supabase storage API URL is required.")
        if not self.service_role_key:
            raise ValueError("Supabase service role key is required for storage operations.")

    def ensure_bucket(self, bucket_name: str, *, public: bool = False) -> dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/bucket",
            headers={**self._auth_headers(), "Content-Type": "application/json"},
            json={"name": bucket_name, "public": bool(public)},
            timeout=self.timeout_seconds,
        )
        if response.status_code == 400:
            payload = self._json(response)
            if str(payload.get("statusCode") or "") == "409" or "already exists" in str(payload.get("message") or "").lower():
                return {"bucket_name": bucket_name, "public": bool(public), "exists": True, "provider": "supabase"}
        response.raise_for_status()
        return {"bucket_name": bucket_name, "public": bool(public), "exists": True, "provider": "supabase"}

    def upload_bytes(
        self,
        bucket_name: str,
        object_path: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
        upsert: bool = True,
    ) -> dict[str, Any]:
        path = str(_safe_relative_path(object_path)).replace("\\", "/")
        response = requests.post(
            f"{self.base_url}/object/{bucket_name}/{path}",
            headers={**self._auth_headers(), "Content-Type": content_type, "x-upsert": "true" if upsert else "false"},
            data=data,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = self._json(response)
        return {
            "bucket_name": bucket_name,
            "object_path": path,
            "bytes_written": len(data),
            "content_type": content_type,
            "key": payload.get("Key", ""),
            "id": payload.get("Id", ""),
            "provider": "supabase",
        }

    def upload_text(
        self,
        bucket_name: str,
        object_path: str,
        text: str,
        *,
        content_type: str = "text/plain; charset=utf-8",
        upsert: bool = True,
    ) -> dict[str, Any]:
        return self.upload_bytes(bucket_name, object_path, str(text or "").encode("utf-8"), content_type=content_type, upsert=upsert)

    def upload_json(self, bucket_name: str, object_path: str, payload: dict[str, Any], *, upsert: bool = True) -> dict[str, Any]:
        return self.upload_bytes(
            bucket_name,
            object_path,
            json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
            content_type="application/json",
            upsert=upsert,
        )

    def download_bytes(self, bucket_name: str, object_path: str) -> bytes:
        path = str(_safe_relative_path(object_path)).replace("\\", "/")
        response = requests.get(
            f"{self.base_url}/object/authenticated/{bucket_name}/{path}",
            headers=self._auth_headers(),
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.content

    def download_text(self, bucket_name: str, object_path: str, *, encoding: str = "utf-8") -> str:
        return self.download_bytes(bucket_name, object_path).decode(encoding)

    def get_object_info(self, bucket_name: str, object_path: str) -> dict[str, Any]:
        path = str(_safe_relative_path(object_path)).replace("\\", "/")
        rows = self.list_objects(bucket_name, prefix=path, limit=1, offset=0)
        row = rows[0] if rows and str((rows[0] or {}).get("path") or "") == path else {}
        metadata = dict(row.get("metadata") or {}) if isinstance(row, dict) else {}
        content_type = (
            str(row.get("content_type") or "").strip()
            or str(metadata.get("mimetype") or "").strip()
            or str(metadata.get("contentType") or "").strip()
        )
        return {
            "bucket_name": bucket_name,
            "object_path": path,
            "name": str(row.get("name") or Path(path).name),
            "size": int(row.get("size") or 0),
            "content_type": content_type,
            "provider": "supabase",
            "metadata": metadata,
        }

    def list_objects(self, bucket_name: str, *, prefix: str = "", limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        prefix_text = str(_safe_relative_path(prefix)).replace("\\", "/") if str(prefix or "").strip() else ""
        rows = self._list_recursive(bucket_name)
        normalized: list[dict[str, Any]] = []
        for item in rows:
            row = dict(item or {})
            path = str(row.pop("_path", "") or row.get("path") or row.get("name") or "").strip()
            if prefix_text and not path.startswith(prefix_text):
                continue
            metadata = dict(row.get("metadata") or {}) if isinstance(row.get("metadata"), dict) else {}
            normalized.append(
                dict(
                    row,
                    path=path,
                    content_type=str(row.get("content_type") or "").strip()
                    or str(metadata.get("mimetype") or "").strip()
                    or str(metadata.get("contentType") or "").strip(),
                    metadata=metadata,
                    provider="supabase",
                )
            )
        normalized.sort(key=lambda item: str(item.get("path") or ""))
        start = max(0, int(offset))
        return normalized[start: start + max(1, int(limit))]

    def _list_recursive(self, bucket_name: str) -> list[dict[str, Any]]:
        pending = [""]
        objects: list[dict[str, Any]] = []
        visited: set[str] = set()
        while pending:
            directory = pending.pop()
            if directory in visited:
                continue
            visited.add(directory)
            page_offset = 0
            while True:
                response = requests.post(
                    f"{self.base_url}/object/list/{bucket_name}",
                    headers={**self._auth_headers(), "Content-Type": "application/json"},
                    json={"prefix": directory, "limit": 1000, "offset": page_offset},
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                payload = self._json(response)
                page = payload if isinstance(payload, list) else []
                for item in page:
                    row = dict(item or {})
                    name = str(row.get("name") or "").strip().strip("/")
                    if not name:
                        continue
                    path = f"{directory.rstrip('/')}/{name}".strip("/")
                    metadata = row.get("metadata")
                    if not row.get("id") and not isinstance(metadata, dict):
                        pending.append(path)
                    else:
                        row["_path"] = path
                        objects.append(row)
                page_offset += len(page)
                if len(page) < 1000:
                    break
        return objects

    def delete_object(self, bucket_name: str, object_path: str) -> dict[str, Any]:
        path = str(_safe_relative_path(object_path)).replace("\\", "/")
        response = requests.delete(
            f"{self.base_url}/object/{bucket_name}/{path}",
            headers=self._auth_headers(),
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = self._json(response)
        return {"bucket_name": bucket_name, "object_path": path, "message": payload.get("message", ""), "provider": "supabase"}

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.service_role_key}", "apikey": self.service_role_key}

    @staticmethod
    def _json(response: requests.Response) -> dict[str, Any] | list[Any]:
        try:
            return response.json()
        except Exception:
            return {}
