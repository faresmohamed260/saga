from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from packages.artifact_storage_runtime.contracts import ArtifactStorageTool
from saga.providers.artifact_storage_runtime_adapter import create_runtime_artifact_storage_client


class ArtifactStorageService:
    """Saga-facing artifact storage surface over the portable filesystem runtime."""

    def __init__(self, *, storage: ArtifactStorageTool | None = None) -> None:
        self.storage = storage or create_runtime_artifact_storage_client()

    def uploaded_sources_root(self) -> Path:
        return self.storage.ensure_dir("dashboard", "uploads")

    def register_uploaded_source_target(self, filename: str) -> Path:
        return self.uploaded_sources_root() / self._slugify(filename)

    def identity_series_root(self, series_id: str) -> Path:
        return self.storage.ensure_dir("identity_series", self._slugify(series_id))

    def create_decoder_run_dir(self, *, story_mode: str, book_id: str) -> Path:
        return self.storage.create_temp_dir(prefix=f"decoder_{self._slugify(story_mode)}_{self._slugify(book_id)}_")

    def generated_story_exports_root(self) -> Path:
        return self.storage.ensure_dir("dashboard", "story_exports")

    def generated_story_epub_path(self, *, title: str, story_id: str) -> Path:
        filename = f"{self._slugify(title)}_{story_id[:8]}.epub"
        return self.generated_story_exports_root() / filename

    def render_output_dir(self, contract_ref: str | Path) -> Path:
        return self.storage.ensure_dir(*self._render_output_parts(contract_ref))

    def render_images_dir(self, contract_ref: str | Path) -> Path:
        return self.storage.ensure_dir(*self._render_output_parts(contract_ref), "images")

    def render_manifest_path(self, contract_ref: str | Path) -> Path:
        return self.render_output_dir(contract_ref) / "manifest.json"

    def render_report_path(self, contract_ref: str | Path) -> Path:
        return self.render_output_dir(contract_ref) / "render_report.json"

    def write_render_manifest(self, contract_ref: str | Path, payload: dict[str, Any]) -> Path:
        return self.storage.write_json([*self._render_output_parts(contract_ref), "manifest.json"], payload)

    def write_render_report(self, contract_ref: str | Path, payload: dict[str, Any]) -> Path:
        return self.storage.write_json([*self._render_output_parts(contract_ref), "render_report.json"], payload)

    def _render_output_parts(self, contract_ref: str | Path) -> list[str]:
        contract_str = str(contract_ref)
        if contract_str.startswith("db://book/"):
            book_id = contract_str.split("db://book/", 1)[-1].strip() or "book"
            return ["visual_state", "character_sheet_renders", "database_books", self._slugify(book_id)]
        contract = Path(contract_str)
        contract_name = contract.name.replace(".contract.json", "")
        parent_run = contract.parent.parent.name if contract.parent.name == "contracts" else contract.parent.name
        series_name = contract.parent.parent.parent.name if contract.parent.name == "contracts" and contract.parent.parent.parent else "series"
        return [
            "visual_state",
            "character_sheet_renders",
            self._slugify(series_name),
            self._slugify(parent_run),
            self._slugify(contract_name),
        ]

    @staticmethod
    def _slugify(value: str) -> str:
        cleaned = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower())
        return cleaned.strip("-") or "unnamed"
