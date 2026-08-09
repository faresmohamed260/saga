from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from saga.services.image_thumbnail_service import ensure_thumbnail


def normalize_runtime_path(path: str) -> str:
    raw = str(path or "").strip()
    if not raw:
        return ""
    try:
        return str(Path(raw).resolve())
    except OSError:
        return raw


def resolve_runtime_thumbnail(image_path: str, thumbnail_path: str = "") -> str:
    source = normalize_runtime_path(image_path)
    if not source:
        return ""
    existing = normalize_runtime_path(thumbnail_path)
    if existing and Path(existing).exists():
        return existing
    try:
        return normalize_runtime_path(ensure_thumbnail(source))
    except Exception:
        return ""


@dataclass(frozen=True)
class RenderArtifactProjection:
    output_path: str
    thumbnail_path: str
    has_output_file: bool
    render_status: str
    workflow_name: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_render_artifact_projection(
    image_path: str,
    *,
    thumbnail_path: str = "",
    render_status: str = "",
    workflow_name: str = "",
) -> RenderArtifactProjection:
    normalized_image_path = normalize_runtime_path(image_path)
    normalized_thumbnail_path = resolve_runtime_thumbnail(normalized_image_path, thumbnail_path)
    return RenderArtifactProjection(
        output_path=normalized_image_path,
        thumbnail_path=normalized_thumbnail_path,
        has_output_file=bool(normalized_image_path and Path(normalized_image_path).exists()),
        render_status=str(render_status or "").strip(),
        workflow_name=str(workflow_name or "").strip(),
    )


def build_entity_render_artifact_projection(
    *,
    entity_image_path: str = "",
    entity_thumbnail_path: str = "",
    latest_image: dict[str, Any] | None = None,
) -> RenderArtifactProjection:
    image_payload = dict(latest_image or {})
    return build_render_artifact_projection(
        str(entity_image_path or image_payload.get("output_path") or ""),
        thumbnail_path=str(entity_thumbnail_path or image_payload.get("thumbnail_path") or ""),
        render_status=str(image_payload.get("render_status") or ""),
        workflow_name=str(image_payload.get("workflow_name") or ""),
    )
