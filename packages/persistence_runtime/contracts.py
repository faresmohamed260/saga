"""Portable contracts for persistence runtime clients, providers, and stores."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import AliasChoices, BaseModel, Field

from packages.runtime_common import RuntimeRequestMetadata


class ProviderConfigRecord(BaseModel):
    provider_name: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    updated_at: str = ""
    request_metadata: RuntimeRequestMetadata = Field(
        default_factory=RuntimeRequestMetadata,
        validation_alias=AliasChoices("request_metadata", "metadata"),
        serialization_alias="request_metadata",
    )


class ProviderStatusSnapshot(BaseModel):
    app_name: str = ""
    api_url: str = ""
    ui_url: str = ""
    health_url: str = ""
    warm_until: int = 0
    last_seen_at: int = 0
    last_health_ok: bool | None = None
    last_health_checked_at: int = 0
    last_request_ok: bool | None = None
    last_request_checked_at: int = 0
    last_error: str = ""
    last_error_at: int = 0
    live_payload_checked_at: int = 0


class ProviderStatusRecord(BaseModel):
    provider_name: str = Field(min_length=1)
    label: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    status: ProviderStatusSnapshot = Field(default_factory=ProviderStatusSnapshot)
    updated_at: str = ""
    request_metadata: RuntimeRequestMetadata = Field(
        default_factory=RuntimeRequestMetadata,
        validation_alias=AliasChoices("request_metadata", "metadata"),
        serialization_alias="request_metadata",
    )


class ProviderStatusListPayload(BaseModel):
    provider_name: str = ""
    result_count: int = 0
    results: list[ProviderStatusRecord] = Field(default_factory=list)
    request_metadata: RuntimeRequestMetadata = Field(
        default_factory=RuntimeRequestMetadata,
        validation_alias=AliasChoices("request_metadata", "metadata"),
        serialization_alias="request_metadata",
    )


class ProviderConfigLookupPayload(BaseModel):
    provider_name: str = ""
    found: bool = False
    config: ProviderConfigRecord | None = None
    request_metadata: RuntimeRequestMetadata = Field(
        default_factory=RuntimeRequestMetadata,
        validation_alias=AliasChoices("request_metadata", "metadata"),
        serialization_alias="request_metadata",
    )


class ProviderOperationalRuntimeState(BaseModel):
    app_name: str = ""
    runtime_generation: int = 0
    next_index: int = 0
    active_label: str = ""
    active_api_url: str = ""
    active_ui_url: str = ""
    active_health_url: str = ""
    active_app_name: str = ""
    active_status_found: bool = False
    status_labels: list[str] = Field(default_factory=list)
    status_count: int = 0
    diagnostics: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


class ProviderOperationalStatePayload(BaseModel):
    provider_name: str = ""
    found: bool = False
    config: ProviderConfigRecord | None = None
    runtime_state: ProviderOperationalRuntimeState = Field(default_factory=ProviderOperationalRuntimeState)
    statuses: list[ProviderStatusRecord] = Field(default_factory=list)
    status_count: int = 0
    healthy_labels: list[str] = Field(default_factory=list)
    ready_labels: list[str] = Field(default_factory=list)
    error_labels: list[str] = Field(default_factory=list)
    request_metadata: RuntimeRequestMetadata = Field(
        default_factory=RuntimeRequestMetadata,
        validation_alias=AliasChoices("request_metadata", "metadata"),
        serialization_alias="request_metadata",
    )


class StorageBucketPayload(BaseModel):
    bucket_name: str = ""
    public: bool = False
    exists: bool = False
    provider: str = ""
    request_metadata: RuntimeRequestMetadata = Field(
        default_factory=RuntimeRequestMetadata,
        validation_alias=AliasChoices("request_metadata", "metadata"),
        serialization_alias="request_metadata",
    )


class StorageObjectWritePayload(BaseModel):
    bucket_name: str = ""
    object_path: str = ""
    bytes_written: int = 0
    content_type: str = ""
    provider: str = ""
    key: str = ""
    id: str = ""
    request_metadata: RuntimeRequestMetadata = Field(
        default_factory=RuntimeRequestMetadata,
        validation_alias=AliasChoices("request_metadata", "metadata"),
        serialization_alias="request_metadata",
    )


class StorageObjectTextPayload(BaseModel):
    provider: str = ""
    bucket_name: str = ""
    object_path: str = ""
    text: str = ""
    request_metadata: RuntimeRequestMetadata = Field(
        default_factory=RuntimeRequestMetadata,
        validation_alias=AliasChoices("request_metadata", "metadata"),
        serialization_alias="request_metadata",
    )


class StorageObjectListEntry(BaseModel):
    name: str = ""
    path: str = ""
    size: int = 0
    content_type: str = ""
    provider: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class StorageObjectListPayload(BaseModel):
    provider: str = ""
    bucket_name: str = ""
    prefix: str = ""
    result_count: int = 0
    results: list[StorageObjectListEntry] = Field(default_factory=list)
    request_metadata: RuntimeRequestMetadata = Field(
        default_factory=RuntimeRequestMetadata,
        validation_alias=AliasChoices("request_metadata", "metadata"),
        serialization_alias="request_metadata",
    )


class StorageObjectDeletePayload(BaseModel):
    bucket_name: str = ""
    object_path: str = ""
    deleted: bool = False
    provider: str = ""
    message: str = ""
    request_metadata: RuntimeRequestMetadata = Field(
        default_factory=RuntimeRequestMetadata,
        validation_alias=AliasChoices("request_metadata", "metadata"),
        serialization_alias="request_metadata",
    )


class ArtifactStorePayload(BaseModel):
    bucket_name: str = ""
    object_path: str = ""
    provider: str = ""
    artifact_type: str = ""
    record_id: str = ""
    record: dict[str, Any] = Field(default_factory=dict)
    bytes_written: int = 0
    content_type: str = ""
    key: str = ""
    id: str = ""
    request_metadata: RuntimeRequestMetadata = Field(
        default_factory=RuntimeRequestMetadata,
        validation_alias=AliasChoices("request_metadata", "metadata"),
        serialization_alias="request_metadata",
    )


class LibrarySeriesRecord(BaseModel):
    series_id: str = ""
    title: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    updated_at: str = ""


class LibraryBookRecord(BaseModel):
    book_id: str = ""
    series_id: str = ""
    title: str = ""
    book_index: int | None = None
    source_uri: str = ""
    source_type: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    updated_at: str = ""


class LibrarySceneRecord(BaseModel):
    scene_id: str = ""
    book_id: str = ""
    chapter_index: int = 0
    scene_index: int = 0
    summary: str = ""
    text: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    updated_at: str = ""


class LibraryRecordPayload(BaseModel):
    record_id: str = ""
    record_type: str = ""
    series_id: str = ""
    book_id: str = ""
    scene_id: str = ""
    title: str = ""
    ordinal: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    updated_at: str = ""


class LibraryBooksListPayload(BaseModel):
    result_count: int = 0
    results: list[LibraryBookRecord] = Field(default_factory=list)
    request_metadata: RuntimeRequestMetadata = Field(
        default_factory=RuntimeRequestMetadata,
        validation_alias=AliasChoices("request_metadata", "metadata"),
        serialization_alias="request_metadata",
    )


class LibraryScenesListPayload(BaseModel):
    result_count: int = 0
    results: list[LibrarySceneRecord] = Field(default_factory=list)
    request_metadata: RuntimeRequestMetadata = Field(
        default_factory=RuntimeRequestMetadata,
        validation_alias=AliasChoices("request_metadata", "metadata"),
        serialization_alias="request_metadata",
    )


class LibraryRecordsListPayload(BaseModel):
    result_count: int = 0
    results: list[LibraryRecordPayload] = Field(default_factory=list)
    request_metadata: RuntimeRequestMetadata = Field(
        default_factory=RuntimeRequestMetadata,
        validation_alias=AliasChoices("request_metadata", "metadata"),
        serialization_alias="request_metadata",
    )


class IdentitySeriesRecord(BaseModel):
    series_id: str = ""
    provider_name: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    updated_at: str = ""
    request_metadata: RuntimeRequestMetadata = Field(
        default_factory=RuntimeRequestMetadata,
        validation_alias=AliasChoices("request_metadata", "metadata"),
        serialization_alias="request_metadata",
    )


class JobLogRecord(BaseModel):
    job_id: str = ""
    stage: str = ""
    message: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""


class JobRecordPayload(BaseModel):
    job_id: str = ""
    job_type: str = ""
    status: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    logs: list[JobLogRecord] = Field(default_factory=list)
    updated_at: str = ""
    request_metadata: RuntimeRequestMetadata = Field(
        default_factory=RuntimeRequestMetadata,
        validation_alias=AliasChoices("request_metadata", "metadata"),
        serialization_alias="request_metadata",
    )


class JobListPayload(BaseModel):
    result_count: int = 0
    results: list[JobRecordPayload] = Field(default_factory=list)
    request_metadata: RuntimeRequestMetadata = Field(
        default_factory=RuntimeRequestMetadata,
        validation_alias=AliasChoices("request_metadata", "metadata"),
        serialization_alias="request_metadata",
    )


class StoryRecordPayload(BaseModel):
    story_id: str = ""
    series_id: str = ""
    book_id: str = ""
    title: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    updated_at: str = ""


class StoryListPayload(BaseModel):
    result_count: int = 0
    results: list[StoryRecordPayload] = Field(default_factory=list)
    request_metadata: RuntimeRequestMetadata = Field(
        default_factory=RuntimeRequestMetadata,
        validation_alias=AliasChoices("request_metadata", "metadata"),
        serialization_alias="request_metadata",
    )


class AudiobookChapterRecord(BaseModel):
    chapter_id: str = ""
    run_id: str = ""
    book_index: int = 0
    chapter_index: int = 0
    payload: dict[str, Any] = Field(default_factory=dict)
    updated_at: str = ""


class AudiobookRunRecordPayload(BaseModel):
    run_id: str = ""
    series_id: str = ""
    book_id: str = ""
    title: str = ""
    status: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    chapters: list[AudiobookChapterRecord] = Field(default_factory=list)
    updated_at: str = ""


class VectorDocumentWritePayload(BaseModel):
    provider: str = ""
    namespace: str = ""
    document_count: int = 0
    request_metadata: RuntimeRequestMetadata = Field(
        default_factory=RuntimeRequestMetadata,
        validation_alias=AliasChoices("request_metadata", "metadata"),
        serialization_alias="request_metadata",
    )


class VectorQueryResultRecord(BaseModel):
    namespace: str = ""
    document_id: str = ""
    content: str = ""
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    score: float = 0.0


class VectorQueryPayload(BaseModel):
    provider: str = ""
    namespace: str = ""
    result_count: int = 0
    results: list[VectorQueryResultRecord] = Field(default_factory=list)
    request_metadata: RuntimeRequestMetadata = Field(
        default_factory=RuntimeRequestMetadata,
        validation_alias=AliasChoices("request_metadata", "metadata"),
        serialization_alias="request_metadata",
    )


class VectorDeletePayload(BaseModel):
    provider: str = ""
    namespace: str = ""
    deleted_count: int = 0
    request_metadata: RuntimeRequestMetadata = Field(
        default_factory=RuntimeRequestMetadata,
        validation_alias=AliasChoices("request_metadata", "metadata"),
        serialization_alias="request_metadata",
    )


class AudiobookRunLookupPayload(BaseModel):
    run_id: str = ""
    found: bool = False
    run: AudiobookRunRecordPayload | None = None
    request_metadata: RuntimeRequestMetadata = Field(
        default_factory=RuntimeRequestMetadata,
        validation_alias=AliasChoices("request_metadata", "metadata"),
        serialization_alias="request_metadata",
    )


class AudiobookRunListPayload(BaseModel):
    result_count: int = 0
    results: list[AudiobookRunRecordPayload] = Field(default_factory=list)
    request_metadata: RuntimeRequestMetadata = Field(
        default_factory=RuntimeRequestMetadata,
        validation_alias=AliasChoices("request_metadata", "metadata"),
        serialization_alias="request_metadata",
    )


class ProviderConfigStore(Protocol):
    def upsert_provider_config(self, provider_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def get_provider_config(self, provider_name: str) -> dict[str, Any] | None:
        ...

    def list_provider_configs(self) -> list[dict[str, Any]]:
        ...

    def get_provider_operational_state(self, provider_name: str) -> dict[str, Any]:
        ...

    def upsert_provider_status(self, provider_name: str, label: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def replace_provider_statuses(self, provider_name: str, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ...

    def list_provider_statuses(self, provider_name: str | None = None) -> list[dict[str, Any]]:
        ...


class LibraryStore(Protocol):
    def upsert_series(self, series_id: str, *, title: str = "", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        ...

    def list_series(self, *, limit: int = 100) -> list[dict[str, Any]]:
        ...

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
        ...

    def list_books(self, *, series_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        ...

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
        ...

    def upsert_scenes(self, scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ...

    def list_scenes(self, *, book_id: str, limit: int = 500) -> list[dict[str, Any]]:
        ...

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
        ...

    def upsert_records(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ...

    def replace_records(
        self,
        *,
        record_type: str,
        series_id: str,
        records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        ...

    def list_records(
        self,
        *,
        record_type: str | None = None,
        series_id: str | None = None,
        book_id: str | None = None,
        scene_id: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        ...


class IdentityStore(Protocol):
    def upsert_identity_series(self, series_id: str, *, provider_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def get_identity_series(self, series_id: str) -> dict[str, Any] | None:
        ...


class JobStore(Protocol):
    def create_job(self, job_id: str, *, job_type: str, status: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        ...

    def update_job(self, job_id: str, *, status: str | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
        ...

    def add_job_log(self, job_id: str, *, stage: str, message: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        ...

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        ...

    def list_jobs(self, *, job_type: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        ...


class ExecutionQueueStore(Protocol):
    def set_policy(self, queue_name: str, payload: dict[str, Any]) -> dict[str, Any]: ...

    def get_policy(self, queue_name: str) -> dict[str, Any] | None: ...

    def enqueue(self, queue_id: str, *, run_id: str, queue_name: str, series_id: str = "", priority: int = 0, capabilities: list[str] | None = None, payload: dict[str, Any] | None = None, available_at_ms: int = 0, max_attempts: int = 3, backoff_seconds: int = 5) -> dict[str, Any]: ...

    def requeue(self, queue_id: str, *, payload: dict[str, Any] | None = None, priority: int | None = None, max_attempts: int | None = None, backoff_seconds: int | None = None, now_ms: int | None = None) -> dict[str, Any] | None: ...

    def claim(self, queue_name: str, *, worker_id: str, lease_seconds: int = 120, now_ms: int | None = None) -> dict[str, Any] | None: ...

    def heartbeat(self, queue_id: str, *, worker_id: str, lease_token: str, lease_seconds: int = 120, now_ms: int | None = None) -> dict[str, Any] | None: ...

    def complete(self, queue_id: str, *, worker_id: str, lease_token: str, status: str = "succeeded", payload: dict[str, Any] | None = None, now_ms: int | None = None) -> dict[str, Any] | None: ...

    def fail(self, queue_id: str, *, worker_id: str, lease_token: str, error: dict[str, Any], retryable: bool = True, now_ms: int | None = None) -> dict[str, Any] | None: ...

    def request_cancel(self, queue_id: str, *, reason: str = "", now_ms: int | None = None) -> dict[str, Any] | None: ...

    def is_cancellation_requested(self, queue_id: str) -> bool: ...

    def recover_expired(self, queue_name: str, *, now_ms: int | None = None) -> list[dict[str, Any]]: ...

    def get(self, queue_id: str) -> dict[str, Any] | None: ...

    def list(self, *, queue_name: str | None = None, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]: ...

    def emit_event(self, *, queue_name: str, queue_id: str, run_id: str, event_type: str, status: str = "", worker_id: str = "", timestamp_ms: int | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]: ...

    def list_events(self, *, run_id: str = "", queue_name: str = "", limit: int = 1000) -> list[dict[str, Any]]: ...

    def purge_terminal(self, queue_name: str, *, run_ids: list[str]) -> dict[str, int]: ...


class LineageStore(Protocol):
    def append(self, record: dict[str, Any]) -> dict[str, Any]: ...

    def get(self, execution_id: str) -> dict[str, Any] | None: ...

    def find_latest_accepted(
        self, *, series_id: str, stage: str, input_fingerprint: str, output_fingerprint: str = "",
    ) -> dict[str, Any] | None: ...

    def list(self, *, run_id: str = "", series_id: str = "", stage: str = "", limit: int = 1000) -> list[dict[str, Any]]: ...


class ObservabilityStore(Protocol):
    def append(self, record: dict[str, Any]) -> dict[str, Any]: ...

    def append_many(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]: ...

    def list(
        self, *, kind: str = "", run_id: str = "", series_id: str = "", component: str = "",
        provider: str = "", name: str = "", since_ms: int = 0, until_ms: int = 0, limit: int = 1000,
    ) -> list[dict[str, Any]]: ...

    def delete_before(self, timestamp_ms: int, *, kind: str = "") -> int: ...


class UsageLedgerStore(Protocol):
    def configure_policy(self, policy: dict[str, Any]) -> dict[str, Any]: ...

    def list_policies(self, *, enabled: bool | None = None, limit: int = 1000) -> list[dict[str, Any]]: ...

    def reserve(self, entry: dict[str, Any]) -> dict[str, Any]: ...

    def settle(self, *, reservation_id: str, release_entry: dict[str, Any], charge_entry: dict[str, Any]) -> dict[str, Any]: ...

    def release(self, entry: dict[str, Any]) -> dict[str, Any]: ...

    def list(self, *, project_id: str = "", run_id: str = "", provider: str = "", account_alias: str = "", entry_kind: str = "", since_ms: int = 0, limit: int = 1000) -> list[dict[str, Any]]: ...


class DeploymentStore(Protocol):
    def record_release(self, release: dict[str, Any]) -> dict[str, Any]: ...

    def set_release_status(self, release_id: str, *, status: str) -> dict[str, Any] | None: ...

    def promote_release(self, release_id: str, *, expected_status: str = "staging") -> dict[str, Any]: ...

    def get_release(self, release_id: str) -> dict[str, Any] | None: ...

    def list_releases(self, *, status: str = "", limit: int = 100) -> list[dict[str, Any]]: ...

    def record_release_gate_evidence(self, evidence: dict[str, Any]) -> dict[str, Any]: ...

    def list_release_gate_evidence(
        self, *, release_id: str, gate: str = "", limit: int = 1000
    ) -> list[dict[str, Any]]: ...

    def heartbeat(self, process: dict[str, Any]) -> dict[str, Any]: ...

    def list_heartbeats(self, *, role: str = "", since_ms: int = 0, limit: int = 1000) -> list[dict[str, Any]]: ...


class StoryStore(Protocol):
    def upsert_story(
        self,
        story_id: str,
        *,
        series_id: str = "",
        book_id: str = "",
        title: str = "",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ...

    def list_stories(self, *, series_id: str | None = None, book_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        ...


class AudiobookStore(Protocol):
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
        ...

    def upsert_chapter(
        self,
        chapter_id: str,
        *,
        run_id: str,
        book_index: int,
        chapter_index: int,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ...

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        ...

    def list_runs(self, *, series_id: str | None = None, book_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        ...


class VectorStore(Protocol):
    def upsert_documents(self, namespace: str, documents: list[dict[str, Any]]) -> dict[str, Any]:
        ...

    def list_documents(
        self,
        namespace: str,
        *,
        metadata_filters: dict[str, Any] | None = None,
        limit: int = 10000,
    ) -> list[dict[str, Any]]:
        ...

    def query_documents(
        self,
        namespace: str,
        *,
        query_vector: list[float],
        top_k: int = 6,
        metadata_filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        ...

    def delete_documents(self, namespace: str, document_ids: list[str] | None = None) -> dict[str, Any]:
        ...


class ObjectStorageStore(Protocol):
    def ensure_bucket(self, bucket_name: str, *, public: bool = False) -> dict[str, Any]:
        ...

    def upload_bytes(
        self,
        bucket_name: str,
        object_path: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
        upsert: bool = True,
    ) -> dict[str, Any]:
        ...

    def upload_text(
        self,
        bucket_name: str,
        object_path: str,
        text: str,
        *,
        content_type: str = "text/plain; charset=utf-8",
        upsert: bool = True,
    ) -> dict[str, Any]:
        ...

    def upload_json(self, bucket_name: str, object_path: str, payload: dict[str, Any], *, upsert: bool = True) -> dict[str, Any]:
        ...

    def download_bytes(self, bucket_name: str, object_path: str) -> bytes:
        ...

    def download_text(self, bucket_name: str, object_path: str, *, encoding: str = "utf-8") -> str:
        ...

    def get_object_info(self, bucket_name: str, object_path: str) -> dict[str, Any]:
        ...

    def list_objects(self, bucket_name: str, *, prefix: str = "", limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        ...

    def delete_object(self, bucket_name: str, object_path: str) -> dict[str, Any]:
        ...


class PersistenceRuntime(Protocol):
    provider_configs: ProviderConfigStore
    library: LibraryStore
    identity: IdentityStore
    jobs: JobStore
    execution_queue: ExecutionQueueStore
    lineage: LineageStore
    observability: ObservabilityStore
    usage: UsageLedgerStore
    deployments: DeploymentStore
    stories: StoryStore
    audiobooks: AudiobookStore
    vectors: VectorStore
    objects: ObjectStorageStore

    def initialize(self) -> None:
        ...

    def close(self) -> None:
        ...

    def provider_name(self) -> str:
        ...


class PersistenceProvider(PersistenceRuntime, Protocol):
    engine: Any
