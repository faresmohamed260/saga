"""Provider-oriented persistence runtime client."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from packages.persistence_runtime.conventions import ArtifactStorageManager, EphemeralWorkspaceManager, default_ephemeral_root
from packages.persistence_runtime.contracts import (
    AudiobookRunListPayload,
    AudiobookRunLookupPayload,
    AudiobookRunRecordPayload,
    ArtifactStorePayload,
    IdentitySeriesRecord,
    JobListPayload,
    JobRecordPayload,
    LibraryBookRecord,
    LibraryBooksListPayload,
    LibraryRecordPayload,
    LibraryRecordsListPayload,
    LibrarySceneRecord,
    LibraryScenesListPayload,
    ProviderConfigLookupPayload,
    ProviderConfigRecord,
    ProviderOperationalStatePayload,
    ProviderStatusListPayload,
    ProviderStatusRecord,
    StorageBucketPayload,
    StorageObjectDeletePayload,
    StorageObjectListEntry,
    StorageObjectListPayload,
    StorageObjectTextPayload,
    StorageObjectWritePayload,
    StoryListPayload,
    StoryRecordPayload,
    VectorDeletePayload,
    VectorDocumentWritePayload,
    VectorQueryPayload,
    VectorQueryResultRecord,
)
from packages.persistence_runtime.models import PersistenceProfile, PersistenceRuntimeConfig
from packages.persistence_runtime.providers import create_provider
from packages.runtime_common import build_structured_runtime_tool


class PersistenceRuntimeClient:
    def __init__(
        self,
        *,
        profile: PersistenceProfile,
        config: PersistenceRuntimeConfig,
    ) -> None:
        self.profile = profile
        self.config = config
        self.provider = create_provider(profile=profile, config=config)
        self.provider_configs = self.provider.provider_configs
        self.library = self.provider.library
        self.identity = self.provider.identity
        self.jobs = self.provider.jobs
        self.execution_queue = self.provider.execution_queue
        self.lineage = self.provider.lineage
        self.observability = self.provider.observability
        self.usage = self.provider.usage
        self.deployments = self.provider.deployments
        self.stories = self.provider.stories
        self.audiobooks = self.provider.audiobooks
        self.vectors = self.provider.vectors
        self.objects = self.provider.objects
        self.artifacts = ArtifactStorageManager(self.objects, self.library)
        self.ephemeral = EphemeralWorkspaceManager(default_ephemeral_root(profile.local_storage_root_dir))
        self.engine = self.provider.engine
        self.database_url = getattr(self.provider, "database_url", "")

    def initialize(self) -> None:
        self.provider.initialize()

    def close(self) -> None:
        self.provider.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def provider_name(self) -> str:
        return self.provider.provider_name()

    def as_langgraph_tools(self) -> list[StructuredTool]:
        client = self

        def build_tool(*, name: str, description: str, args_schema: type[BaseModel], operation: str, func, response_model: type[BaseModel] | None = None):
            return build_structured_runtime_tool(
                func=func,
                name=name,
                description=description,
                args_schema=args_schema,
                component="persistence_runtime",
                operation=operation,
                provider_name=client.provider_name,
                metadata=lambda: {"profile": client.profile.name, "tool_name": name},
                response_model=response_model,
                error_code=f"{name}_failed",
            )

        class UpsertProviderConfigArgs(BaseModel):
            provider_name: str = Field(description="Logical provider name.")
            payload: dict[str, Any] = Field(description="Provider configuration payload.")

        class GetProviderConfigArgs(BaseModel):
            provider_name: str = Field(description="Logical provider name.")

        class GetProviderOperationalStateArgs(BaseModel):
            provider_name: str = Field(description="Logical provider name.")

        class UpsertProviderStatusArgs(BaseModel):
            provider_name: str = Field(description="Logical provider name.")
            label: str = Field(description="Stable status label such as a token, account, or endpoint name.")
            payload: dict[str, Any] = Field(description="Operational status payload.")

        class ListProviderStatusesArgs(BaseModel):
            provider_name: str = Field(default="", description="Optional provider filter.")

        class UpsertSeriesArgs(BaseModel):
            series_id: str = Field(description="Stable series identifier.")
            title: str = Field(default="", description="Display title.")
            metadata: dict[str, Any] = Field(default_factory=dict, description="Supplemental series metadata.")

        class UpsertBookArgs(BaseModel):
            book_id: str = Field(description="Stable book identifier.")
            series_id: str = Field(default="", description="Owning series identifier.")
            title: str = Field(default="", description="Display title.")
            book_index: int | None = Field(default=None, description="Optional ordinal within the series.")
            source_uri: str = Field(default="", description="Optional source URI.")
            source_type: str = Field(default="", description="Optional source type such as epub or pdf.")
            metadata: dict[str, Any] = Field(default_factory=dict, description="Supplemental book metadata.")

        class UpsertSceneArgs(BaseModel):
            scene_id: str = Field(description="Stable scene identifier.")
            book_id: str = Field(description="Owning book identifier.")
            chapter_index: int = Field(description="Chapter ordinal.")
            scene_index: int = Field(description="Scene ordinal within the chapter.")
            summary: str = Field(default="", description="Scene summary.")
            text: str = Field(default="", description="Scene text.")
            payload: dict[str, Any] = Field(default_factory=dict, description="Supplemental scene payload.")

        class UpsertRecordArgs(BaseModel):
            record_id: str = Field(description="Stable record identifier.")
            record_type: str = Field(description="Record category such as entity, event, or prompt.")
            series_id: str = Field(default="", description="Optional series identifier.")
            book_id: str = Field(default="", description="Optional book identifier.")
            scene_id: str = Field(default="", description="Optional scene identifier.")
            title: str = Field(default="", description="Display title.")
            ordinal: int | None = Field(default=None, description="Optional ordering value.")
            payload: dict[str, Any] = Field(default_factory=dict, description="Supplemental record payload.")

        class ListBooksArgs(BaseModel):
            series_id: str = Field(default="", description="Optional series filter.")
            limit: int = Field(default=50, ge=1, le=500, description="Maximum number of books to return.")

        class ListScenesArgs(BaseModel):
            book_id: str = Field(description="Book identifier.")
            limit: int = Field(default=100, ge=1, le=1000, description="Maximum number of scenes to return.")

        class ListRecordsArgs(BaseModel):
            record_type: str = Field(default="", description="Optional record type filter.")
            series_id: str = Field(default="", description="Optional series filter.")
            book_id: str = Field(default="", description="Optional book filter.")
            scene_id: str = Field(default="", description="Optional scene filter.")
            limit: int = Field(default=100, ge=1, le=1000, description="Maximum number of records to return.")

        class UpsertIdentitySeriesArgs(BaseModel):
            series_id: str = Field(description="Stable series identifier.")
            provider_name: str = Field(description="Identity provider name.")
            payload: dict[str, Any] = Field(default_factory=dict, description="Identity payload.")

        class GetIdentitySeriesArgs(BaseModel):
            series_id: str = Field(description="Stable series identifier.")

        class CreateJobArgs(BaseModel):
            job_id: str = Field(description="Stable job identifier.")
            job_type: str = Field(description="Logical job type.")
            status: str = Field(description="Current job status.")
            payload: dict[str, Any] = Field(default_factory=dict, description="Job payload.")

        class AddJobLogArgs(BaseModel):
            job_id: str = Field(description="Stable job identifier.")
            stage: str = Field(description="Job stage label.")
            message: str = Field(description="Log message.")
            payload: dict[str, Any] = Field(default_factory=dict, description="Structured log payload.")

        class GetJobArgs(BaseModel):
            job_id: str = Field(description="Stable job identifier.")

        class ListJobsArgs(BaseModel):
            job_type: str = Field(default="", description="Optional job type filter.")
            limit: int = Field(default=100, ge=1, le=1000, description="Maximum number of jobs to return.")

        class UpsertStoryArgs(BaseModel):
            story_id: str = Field(description="Stable story identifier.")
            series_id: str = Field(default="", description="Optional series identifier.")
            book_id: str = Field(default="", description="Optional book identifier.")
            title: str = Field(default="", description="Story title.")
            payload: dict[str, Any] = Field(default_factory=dict, description="Story payload.")

        class ListStoriesArgs(BaseModel):
            series_id: str = Field(default="", description="Optional series filter.")
            book_id: str = Field(default="", description="Optional book filter.")
            limit: int = Field(default=100, ge=1, le=1000, description="Maximum number of stories to return.")

        class UpsertAudiobookRunArgs(BaseModel):
            run_id: str = Field(description="Stable audiobook run identifier.")
            series_id: str = Field(default="", description="Optional series identifier.")
            book_id: str = Field(default="", description="Optional book identifier.")
            title: str = Field(default="", description="Audiobook title.")
            status: str = Field(default="staged", description="Run status.")
            payload: dict[str, Any] = Field(default_factory=dict, description="Audiobook run payload.")

        class UpsertAudiobookChapterArgs(BaseModel):
            chapter_id: str = Field(description="Stable audiobook chapter identifier.")
            run_id: str = Field(description="Owning audiobook run identifier.")
            book_index: int = Field(description="Book ordinal.")
            chapter_index: int = Field(description="Chapter ordinal.")
            payload: dict[str, Any] = Field(default_factory=dict, description="Audiobook chapter payload.")

        class GetAudiobookRunArgs(BaseModel):
            run_id: str = Field(description="Stable audiobook run identifier.")

        class ListAudiobookRunsArgs(BaseModel):
            series_id: str = Field(default="", description="Optional series filter.")
            book_id: str = Field(default="", description="Optional book filter.")
            limit: int = Field(default=100, ge=1, le=1000, description="Maximum number of runs to return.")

        class UpsertVectorDocumentsArgs(BaseModel):
            namespace: str = Field(description="Logical vector namespace.")
            documents: list[dict[str, Any]] = Field(
                description="Vector documents. Each item should include document_id, embedding, and optional content, summary, and metadata."
            )

        class QueryVectorDocumentsArgs(BaseModel):
            namespace: str = Field(description="Logical vector namespace.")
            query_vector: list[float] = Field(description="Dense query vector.")
            top_k: int = Field(default=6, ge=1, le=100, description="Maximum number of nearest results to return.")
            metadata_filters: dict[str, Any] = Field(default_factory=dict, description="Optional exact-match metadata filters.")

        class DeleteVectorDocumentsArgs(BaseModel):
            namespace: str = Field(description="Logical vector namespace.")
            document_ids: list[str] = Field(default_factory=list, description="Optional document identifiers to delete. Leave empty to clear the namespace.")

        class EnsureBucketArgs(BaseModel):
            bucket_name: str = Field(description="Storage bucket name.")
            public: bool = Field(default=False, description="Whether the bucket should be public.")

        class UploadTextObjectArgs(BaseModel):
            bucket_name: str = Field(description="Storage bucket name.")
            object_path: str = Field(description="Path of the object within the bucket.")
            text: str = Field(description="UTF-8 text payload.")
            content_type: str = Field(default="text/plain; charset=utf-8", description="Content type header.")
            upsert: bool = Field(default=True, description="Whether to overwrite an existing object.")

        class UploadJsonObjectArgs(BaseModel):
            bucket_name: str = Field(description="Storage bucket name.")
            object_path: str = Field(description="Path of the object within the bucket.")
            payload: dict[str, Any] = Field(description="JSON payload to store.")
            upsert: bool = Field(default=True, description="Whether to overwrite an existing object.")

        class DownloadTextObjectArgs(BaseModel):
            bucket_name: str = Field(description="Storage bucket name.")
            object_path: str = Field(description="Path of the object within the bucket.")

        class ListObjectsArgs(BaseModel):
            bucket_name: str = Field(description="Storage bucket name.")
            prefix: str = Field(default="", description="Optional prefix filter.")
            limit: int = Field(default=100, ge=1, le=1000, description="Maximum number of results to return.")
            offset: int = Field(default=0, ge=0, description="Pagination offset.")

        class DeleteObjectArgs(BaseModel):
            bucket_name: str = Field(description="Storage bucket name.")
            object_path: str = Field(description="Path of the object within the bucket.")

        class StoreTextArtifactArgs(BaseModel):
            artifact_type: str = Field(description="Durable artifact family such as source_document, generated_image, identity_export, story_export, audio_output, or runtime_report.")
            filename: str = Field(description="Artifact filename.")
            text: str = Field(description="UTF-8 text payload.")
            content_type: str = Field(default="text/plain; charset=utf-8", description="Content type header.")
            series_id: str = Field(default="", description="Owning series identifier when applicable.")
            book_id: str = Field(default="", description="Owning book identifier when applicable.")
            scene_id: str = Field(default="", description="Owning scene identifier when applicable.")
            entity_id: str = Field(default="", description="Owning entity identifier for generated image artifacts.")
            story_id: str = Field(default="", description="Owning story identifier for story exports.")
            run_id: str = Field(default="", description="Owning audiobook run identifier for audio outputs.")
            chapter_id: str = Field(default="", description="Owning audiobook chapter identifier for audio outputs.")
            provider_name: str = Field(default="", description="Provider name for runtime reports.")
            report_kind: str = Field(default="", description="Report kind for runtime reports.")
            metadata: dict[str, Any] = Field(default_factory=dict, description="Extra structured metadata to link with the artifact record.")

        class StoreJsonArtifactArgs(BaseModel):
            artifact_type: str = Field(description="Durable artifact family such as source_document, generated_image, identity_export, story_export, audio_output, or runtime_report.")
            filename: str = Field(description="Artifact filename.")
            payload: dict[str, Any] = Field(description="JSON payload to store.")
            series_id: str = Field(default="", description="Owning series identifier when applicable.")
            book_id: str = Field(default="", description="Owning book identifier when applicable.")
            scene_id: str = Field(default="", description="Owning scene identifier when applicable.")
            entity_id: str = Field(default="", description="Owning entity identifier for generated image artifacts.")
            story_id: str = Field(default="", description="Owning story identifier for story exports.")
            run_id: str = Field(default="", description="Owning audiobook run identifier for audio outputs.")
            chapter_id: str = Field(default="", description="Owning audiobook chapter identifier for audio outputs.")
            provider_name: str = Field(default="", description="Provider name for runtime reports.")
            report_kind: str = Field(default="", description="Report kind for runtime reports.")
            metadata: dict[str, Any] = Field(default_factory=dict, description="Extra structured metadata to link with the artifact record.")

        def upsert_provider_config_tool(provider_name: str, payload: dict[str, Any]) -> dict[str, Any]:
            return client.provider_configs.upsert_provider_config(provider_name, payload)

        def get_provider_config_tool(provider_name: str) -> dict[str, Any] | None:
            return client.provider_configs.get_provider_config(provider_name)

        def get_provider_config_lookup_tool(provider_name: str) -> dict[str, Any]:
            row = get_provider_config_tool(provider_name)
            return ProviderConfigLookupPayload(
                provider_name=str(provider_name or ""),
                found=row is not None,
                config=ProviderConfigRecord.model_validate(row) if row is not None else None,
            ).model_dump()

        def get_provider_operational_state_tool(provider_name: str) -> dict[str, Any]:
            return ProviderOperationalStatePayload.model_validate(
                client.provider_configs.get_provider_operational_state(provider_name)
            ).model_dump()

        def upsert_provider_status_tool(provider_name: str, label: str, payload: dict[str, Any]) -> dict[str, Any]:
            return client.provider_configs.upsert_provider_status(provider_name, label, payload)

        def list_provider_statuses_tool(provider_name: str = "") -> dict[str, Any]:
            results = client.provider_configs.list_provider_statuses(provider_name or None)
            return ProviderStatusListPayload(
                provider_name=str(provider_name or ""),
                result_count=len(results),
                results=[ProviderStatusRecord.model_validate(item) for item in results],
            ).model_dump()

        def upsert_series_tool(series_id: str, title: str = "", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
            return client.library.upsert_series(series_id, title=title, metadata=metadata or {})

        def upsert_book_tool(
            book_id: str,
            series_id: str = "",
            title: str = "",
            book_index: int | None = None,
            source_uri: str = "",
            source_type: str = "",
            metadata: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            return client.library.upsert_book(
                book_id,
                series_id=series_id,
                title=title,
                book_index=book_index,
                source_uri=source_uri,
                source_type=source_type,
                metadata=metadata or {},
            )

        def upsert_scene_tool(
            scene_id: str,
            book_id: str,
            chapter_index: int,
            scene_index: int,
            summary: str = "",
            text: str = "",
            payload: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            return client.library.upsert_scene(
                scene_id,
                book_id=book_id,
                chapter_index=chapter_index,
                scene_index=scene_index,
                summary=summary,
                text=text,
                payload=payload or {},
            )

        def upsert_record_tool(
            record_id: str,
            record_type: str,
            series_id: str = "",
            book_id: str = "",
            scene_id: str = "",
            title: str = "",
            ordinal: int | None = None,
            payload: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            return client.library.upsert_record(
                record_id,
                record_type=record_type,
                series_id=series_id,
                book_id=book_id,
                scene_id=scene_id,
                title=title,
                ordinal=ordinal,
                payload=payload or {},
            )

        def list_books_tool(series_id: str = "", limit: int = 50) -> dict[str, Any]:
            results = client.library.list_books(series_id=series_id or None, limit=limit)
            return LibraryBooksListPayload(
                result_count=len(results),
                results=[LibraryBookRecord.model_validate(item) for item in results],
            ).model_dump()

        def list_scenes_tool(book_id: str, limit: int = 100) -> dict[str, Any]:
            results = client.library.list_scenes(book_id=book_id, limit=limit)
            return LibraryScenesListPayload(
                result_count=len(results),
                results=[LibrarySceneRecord.model_validate(item) for item in results],
            ).model_dump()

        def list_records_tool(
            record_type: str = "",
            series_id: str = "",
            book_id: str = "",
            scene_id: str = "",
            limit: int = 100,
        ) -> dict[str, Any]:
            results = client.library.list_records(
                record_type=record_type or None,
                series_id=series_id or None,
                book_id=book_id or None,
                scene_id=scene_id or None,
                limit=limit,
            )
            return LibraryRecordsListPayload(
                result_count=len(results),
                results=[LibraryRecordPayload.model_validate(item) for item in results],
            ).model_dump()

        def upsert_identity_series_tool(series_id: str, provider_name: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
            return client.identity.upsert_identity_series(series_id, provider_name=provider_name, payload=payload or {})

        def get_identity_series_tool(series_id: str) -> dict[str, Any] | None:
            row = client.identity.get_identity_series(series_id)
            return IdentitySeriesRecord.model_validate(row).model_dump() if row is not None else None

        def create_job_tool(job_id: str, job_type: str, status: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
            return client.jobs.create_job(job_id, job_type=job_type, status=status, payload=payload or {})

        def add_job_log_tool(job_id: str, stage: str, message: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
            return client.jobs.add_job_log(job_id, stage=stage, message=message, payload=payload or {})

        def get_job_tool(job_id: str) -> dict[str, Any] | None:
            row = client.jobs.get_job(job_id)
            return JobRecordPayload.model_validate(row).model_dump() if row is not None else None

        def list_jobs_tool(job_type: str = "", limit: int = 100) -> dict[str, Any]:
            results = client.jobs.list_jobs(job_type=job_type or None, limit=limit)
            return JobListPayload(
                result_count=len(results),
                results=[JobRecordPayload.model_validate(item) for item in results],
            ).model_dump()

        def upsert_story_tool(
            story_id: str,
            series_id: str = "",
            book_id: str = "",
            title: str = "",
            payload: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            return client.stories.upsert_story(story_id, series_id=series_id, book_id=book_id, title=title, payload=payload or {})

        def list_stories_tool(series_id: str = "", book_id: str = "", limit: int = 100) -> dict[str, Any]:
            results = client.stories.list_stories(series_id=series_id or None, book_id=book_id or None, limit=limit)
            return StoryListPayload(
                result_count=len(results),
                results=[StoryRecordPayload.model_validate(item) for item in results],
            ).model_dump()

        def upsert_audiobook_run_tool(
            run_id: str,
            series_id: str = "",
            book_id: str = "",
            title: str = "",
            status: str = "staged",
            payload: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            return client.audiobooks.upsert_run(
                run_id,
                series_id=series_id,
                book_id=book_id,
                title=title,
                status=status,
                payload=payload or {},
            )

        def upsert_audiobook_chapter_tool(
            chapter_id: str,
            run_id: str,
            book_index: int,
            chapter_index: int,
            payload: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            return client.audiobooks.upsert_chapter(
                chapter_id,
                run_id=run_id,
                book_index=book_index,
                chapter_index=chapter_index,
                payload=payload or {},
            )

        def get_audiobook_run_tool(run_id: str) -> dict[str, Any] | None:
            row = client.audiobooks.get_run(run_id)
            return AudiobookRunLookupPayload(
                run_id=run_id,
                found=row is not None,
                run=AudiobookRunRecordPayload.model_validate(row) if row is not None else None,
            ).model_dump()

        def list_audiobook_runs_tool(series_id: str = "", book_id: str = "", limit: int = 100) -> dict[str, Any]:
            results = client.audiobooks.list_runs(series_id=series_id or None, book_id=book_id or None, limit=limit)
            return AudiobookRunListPayload(
                result_count=len(results),
                results=[AudiobookRunRecordPayload.model_validate(item) for item in results],
            ).model_dump()

        def upsert_vector_documents_tool(namespace: str, documents: list[dict[str, Any]]) -> dict[str, Any]:
            payload = client.vectors.upsert_documents(namespace, documents)
            return VectorDocumentWritePayload(
                provider=client.provider_name(),
                namespace=str(payload.get("namespace") or namespace),
                document_count=int(payload.get("document_count") or 0),
            ).model_dump()

        def query_vector_documents_tool(
            namespace: str,
            query_vector: list[float],
            top_k: int = 6,
            metadata_filters: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            results = client.vectors.query_documents(
                namespace,
                query_vector=query_vector,
                top_k=top_k,
                metadata_filters=metadata_filters or {},
            )
            return VectorQueryPayload(
                provider=client.provider_name(),
                namespace=namespace,
                result_count=len(results),
                results=[VectorQueryResultRecord.model_validate(item) for item in results],
            ).model_dump()

        def delete_vector_documents_tool(namespace: str, document_ids: list[str] | None = None) -> dict[str, Any]:
            payload = client.vectors.delete_documents(namespace, document_ids or [])
            return VectorDeletePayload(
                provider=client.provider_name(),
                namespace=str(payload.get("namespace") or namespace),
                deleted_count=int(payload.get("deleted_count") or 0),
            ).model_dump()

        def ensure_bucket_tool(bucket_name: str, public: bool = False) -> dict[str, Any]:
            payload = client.objects.ensure_bucket(bucket_name, public=public)
            payload["provider"] = client.provider_name()
            return payload

        def upload_text_object_tool(
            bucket_name: str,
            object_path: str,
            text: str,
            content_type: str = "text/plain; charset=utf-8",
            upsert: bool = True,
        ) -> dict[str, Any]:
            payload = client.objects.upload_text(
                bucket_name,
                object_path,
                text,
                content_type=content_type,
                upsert=upsert,
            )
            payload["provider"] = client.provider_name()
            return payload

        def upload_json_object_tool(
            bucket_name: str,
            object_path: str,
            payload: dict[str, Any],
            upsert: bool = True,
        ) -> dict[str, Any]:
            result = client.objects.upload_json(bucket_name, object_path, payload, upsert=upsert)
            result["provider"] = client.provider_name()
            return result

        def download_text_object_tool(bucket_name: str, object_path: str) -> dict[str, Any]:
            text_payload = client.objects.download_text(bucket_name, object_path)
            return {
                "provider": client.provider_name(),
                "bucket_name": bucket_name,
                "object_path": object_path,
                "text": text_payload,
            }

        def list_objects_tool(bucket_name: str, prefix: str = "", limit: int = 100, offset: int = 0) -> dict[str, Any]:
            results = client.objects.list_objects(bucket_name, prefix=prefix, limit=limit, offset=offset)
            return StorageObjectListPayload(
                provider=client.provider_name(),
                bucket_name=bucket_name,
                prefix=prefix,
                result_count=len(results),
                results=[StorageObjectListEntry.model_validate(item) for item in results],
            ).model_dump()

        def delete_object_tool(bucket_name: str, object_path: str) -> dict[str, Any]:
            payload = client.objects.delete_object(bucket_name, object_path)
            payload["provider"] = client.provider_name()
            return payload

        def store_text_artifact_tool(
            artifact_type: str,
            filename: str,
            text: str,
            content_type: str = "text/plain; charset=utf-8",
            series_id: str = "",
            book_id: str = "",
            scene_id: str = "",
            entity_id: str = "",
            story_id: str = "",
            run_id: str = "",
            chapter_id: str = "",
            provider_name: str = "",
            report_kind: str = "",
            metadata: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            payload = client.artifacts.store_text(
                artifact_type=artifact_type,
                filename=filename,
                text=text,
                content_type=content_type,
                series_id=series_id,
                book_id=book_id,
                scene_id=scene_id,
                entity_id=entity_id,
                story_id=story_id,
                run_id=run_id,
                chapter_id=chapter_id,
                provider_name=provider_name,
                report_kind=report_kind,
                metadata=metadata or {},
            )
            payload["provider"] = client.provider_name()
            return payload

        def store_json_artifact_tool(
            artifact_type: str,
            filename: str,
            payload: dict[str, Any],
            series_id: str = "",
            book_id: str = "",
            scene_id: str = "",
            entity_id: str = "",
            story_id: str = "",
            run_id: str = "",
            chapter_id: str = "",
            provider_name: str = "",
            report_kind: str = "",
            metadata: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            result = client.artifacts.store_json(
                artifact_type=artifact_type,
                filename=filename,
                payload=payload,
                series_id=series_id,
                book_id=book_id,
                scene_id=scene_id,
                entity_id=entity_id,
                story_id=story_id,
                run_id=run_id,
                chapter_id=chapter_id,
                provider_name=provider_name,
                report_kind=report_kind,
                metadata=metadata or {},
            )
            result["provider"] = client.provider_name()
            return result

        return [
            build_tool(name="persistence_upsert_provider_config", description="Create or replace a provider configuration payload in the persistence runtime.", args_schema=UpsertProviderConfigArgs, operation="upsert_provider_config", func=lambda **kwargs: ProviderConfigRecord.model_validate(upsert_provider_config_tool(**kwargs)).model_dump(), response_model=ProviderConfigRecord),
            build_tool(name="persistence_get_provider_config", description="Fetch a provider configuration payload from the persistence runtime.", args_schema=GetProviderConfigArgs, operation="get_provider_config", func=get_provider_config_lookup_tool, response_model=ProviderConfigLookupPayload),
            build_tool(name="persistence_get_provider_operational_state", description="Fetch the normalized provider operational state, including config, extracted runtime state, and status rows.", args_schema=GetProviderOperationalStateArgs, operation="get_provider_operational_state", func=get_provider_operational_state_tool, response_model=ProviderOperationalStatePayload),
            build_tool(name="persistence_upsert_provider_status", description="Create or replace a provider operational status payload in the persistence runtime.", args_schema=UpsertProviderStatusArgs, operation="upsert_provider_status", func=lambda **kwargs: ProviderStatusRecord.model_validate(upsert_provider_status_tool(**kwargs)).model_dump(), response_model=ProviderStatusRecord),
            build_tool(name="persistence_list_provider_statuses", description="List provider operational statuses from the persistence runtime.", args_schema=ListProviderStatusesArgs, operation="list_provider_statuses", func=list_provider_statuses_tool, response_model=ProviderStatusListPayload),
            build_tool(name="persistence_upsert_series", description="Create or update a library series record.", args_schema=UpsertSeriesArgs, operation="upsert_series", func=upsert_series_tool),
            build_tool(name="persistence_upsert_book", description="Create or update a library book record.", args_schema=UpsertBookArgs, operation="upsert_book", func=upsert_book_tool),
            build_tool(name="persistence_upsert_scene", description="Create or update a library scene record.", args_schema=UpsertSceneArgs, operation="upsert_scene", func=upsert_scene_tool),
            build_tool(name="persistence_upsert_record", description="Create or update a scoped library record such as an entity or event.", args_schema=UpsertRecordArgs, operation="upsert_record", func=upsert_record_tool),
            build_tool(name="persistence_list_books", description="List library books, optionally filtered by series id.", args_schema=ListBooksArgs, operation="list_books", func=list_books_tool, response_model=LibraryBooksListPayload),
            build_tool(name="persistence_list_scenes", description="List scenes for a book.", args_schema=ListScenesArgs, operation="list_scenes", func=list_scenes_tool, response_model=LibraryScenesListPayload),
            build_tool(name="persistence_list_records", description="List structured library records with optional scope filters.", args_schema=ListRecordsArgs, operation="list_records", func=list_records_tool, response_model=LibraryRecordsListPayload),
            build_tool(name="persistence_upsert_identity_series", description="Create or update an identity-analysis record for a series.", args_schema=UpsertIdentitySeriesArgs, operation="upsert_identity_series", func=upsert_identity_series_tool),
            build_tool(name="persistence_get_identity_series", description="Fetch an identity-analysis record for a series.", args_schema=GetIdentitySeriesArgs, operation="get_identity_series", func=get_identity_series_tool, response_model=IdentitySeriesRecord),
            build_tool(name="persistence_create_job", description="Create or replace a structured job record.", args_schema=CreateJobArgs, operation="create_job", func=create_job_tool),
            build_tool(name="persistence_add_job_log", description="Append a structured log entry to a job.", args_schema=AddJobLogArgs, operation="add_job_log", func=add_job_log_tool),
            build_tool(name="persistence_get_job", description="Fetch a job with its logs.", args_schema=GetJobArgs, operation="get_job", func=get_job_tool, response_model=JobRecordPayload),
            build_tool(name="persistence_list_jobs", description="List structured jobs with an optional job-type filter.", args_schema=ListJobsArgs, operation="list_jobs", func=list_jobs_tool, response_model=JobListPayload),
            build_tool(name="persistence_upsert_story", description="Create or update a generated story record.", args_schema=UpsertStoryArgs, operation="upsert_story", func=upsert_story_tool),
            build_tool(name="persistence_list_stories", description="List generated story records.", args_schema=ListStoriesArgs, operation="list_stories", func=list_stories_tool, response_model=StoryListPayload),
            build_tool(name="persistence_upsert_audiobook_run", description="Create or update an audiobook run record.", args_schema=UpsertAudiobookRunArgs, operation="upsert_audiobook_run", func=upsert_audiobook_run_tool),
            build_tool(name="persistence_upsert_audiobook_chapter", description="Create or update an audiobook chapter record.", args_schema=UpsertAudiobookChapterArgs, operation="upsert_audiobook_chapter", func=upsert_audiobook_chapter_tool),
            build_tool(name="persistence_get_audiobook_run", description="Fetch an audiobook run with its chapters.", args_schema=GetAudiobookRunArgs, operation="get_audiobook_run", func=get_audiobook_run_tool, response_model=AudiobookRunLookupPayload),
            build_tool(name="persistence_list_audiobook_runs", description="List audiobook run records.", args_schema=ListAudiobookRunsArgs, operation="list_audiobook_runs", func=list_audiobook_runs_tool, response_model=AudiobookRunListPayload),
            build_tool(name="persistence_upsert_vector_documents", description="Create or update vector documents in the configured persistence provider.", args_schema=UpsertVectorDocumentsArgs, operation="upsert_vector_documents", func=upsert_vector_documents_tool, response_model=VectorDocumentWritePayload),
            build_tool(name="persistence_query_vector_documents", description="Query vector documents from the configured persistence provider.", args_schema=QueryVectorDocumentsArgs, operation="query_vector_documents", func=query_vector_documents_tool, response_model=VectorQueryPayload),
            build_tool(name="persistence_delete_vector_documents", description="Delete vector documents from the configured persistence provider.", args_schema=DeleteVectorDocumentsArgs, operation="delete_vector_documents", func=delete_vector_documents_tool, response_model=VectorDeletePayload),
            build_tool(name="persistence_ensure_bucket", description="Create or verify an object storage bucket in the configured persistence provider.", args_schema=EnsureBucketArgs, operation="ensure_bucket", func=ensure_bucket_tool, response_model=StorageBucketPayload),
            build_tool(name="persistence_upload_text_object", description="Upload a UTF-8 text object into provider-backed storage.", args_schema=UploadTextObjectArgs, operation="upload_text_object", func=upload_text_object_tool, response_model=StorageObjectWritePayload),
            build_tool(name="persistence_upload_json_object", description="Upload a JSON object into provider-backed storage.", args_schema=UploadJsonObjectArgs, operation="upload_json_object", func=upload_json_object_tool, response_model=StorageObjectWritePayload),
            build_tool(name="persistence_download_text_object", description="Download a UTF-8 text object from provider-backed storage.", args_schema=DownloadTextObjectArgs, operation="download_text_object", func=download_text_object_tool, response_model=StorageObjectTextPayload),
            build_tool(name="persistence_list_objects", description="List objects in provider-backed storage using an optional prefix filter.", args_schema=ListObjectsArgs, operation="list_objects", func=list_objects_tool, response_model=StorageObjectListPayload),
            build_tool(name="persistence_delete_object", description="Delete an object from provider-backed storage.", args_schema=DeleteObjectArgs, operation="delete_object", func=delete_object_tool, response_model=StorageObjectDeletePayload),
            build_tool(name="persistence_store_text_artifact", description="Store a durable text artifact with enforced bucket/path conventions and relational metadata linkage.", args_schema=StoreTextArtifactArgs, operation="store_text_artifact", func=store_text_artifact_tool, response_model=ArtifactStorePayload),
            build_tool(name="persistence_store_json_artifact", description="Store a durable JSON artifact with enforced bucket/path conventions and relational metadata linkage.", args_schema=StoreJsonArtifactArgs, operation="store_json_artifact", func=store_json_artifact_tool, response_model=ArtifactStorePayload),
        ]
