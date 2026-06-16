from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON


def _uuid() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Series(Base, TimestampMixin):
    __tablename__ = "series"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    series_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    title: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class PipelineRun(Base, TimestampMixin):
    __tablename__ = "pipeline_runs"
    __table_args__ = (UniqueConstraint("series_id", "run_id", name="uq_pipeline_runs_series_run"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    series_id: Mapped[str] = mapped_column(String(255), index=True)
    run_id: Mapped[str] = mapped_column(String(255), index=True)
    series_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_dir: Mapped[str | None] = mapped_column(Text, nullable=True)
    log_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    command_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    worker_pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at_utc: Mapped[str | None] = mapped_column(String(64), nullable=True)
    finished_at_utc: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latest_progress_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    status_payload_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class PipelineRunBook(Base, TimestampMixin):
    __tablename__ = "pipeline_run_books"
    __table_args__ = (UniqueConstraint("pipeline_run_id", "book_index", name="uq_pipeline_run_books_run_book"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    pipeline_run_id: Mapped[str] = mapped_column(ForeignKey("pipeline_runs.id"), index=True)
    series_id: Mapped[str] = mapped_column(String(255), index=True)
    run_id: Mapped[str] = mapped_column(String(255), index=True)
    book_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    phase: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    scenes_processed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_scenes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failed_scenes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    successful_scenes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checkpoint_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    contract_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at_utc: Mapped[str | None] = mapped_column(String(64), nullable=True)
    finished_at_utc: Mapped[str | None] = mapped_column(String(64), nullable=True)
    elapsed_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_progress_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    raw_payload_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class DashboardJob(Base, TimestampMixin):
    __tablename__ = "dashboard_jobs"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    job_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    command: Mapped[str | None] = mapped_column(Text, nullable=True)
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    return_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at_utc: Mapped[str | None] = mapped_column(String(64), nullable=True)
    finished_at_utc: Mapped[str | None] = mapped_column(String(64), nullable=True)
    progress_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    request_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    artifacts_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    log_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class DashboardJobLog(Base, TimestampMixin):
    __tablename__ = "dashboard_job_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(ForeignKey("dashboard_jobs.id"), index=True)
    line_index: Mapped[int] = mapped_column(Integer, index=True)
    level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    line_text: Mapped[str] = mapped_column(Text)


class UploadedSource(Base, TimestampMixin):
    __tablename__ = "uploaded_sources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    original_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    stored_path: Mapped[str] = mapped_column(Text, unique=True, index=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    source_kind: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class ProviderConfig(Base, TimestampMixin):
    __tablename__ = "provider_configs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    provider_name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    active_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    transport: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class ProviderAccount(Base, TimestampMixin):
    __tablename__ = "provider_accounts"
    __table_args__ = (UniqueConstraint("provider_name", "label", name="uq_provider_accounts_provider_label"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    provider_name: Mapped[str] = mapped_column(String(64), index=True)
    label: Mapped[str] = mapped_column(String(255), index=True)
    account_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    auth_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    password: Mapped[str | None] = mapped_column(Text, nullable=True)
    account_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    metadata_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class ProviderAccountStatus(Base, TimestampMixin):
    __tablename__ = "provider_account_statuses"
    __table_args__ = (UniqueConstraint("provider_name", "label", name="uq_provider_status_provider_label"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    provider_name: Mapped[str] = mapped_column(String(64), index=True)
    label: Mapped[str] = mapped_column(String(255), index=True)
    probe_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    transport: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolved_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quota_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    remaining_requests_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remaining_input_tokens_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remaining_output_tokens_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remaining_requests_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remaining_tokens_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    credits_remaining: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_checked_at_utc: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class IdentitySeries(Base, TimestampMixin):
    __tablename__ = "identity_series"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    series_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    character_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    alias_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reference_entity_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    narrator_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class IdentityBook(Base, TimestampMixin):
    __tablename__ = "identity_books"
    __table_args__ = (UniqueConstraint("identity_series_id", "book_index", name="uq_identity_books_series_book_index"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    identity_series_id: Mapped[str] = mapped_column(ForeignKey("identity_series.id"), index=True)
    book_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    book_slug: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_dir: Mapped[str | None] = mapped_column(Text, nullable=True)
    pipeline_identity_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_identity_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    clean_identity_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    cleanup_report_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    character_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    alias_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reference_entity_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    suppressed_cluster_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    narrator_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    diagnostics_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class IdentityCharacter(Base, TimestampMixin):
    __tablename__ = "identity_characters"
    __table_args__ = (UniqueConstraint("identity_series_id", "character_id", name="uq_identity_characters_series_character"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    identity_series_id: Mapped[str] = mapped_column(ForeignKey("identity_series.id"), index=True)
    character_id: Mapped[str] = mapped_column(String(255), index=True)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mention_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quote_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_flags: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
    book_sources: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
    payload_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class IdentityAlias(Base, TimestampMixin):
    __tablename__ = "identity_aliases"
    __table_args__ = (UniqueConstraint("identity_series_id", "alias_key", name="uq_identity_aliases_series_alias"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    identity_series_id: Mapped[str] = mapped_column(ForeignKey("identity_series.id"), index=True)
    alias_key: Mapped[str] = mapped_column(Text, index=True)
    target_character_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)


class IdentityReferenceEntity(Base, TimestampMixin):
    __tablename__ = "identity_reference_entities"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    identity_series_id: Mapped[str] = mapped_column(ForeignKey("identity_series.id"), index=True)
    reference_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    aliases: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
    risk_flags: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
    book_sources: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
    payload_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class IdentityNarrator(Base, TimestampMixin):
    __tablename__ = "identity_narrators"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    identity_series_id: Mapped[str] = mapped_column(ForeignKey("identity_series.id"), index=True)
    book_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    book_slug: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    narrator_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class Book(Base, TimestampMixin):
    __tablename__ = "books"
    __table_args__ = (UniqueConstraint("series_id", "book_index", name="uq_books_series_book_index"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    series_fk: Mapped[str | None] = mapped_column(ForeignKey("series.id"), nullable=True)
    series_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    book_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(Text)
    source_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_hash_sha256: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    contract_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    analysis_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    analysis_provider_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    identity_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scene_failure_policy: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scene_analysis_quality: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class Chapter(Base, TimestampMixin):
    __tablename__ = "chapters"
    __table_args__ = (UniqueConstraint("book_id", "chapter_index", name="uq_chapters_book_chapter_index"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    book_id: Mapped[str] = mapped_column(ForeignKey("books.id"), index=True)
    chapter_index: Mapped[int] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class Scene(Base, TimestampMixin):
    __tablename__ = "scenes"
    __table_args__ = (UniqueConstraint("book_id", "chapter_index", "scene_index", name="uq_scenes_book_chapter_scene"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    book_id: Mapped[str] = mapped_column(ForeignKey("books.id"), index=True)
    chapter_id: Mapped[str | None] = mapped_column(ForeignKey("chapters.id"), nullable=True)
    book_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chapter_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scene_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    location_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    location_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_account_alias: Mapped[str | None] = mapped_column(String(128), nullable=True)
    rotation_used: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    rotation_attempt_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    analysis_duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    payload_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class Entity(Base, TimestampMixin):
    __tablename__ = "entities"
    __table_args__ = (UniqueConstraint("book_id", "canonical_name", "entity_type", name="uq_entities_book_name_type"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    book_id: Mapped[str] = mapped_column(ForeignKey("books.id"), index=True)
    canonical_name: Mapped[str] = mapped_column(Text, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    mention_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_seen_book_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_seen_chapter_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_seen_scene_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    entity_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    initial_physical_description: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    first_appearance_profile: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    typed_attributes: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    latest_world_state: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    narrative_roles: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
    descriptions: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
    state_changes: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
    event_links: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
    visual_change_log: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
    analysis_quality_flags: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
    baseline_visual_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_image_bytes: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    metadata_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class CharacterProfile(Base, TimestampMixin):
    __tablename__ = "character_profiles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    book_id: Mapped[str] = mapped_column(ForeignKey("books.id"), index=True)
    entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), nullable=True, index=True)
    character_name: Mapped[str] = mapped_column(Text, index=True)
    payload_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class CharacterVisualBaseline(Base, TimestampMixin):
    __tablename__ = "character_visual_baselines"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    book_id: Mapped[str] = mapped_column(ForeignKey("books.id"), index=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), unique=True, index=True)
    gender_presentation: Mapped[str | None] = mapped_column(Text, nullable=True)
    species_or_race: Mapped[str | None] = mapped_column(Text, nullable=True)
    apparent_age_group: Mapped[str | None] = mapped_column(Text, nullable=True)
    height_impression: Mapped[str | None] = mapped_column(Text, nullable=True)
    build: Mapped[str | None] = mapped_column(Text, nullable=True)
    skin_tone_or_complexion: Mapped[str | None] = mapped_column(Text, nullable=True)
    hair_color: Mapped[str | None] = mapped_column(Text, nullable=True)
    hair_length_or_style: Mapped[str | None] = mapped_column(Text, nullable=True)
    eye_color: Mapped[str | None] = mapped_column(Text, nullable=True)
    facial_features: Mapped[str | None] = mapped_column(Text, nullable=True)
    distinguishing_marks: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_clothing_style: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_accessories: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_footwear: Mapped[str | None] = mapped_column(Text, nullable=True)
    signature_items: Mapped[str | None] = mapped_column(Text, nullable=True)
    fantasy_features: Mapped[str | None] = mapped_column(Text, nullable=True)
    world_genre_cues: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_scene_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class CharacterVisualSceneState(Base, TimestampMixin):
    __tablename__ = "character_visual_scene_states"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    book_id: Mapped[str] = mapped_column(ForeignKey("books.id"), index=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True)
    scene_id: Mapped[str | None] = mapped_column(ForeignKey("scenes.id"), nullable=True, index=True)
    chapter_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scene_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scene_outfit: Mapped[str | None] = mapped_column(Text, nullable=True)
    scene_accessories: Mapped[str | None] = mapped_column(Text, nullable=True)
    scene_footwear: Mapped[str | None] = mapped_column(Text, nullable=True)
    visible_condition: Mapped[str | None] = mapped_column(Text, nullable=True)
    injuries: Mapped[str | None] = mapped_column(Text, nullable=True)
    dirt_blood_markings: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_language: Mapped[str | None] = mapped_column(Text, nullable=True)
    expression: Mapped[str | None] = mapped_column(Text, nullable=True)
    carried_items: Mapped[str | None] = mapped_column(Text, nullable=True)
    temporary_effects: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_scene_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class CreatureVisualBaseline(Base, TimestampMixin):
    __tablename__ = "creature_visual_baselines"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    book_id: Mapped[str] = mapped_column(ForeignKey("books.id"), index=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), unique=True, index=True)
    species_kind: Mapped[str | None] = mapped_column(Text, nullable=True)
    size_class: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    surface_covering: Mapped[str | None] = mapped_column(Text, nullable=True)
    coloration: Mapped[str | None] = mapped_column(Text, nullable=True)
    head_features: Mapped[str | None] = mapped_column(Text, nullable=True)
    eyes: Mapped[str | None] = mapped_column(Text, nullable=True)
    limbs_appendages: Mapped[str | None] = mapped_column(Text, nullable=True)
    natural_weapons: Mapped[str | None] = mapped_column(Text, nullable=True)
    wings: Mapped[str | None] = mapped_column(Text, nullable=True)
    tail: Mapped[str | None] = mapped_column(Text, nullable=True)
    magical_features: Mapped[str | None] = mapped_column(Text, nullable=True)
    world_genre_cues: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_scene_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class ObjectVisualBaseline(Base, TimestampMixin):
    __tablename__ = "object_visual_baselines"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    book_id: Mapped[str] = mapped_column(ForeignKey("books.id"), index=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), unique=True, index=True)
    object_class: Mapped[str | None] = mapped_column(Text, nullable=True)
    function: Mapped[str | None] = mapped_column(Text, nullable=True)
    size_scale: Mapped[str | None] = mapped_column(Text, nullable=True)
    shape_form: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_material: Mapped[str | None] = mapped_column(Text, nullable=True)
    secondary_materials: Mapped[str | None] = mapped_column(Text, nullable=True)
    color_finish: Mapped[str | None] = mapped_column(Text, nullable=True)
    surface_texture: Mapped[str | None] = mapped_column(Text, nullable=True)
    condition_default: Mapped[str | None] = mapped_column(Text, nullable=True)
    symbolic_markings: Mapped[str | None] = mapped_column(Text, nullable=True)
    magical_properties: Mapped[str | None] = mapped_column(Text, nullable=True)
    world_genre_cues: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_scene_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class ObjectSceneState(Base, TimestampMixin):
    __tablename__ = "object_scene_states"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    book_id: Mapped[str] = mapped_column(ForeignKey("books.id"), index=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True)
    scene_id: Mapped[str | None] = mapped_column(ForeignKey("scenes.id"), nullable=True, index=True)
    chapter_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scene_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    owner_or_holder: Mapped[str | None] = mapped_column(Text, nullable=True)
    activation_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    damage_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    location_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    contained_contents: Mapped[str | None] = mapped_column(Text, nullable=True)
    temporary_effects: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_scene_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class LocationVisualBaseline(Base, TimestampMixin):
    __tablename__ = "location_visual_baselines"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    book_id: Mapped[str] = mapped_column(ForeignKey("books.id"), index=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), unique=True, index=True)
    location_class: Mapped[str | None] = mapped_column(Text, nullable=True)
    indoor_outdoor: Mapped[str | None] = mapped_column(Text, nullable=True)
    environment_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    region_or_domain: Mapped[str | None] = mapped_column(Text, nullable=True)
    architecture_or_terrain_style: Mapped[str | None] = mapped_column(Text, nullable=True)
    dominant_materials: Mapped[str | None] = mapped_column(Text, nullable=True)
    lighting_default: Mapped[str | None] = mapped_column(Text, nullable=True)
    weather_exposure: Mapped[str | None] = mapped_column(Text, nullable=True)
    ambient_mood: Mapped[str | None] = mapped_column(Text, nullable=True)
    notable_features: Mapped[str | None] = mapped_column(Text, nullable=True)
    magic_or_tech_presence: Mapped[str | None] = mapped_column(Text, nullable=True)
    world_genre_cues: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_scene_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class LocationSceneState(Base, TimestampMixin):
    __tablename__ = "location_scene_states"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    book_id: Mapped[str] = mapped_column(ForeignKey("books.id"), index=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True)
    scene_id: Mapped[str | None] = mapped_column(ForeignKey("scenes.id"), nullable=True, index=True)
    chapter_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scene_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lighting_current: Mapped[str | None] = mapped_column(Text, nullable=True)
    weather_current: Mapped[str | None] = mapped_column(Text, nullable=True)
    occupancy_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    damage_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    temporary_setup: Mapped[str | None] = mapped_column(Text, nullable=True)
    atmosphere_shift: Mapped[str | None] = mapped_column(Text, nullable=True)
    active_effects: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_scene_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class StableCharacterState(Base, TimestampMixin):
    __tablename__ = "stable_character_states"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    book_id: Mapped[str] = mapped_column(ForeignKey("books.id"), index=True)
    entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), nullable=True, index=True)
    character_name: Mapped[str] = mapped_column(Text, index=True)
    payload_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class Event(Base, TimestampMixin):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    book_id: Mapped[str] = mapped_column(ForeignKey("books.id"), index=True)
    scene_id: Mapped[str | None] = mapped_column(ForeignKey("scenes.id"), nullable=True, index=True)
    chapter_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scene_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_id_external: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    event_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    entities_involved: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
    payload_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class SemanticDocumentEmbedding(Base, TimestampMixin):
    __tablename__ = "semantic_document_embeddings"
    __table_args__ = (
        UniqueConstraint(
            "book_id",
            "source_type",
            "source_id",
            "embedding_model",
            name="uq_semantic_doc_book_source_model",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    book_id: Mapped[str] = mapped_column(ForeignKey("books.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(64), index=True)
    source_id: Mapped[str] = mapped_column(String(64), index=True)
    chapter_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scene_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(128), index=True)
    embedding_model: Mapped[str] = mapped_column(String(255), index=True)
    embedding_json: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class TimelineRow(Base, TimestampMixin):
    __tablename__ = "timeline_rows"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    book_id: Mapped[str] = mapped_column(ForeignKey("books.id"), index=True)
    event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id"), nullable=True, index=True)
    row_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class VisualPrompt(Base, TimestampMixin):
    __tablename__ = "visual_prompts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    book_id: Mapped[str] = mapped_column(ForeignKey("books.id"), index=True)
    entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), nullable=True, index=True)
    entity_name: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    prompt_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    visual_bucket: Mapped[str | None] = mapped_column(String(128), nullable=True)
    positive_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    negative_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(32), nullable=True)
    book_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chapter_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scene_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


class GeneratedImage(Base, TimestampMixin):
    __tablename__ = "generated_images"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    book_id: Mapped[str] = mapped_column(ForeignKey("books.id"), index=True)
    entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"), nullable=True, index=True)
    prompt_id: Mapped[str | None] = mapped_column(ForeignKey("visual_prompts.id"), nullable=True, index=True)
    entity_name: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    output_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    image_bytes: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    render_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    workflow_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    manifest_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
