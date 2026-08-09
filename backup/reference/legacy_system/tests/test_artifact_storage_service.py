from __future__ import annotations

from pathlib import Path

from packages.artifact_storage_runtime.factory import create_artifact_storage_client
from packages.artifact_storage_runtime.models import ArtifactStorageProfile, ArtifactStorageRuntimeConfig
from saga.services.artifact_storage_service import ArtifactStorageService


def test_artifact_storage_service_resolves_domain_specific_paths(tmp_path: Path) -> None:
    profile = ArtifactStorageProfile(
        name="test",
        root_dir=str(tmp_path / "analysis_outputs"),
        temp_root_dir=str(tmp_path / "analysis_outputs" / "tmp"),
    )
    runtime = create_artifact_storage_client(
        config=ArtifactStorageRuntimeConfig(profile=profile),
        profile=profile,
    )
    storage = ArtifactStorageService(storage=runtime)

    render_dir = storage.render_output_dir("db://book/book-123")
    images_dir = storage.render_images_dir("db://book/book-123")
    manifest_path = storage.write_render_manifest("db://book/book-123", {"ok": True})
    report_path = storage.write_render_report("db://book/book-123", {"renders": []})
    export_path = storage.generated_story_epub_path(title="Recovered Story", story_id="story-12345678")
    identity_root = storage.identity_series_root("ACOTAR Main")
    temp_dir = storage.create_decoder_run_dir(story_mode="mid_canon", book_id="book-123")

    assert render_dir.exists()
    assert "database_books" in str(render_dir)
    assert images_dir.exists()
    assert manifest_path.exists()
    assert report_path.exists()
    assert manifest_path.read_text(encoding="utf-8").strip().startswith("{")
    assert export_path.parent.exists()
    assert "recovered-story" in export_path.name
    assert identity_root.exists()
    assert temp_dir.exists()
    assert str(temp_dir).startswith(str(tmp_path / "analysis_outputs" / "tmp"))
