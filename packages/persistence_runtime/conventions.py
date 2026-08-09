"""Policy-enforcing helpers for durable artifacts, vectors, and ephemeral workspaces."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packages.persistence_runtime.contracts import LibraryStore, ObjectStorageStore


SOURCE_DOCUMENT_BUCKET = "source-documents"
GENERATED_IMAGE_BUCKET = "generated-images"
IDENTITY_EXPORT_BUCKET = "identity-exports"
STORY_EXPORT_BUCKET = "story-exports"
AUDIO_OUTPUT_BUCKET = "audio-outputs"
RUNTIME_REPORT_BUCKET = "runtime-reports"

ARTIFACT_BUCKETS = {
    "source_document": SOURCE_DOCUMENT_BUCKET,
    "generated_image": GENERATED_IMAGE_BUCKET,
    "identity_export": IDENTITY_EXPORT_BUCKET,
    "story_export": STORY_EXPORT_BUCKET,
    "audio_output": AUDIO_OUTPUT_BUCKET,
    "runtime_report": RUNTIME_REPORT_BUCKET,
}

VECTOR_NAMESPACE_PATTERN = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")

RESERVED_VECTOR_METADATA_KEYS = {
    "source_scope",
    "content_version",
}


def normalize_identifier(value: str, *, default: str = "default") -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(value or "").strip())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    cleaned = cleaned.strip("-")
    return cleaned or default


def validate_vector_namespace(namespace: str) -> str:
    normalized = str(namespace or "").strip().lower()
    if not normalized:
        raise ValueError("vector namespace is required")
    if "/" in normalized or "\\" in normalized or " " in normalized:
        raise ValueError(f"Invalid vector namespace '{namespace}'. Use dot or hyphen separated segments only.")
    if not VECTOR_NAMESPACE_PATTERN.fullmatch(normalized):
        raise ValueError(f"Invalid vector namespace '{namespace}'.")
    return normalized


def build_vector_namespace(family: str, *parts: str) -> str:
    segments = [normalize_identifier(family)]
    segments.extend(normalize_identifier(part) for part in parts if str(part or "").strip())
    return validate_vector_namespace(".".join(segments))


def build_retrieval_namespace(*, series_id: str, scope_key: str, prefix: str = "retrieval") -> str:
    return build_vector_namespace(prefix, series_id, scope_key)


def validate_vector_document_contract(namespace: str, document: dict[str, Any]) -> dict[str, Any]:
    validate_vector_namespace(namespace)
    normalized = dict(document or {})
    document_id = str(normalized.get("document_id") or "").strip()
    if not document_id:
        raise ValueError("Vector document requires document_id.")
    metadata = normalized.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise ValueError("Vector document metadata must be a JSON object.")
    embedding = normalized.get("embedding") or []
    if not isinstance(embedding, list) or not embedding:
        raise ValueError(f"Vector document '{document_id}' requires a non-empty embedding.")
    normalized["document_id"] = document_id
    normalized["metadata"] = metadata
    normalized["embedding"] = [float(value) for value in embedding]
    return normalized


@dataclass
class ArtifactStorageManager:
    objects: ObjectStorageStore
    library: LibraryStore

    def store_bytes(
        self,
        *,
        artifact_type: str,
        data: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
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
        upsert: bool = True,
        record_type: str = "artifact",
    ) -> dict[str, Any]:
        normalized_type = str(artifact_type or "").strip().lower()
        bucket_name = self.bucket_for_artifact_type(normalized_type)
        object_path = self.object_path_for_artifact(
            artifact_type=normalized_type,
            filename=filename,
            series_id=series_id,
            book_id=book_id,
            scene_id=scene_id,
            entity_id=entity_id,
            story_id=story_id,
            run_id=run_id,
            chapter_id=chapter_id,
            provider_name=provider_name,
            report_kind=report_kind,
        )
        self.objects.ensure_bucket(bucket_name, public=False)
        upload = self.objects.upload_bytes(
            bucket_name,
            object_path,
            data,
            content_type=content_type,
            upsert=upsert,
        )
        artifact_payload = {
            "artifact_type": normalized_type,
            "bucket_name": bucket_name,
            "object_path": object_path,
            "content_type": content_type,
            "size_bytes": len(data),
            "series_id": series_id,
            "book_id": book_id,
            "scene_id": scene_id,
            "entity_id": entity_id,
            "story_id": story_id,
            "run_id": run_id,
            "chapter_id": chapter_id,
            "provider_name": provider_name,
            "report_kind": report_kind,
            "filename": Path(filename).name,
            "created_at": int(time.time()),
            **dict(metadata or {}),
        }
        record_id = self._artifact_record_id(normalized_type, bucket_name, object_path)
        record = self.library.upsert_record(
            record_id,
            record_type=record_type,
            series_id=series_id,
            book_id=book_id,
            scene_id=scene_id,
            title=Path(filename).name,
            payload=artifact_payload,
        )
        return {
            **upload,
            "artifact_type": normalized_type,
            "record_id": record_id,
            "record": record,
            "bucket_name": bucket_name,
            "object_path": object_path,
        }

    def store_text(self, *, text: str, filename: str, content_type: str = "text/plain; charset=utf-8", **kwargs) -> dict[str, Any]:
        return self.store_bytes(
            data=str(text or "").encode("utf-8"),
            filename=filename,
            content_type=content_type,
            **kwargs,
        )

    def store_json(self, *, payload: dict[str, Any], filename: str, **kwargs) -> dict[str, Any]:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        return self.store_bytes(
            data=data,
            filename=filename,
            content_type="application/json",
            **kwargs,
        )

    def promote_file(self, *, source_path: str | Path, delete_source: bool = True, **kwargs) -> dict[str, Any]:
        path = Path(source_path)
        result = self.store_bytes(
            data=path.read_bytes(),
            filename=kwargs.pop("filename", path.name),
            **kwargs,
        )
        if delete_source:
            path.unlink(missing_ok=True)
        return result

    @staticmethod
    def bucket_for_artifact_type(artifact_type: str) -> str:
        normalized = str(artifact_type or "").strip().lower()
        if normalized not in ARTIFACT_BUCKETS:
            raise ValueError(f"Unsupported artifact_type '{artifact_type}'.")
        return ARTIFACT_BUCKETS[normalized]

    def object_path_for_artifact(
        self,
        *,
        artifact_type: str,
        filename: str,
        series_id: str = "",
        book_id: str = "",
        scene_id: str = "",
        entity_id: str = "",
        story_id: str = "",
        run_id: str = "",
        chapter_id: str = "",
        provider_name: str = "",
        report_kind: str = "",
    ) -> str:
        safe_filename = Path(str(filename or "").strip()).name
        if not safe_filename:
            raise ValueError("filename is required")
        if artifact_type == "source_document":
            self._require(series_id, "series_id")
            self._require(book_id, "book_id")
            return f"series/{normalize_identifier(series_id)}/books/{normalize_identifier(book_id)}/source/{safe_filename}"
        if artifact_type == "generated_image":
            self._require(series_id, "series_id")
            self._require(entity_id, "entity_id")
            return f"series/{normalize_identifier(series_id)}/assets/{normalize_identifier(entity_id)}/{safe_filename}"
        if artifact_type == "identity_export":
            self._require(series_id, "series_id")
            return f"series/{normalize_identifier(series_id)}/identity/{safe_filename}"
        if artifact_type == "story_export":
            self._require(series_id, "series_id")
            self._require(story_id, "story_id")
            return f"series/{normalize_identifier(series_id)}/stories/{normalize_identifier(story_id)}/{safe_filename}"
        if artifact_type == "audio_output":
            self._require(series_id, "series_id")
            self._require(run_id, "run_id")
            if str(chapter_id or "").strip():
                return f"series/{normalize_identifier(series_id)}/audio/runs/{normalize_identifier(run_id)}/chapters/{normalize_identifier(chapter_id)}/{safe_filename}"
            return f"series/{normalize_identifier(series_id)}/audio/runs/{normalize_identifier(run_id)}/{safe_filename}"
        if artifact_type == "runtime_report":
            self._require(provider_name, "provider_name")
            resolved_kind = normalize_identifier(report_kind or "general")
            token = uuid.uuid4().hex[:12]
            return f"providers/{normalize_identifier(provider_name)}/reports/{resolved_kind}/{token}-{safe_filename}"
        raise ValueError(f"Unsupported artifact_type '{artifact_type}'.")

    @staticmethod
    def _artifact_record_id(artifact_type: str, bucket_name: str, object_path: str) -> str:
        digest = hashlib.sha256(f"{artifact_type}:{bucket_name}:{object_path}".encode("utf-8")).hexdigest()[:24]
        return f"artifact-{digest}"

    @staticmethod
    def _require(value: str, field_name: str) -> None:
        if not str(value or "").strip():
            raise ValueError(f"{field_name} is required for this artifact type.")


@dataclass
class EphemeralWorkspaceManager:
    root_dir: str

    def __post_init__(self) -> None:
        self.root_path = Path(self.root_dir).resolve()
        self.root_path.mkdir(parents=True, exist_ok=True)

    def create_file(self, *, category: str, suffix: str = "", prefix: str = "", ttl_seconds: int = 3600) -> dict[str, Any]:
        category_dir = self._category_dir(category)
        category_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{normalize_identifier(prefix or 'artifact')}-{uuid.uuid4().hex[:12]}{suffix}"
        target = category_dir / filename
        target.touch()
        expires_at = int(time.time()) + max(1, int(ttl_seconds or 1))
        os.utime(target, (expires_at, expires_at))
        return {"path": str(target), "expires_at": expires_at, "category": normalize_identifier(category)}

    def create_directory(self, *, category: str, prefix: str = "", ttl_seconds: int = 3600) -> dict[str, Any]:
        category_dir = self._category_dir(category)
        category_dir.mkdir(parents=True, exist_ok=True)
        target = category_dir / f"{normalize_identifier(prefix or 'workspace')}-{uuid.uuid4().hex[:12]}"
        target.mkdir(parents=True, exist_ok=True)
        expires_at = int(time.time()) + max(1, int(ttl_seconds or 1))
        os.utime(target, (expires_at, expires_at))
        return {"path": str(target), "expires_at": expires_at, "category": normalize_identifier(category)}

    def cleanup_expired(self, *, now: int | None = None) -> dict[str, Any]:
        cutoff = int(now or time.time())
        deleted_files = 0
        deleted_directories = 0
        for path in sorted(self.root_path.rglob("*"), key=lambda item: len(item.parts), reverse=True):
            try:
                expires_at = int(path.stat().st_mtime)
            except OSError:
                continue
            if expires_at > cutoff:
                continue
            if path.is_file():
                path.unlink(missing_ok=True)
                deleted_files += 1
                continue
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
                deleted_directories += 1
        return {
            "root_dir": str(self.root_path),
            "deleted_files": deleted_files,
            "deleted_directories": deleted_directories,
        }

    def _category_dir(self, category: str) -> Path:
        return self.root_path / normalize_identifier(category)


def default_ephemeral_root(local_storage_root_dir: str) -> str:
    explicit = str(os.getenv("SAGA_EPHEMERAL_ROOT_DIR") or "").strip()
    if explicit:
        return explicit
    if str(local_storage_root_dir or "").strip():
        return str((Path(local_storage_root_dir).resolve() / "_ephemeral"))
    return str((Path(tempfile.gettempdir()) / "saga_ephemeral").resolve())
