"""SQLAlchemy schema for the Supabase/Postgres persistence runtime."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class ProviderConfigRow(Base):
    __tablename__ = "provider_configs"

    provider_name: Mapped[str] = mapped_column(String(120), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ProviderStatusRow(Base):
    __tablename__ = "provider_statuses"
    __table_args__ = (
        UniqueConstraint("provider_name", "label", name="uq_provider_status_provider_label"),
        Index("ix_provider_status_provider", "provider_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider_name: Mapped[str] = mapped_column(String(120), nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class LibrarySeriesRow(Base):
    __tablename__ = "library_series"

    series_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class LibraryBookRow(Base):
    __tablename__ = "library_books"
    __table_args__ = (
        Index("ix_library_books_series", "series_id", "book_index"),
    )

    book_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    series_id: Mapped[str] = mapped_column(ForeignKey("library_series.series_id", ondelete="SET NULL"), default="")
    title: Mapped[str] = mapped_column(String(255), default="")
    book_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_uri: Mapped[str] = mapped_column(Text, default="")
    source_type: Mapped[str] = mapped_column(String(64), default="")
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class LibrarySceneRow(Base):
    __tablename__ = "library_scenes"
    __table_args__ = (
        UniqueConstraint("book_id", "chapter_index", "scene_index", name="uq_library_scenes_position"),
        Index("ix_library_scenes_book", "book_id", "chapter_index", "scene_index"),
    )

    scene_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    book_id: Mapped[str] = mapped_column(ForeignKey("library_books.book_id", ondelete="CASCADE"), nullable=False)
    chapter_index: Mapped[int] = mapped_column(Integer, nullable=False)
    scene_index: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="")
    text: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class LibraryRecordRow(Base):
    __tablename__ = "library_records"
    __table_args__ = (
        Index("ix_library_records_scope", "record_type", "series_id", "book_id", "scene_id"),
    )

    record_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    record_type: Mapped[str] = mapped_column(String(64), nullable=False)
    series_id: Mapped[str] = mapped_column(String(120), default="")
    book_id: Mapped[str] = mapped_column(String(120), default="")
    scene_id: Mapped[str] = mapped_column(String(120), default="")
    title: Mapped[str] = mapped_column(String(255), default="")
    ordinal: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class IdentitySeriesRow(Base):
    __tablename__ = "identity_series"

    series_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    provider_name: Mapped[str] = mapped_column(String(120), default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class JobRow(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_type_status", "job_type", "status"),
    )

    job_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    job_type: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class JobLogRow(Base):
    __tablename__ = "job_logs"
    __table_args__ = (
        Index("ix_job_logs_job", "job_id", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.job_id", ondelete="CASCADE"), nullable=False)
    stage: Mapped[str] = mapped_column(String(120), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ExecutionQueuePolicyRow(Base):
    __tablename__ = "execution_queue_policies"

    queue_name: Mapped[str] = mapped_column(String(120), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ExecutionQueueRow(Base):
    __tablename__ = "execution_queue"
    __table_args__ = (
        UniqueConstraint("run_id", name="uq_execution_queue_run"),
        Index("ix_execution_queue_claim", "queue_name", "status", "available_at_ms", "priority"),
        Index("ix_execution_queue_series", "queue_name", "series_id", "status"),
        Index("ix_execution_queue_lease", "status", "lease_expires_at_ms"),
    )

    queue_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(160), nullable=False)
    queue_name: Mapped[str] = mapped_column(String(120), nullable=False)
    series_id: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="queued")
    priority: Mapped[int] = mapped_column(Integer, default=0)
    capabilities: Mapped[list] = mapped_column(JSON, default=list)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    available_at_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    lease_owner: Mapped[str] = mapped_column(String(160), default="")
    lease_token: Mapped[str] = mapped_column(String(160), default="")
    lease_expires_at_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    heartbeat_at_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    cancellation_requested_at_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    backoff_seconds: Mapped[int] = mapped_column(Integer, default=5)
    last_error: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ExecutionTelemetryRow(Base):
    __tablename__ = "execution_telemetry"
    __table_args__ = (
        Index("ix_execution_telemetry_run", "run_id", "id"),
        Index("ix_execution_telemetry_queue", "queue_name", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    queue_name: Mapped[str] = mapped_column(String(120), default="")
    queue_id: Mapped[str] = mapped_column(String(160), default="")
    run_id: Mapped[str] = mapped_column(String(160), default="")
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="")
    worker_id: Mapped[str] = mapped_column(String(160), default="")
    timestamp_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class ObservabilityRecordRow(Base):
    __tablename__ = "observability_records"
    __table_args__ = (
        Index("ix_observability_time", "kind", "timestamp_ms"),
        Index("ix_observability_run", "run_id", "timestamp_ms"),
        Index("ix_observability_metric", "name", "timestamp_ms"),
        Index("ix_observability_component", "component", "provider", "timestamp_ms"),
    )

    observation_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    timestamp_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    run_id: Mapped[str] = mapped_column(String(160), default="")
    series_id: Mapped[str] = mapped_column(String(120), default="")
    component: Mapped[str] = mapped_column(String(120), default="")
    stage: Mapped[str] = mapped_column(String(120), default="")
    provider: Mapped[str] = mapped_column(String(120), default="")
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="")
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(32), default="")
    dimensions: Mapped[dict] = mapped_column(JSON, default=dict)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UsageLedgerRow(Base):
    __tablename__ = "usage_ledger"
    __table_args__ = (
        Index("ix_usage_ledger_run", "run_id", "timestamp_ms"),
        Index("ix_usage_ledger_project", "project_id", "timestamp_ms"),
        Index("ix_usage_ledger_provider", "provider", "account_alias", "timestamp_ms"),
        Index("ix_usage_ledger_reservation", "reservation_id", "entry_kind"),
    )

    entry_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    reservation_id: Mapped[str] = mapped_column(String(160), nullable=False)
    entry_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    timestamp_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expires_at_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    release_id: Mapped[str] = mapped_column(String(160), default="")
    project_id: Mapped[str] = mapped_column(String(160), default="")
    run_id: Mapped[str] = mapped_column(String(160), default="")
    series_id: Mapped[str] = mapped_column(String(120), default="")
    stage: Mapped[str] = mapped_column(String(120), default="")
    agent: Mapped[str] = mapped_column(String(120), default="")
    component: Mapped[str] = mapped_column(String(120), default="")
    provider: Mapped[str] = mapped_column(String(120), default="")
    account_alias: Mapped[str] = mapped_column(String(160), default="")
    model: Mapped[str] = mapped_column(String(160), default="")
    operation: Mapped[str] = mapped_column(String(120), default="")
    request_count: Mapped[float] = mapped_column(Float, default=0.0)
    input_tokens: Mapped[float] = mapped_column(Float, default=0.0)
    output_tokens: Mapped[float] = mapped_column(Float, default=0.0)
    cached_input_tokens: Mapped[float] = mapped_column(Float, default=0.0)
    compute_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    image_count: Mapped[float] = mapped_column(Float, default=0.0)
    audio_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    cost_status: Mapped[str] = mapped_column(String(32), default="unpriced")
    pricing_version: Mapped[str] = mapped_column(String(80), default="")
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UsageBudgetPolicyRow(Base):
    __tablename__ = "usage_budget_policies"
    __table_args__ = (Index("ix_usage_budget_scope", "scope_type", "scope_value", "enabled"),)

    policy_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_value: Mapped[str] = mapped_column(String(160), default="")
    window_seconds: Mapped[int] = mapped_column(Integer, default=0)
    limits: Mapped[dict] = mapped_column(JSON, default=dict)
    hard_limit: Mapped[bool] = mapped_column(default=True)
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class DeploymentReleaseRow(Base):
    __tablename__ = "deployment_releases"
    __table_args__ = (Index("ix_deployment_releases_status", "status", "created_at"),)

    release_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    git_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    image_digest: Mapped[str] = mapped_column(String(160), default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    manifest: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DeploymentReleaseGateEvidenceRow(Base):
    __tablename__ = "deployment_release_gate_evidence"
    __table_args__ = (
        Index("ix_deployment_release_gate_latest", "release_id", "gate", "observed_at_ms"),
    )

    evidence_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    release_id: Mapped[str] = mapped_column(
        String(160), ForeignKey("deployment_releases.release_id", ondelete="RESTRICT"), nullable=False
    )
    gate: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    observed_at_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expires_at_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    source: Mapped[str] = mapped_column(String(160), nullable=False)
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    artifact_reference: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DeploymentProcessHeartbeatRow(Base):
    __tablename__ = "deployment_process_heartbeats"
    __table_args__ = (Index("ix_deployment_heartbeats_role", "role", "last_seen_ms"),)

    process_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    release_id: Mapped[str] = mapped_column(String(160), default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    last_seen_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class StageLineageRow(Base):
    __tablename__ = "stage_lineage_records"
    __table_args__ = (
        Index("ix_stage_lineage_run", "run_id", "stage", "created_at"),
        Index("ix_stage_lineage_match", "series_id", "stage", "input_fingerprint", "status"),
        Index("ix_stage_lineage_output", "series_id", "stage", "output_fingerprint"),
    )

    execution_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(160), nullable=False)
    series_id: Mapped[str] = mapped_column(String(120), nullable=False)
    stage: Mapped[str] = mapped_column(String(120), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(64), default="executed")
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    output_fingerprint: Mapped[str] = mapped_column(String(64), default="")
    lineage_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_fingerprints: Mapped[dict] = mapped_column(JSON, default=dict)
    versions: Mapped[dict] = mapped_column(JSON, default=dict)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class StoryRow(Base):
    __tablename__ = "generated_stories"
    __table_args__ = (
        Index("ix_generated_stories_scope", "series_id", "book_id"),
    )

    story_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    series_id: Mapped[str] = mapped_column(String(120), default="")
    book_id: Mapped[str] = mapped_column(String(120), default="")
    title: Mapped[str] = mapped_column(String(255), default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AudiobookRunRow(Base):
    __tablename__ = "audiobook_runs"
    __table_args__ = (
        Index("ix_audiobook_runs_scope", "series_id", "book_id", "status"),
    )

    run_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    series_id: Mapped[str] = mapped_column(String(120), default="")
    book_id: Mapped[str] = mapped_column(String(120), default="")
    title: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(64), default="staged")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AudiobookChapterRow(Base):
    __tablename__ = "audiobook_chapters"
    __table_args__ = (
        UniqueConstraint("run_id", "book_index", "chapter_index", name="uq_audiobook_chapter_position"),
        Index("ix_audiobook_chapters_run", "run_id", "book_index", "chapter_index"),
    )

    chapter_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("audiobook_runs.run_id", ondelete="CASCADE"), nullable=False)
    book_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chapter_index: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
